"""skill_embedding_service 單測（v1.6.2 多向量 1:N）。

純函式 `build_embedding_texts` 的三段切分與 `update_embedding` 的
逐段 embed + 全量替換 / 失敗降級；不依賴 DB / LLM，
zip 以 io.BytesIO + zipfile 動態建構，DB 互動透過 monkeypatch 隔離
（對齊 test_classifier_service 慣例）。
"""
from __future__ import annotations

import io
import uuid
import zipfile
from types import SimpleNamespace

import pytest

# 跳過測試若 pgvector 未裝（import 鏈經過 app.models.skill → pgvector）
pgvector = pytest.importorskip("pgvector")  # noqa: F841

from app.services import skill_embedding_service  # noqa: E402


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


class _FakeDB:
    """假 DB session；本測試不會實際查詢，僅做型別占位。"""


# ---------------------------------------------------------------------------
# build_embedding_texts
# ---------------------------------------------------------------------------


def test_build_embedding_texts_normal_three_segments():
    """正常組合切出 name / description / content 三鍵，SKILL.md 內容優先出現。"""
    zip_bytes = _make_zip(
        {
            "notes.md": b"notes content",
            "SKILL.md": b"skill content",
            "README.md": b"readme content",
        }
    )
    out = skill_embedding_service.build_embedding_texts(
        "my-skill", "my description", zip_bytes, max_chars=8000
    )
    assert set(out.keys()) == {"name", "description", "content"}
    assert out["name"] == "my-skill"
    assert out["description"] == "my description"
    content = out["content"]
    assert "skill content" in content
    assert "readme content" in content
    assert "notes content" in content
    # 優先序：SKILL.md → README.md → 其餘依路徑
    assert content.index("skill content") < content.index("readme content")
    assert content.index("readme content") < content.index("notes content")


def test_build_embedding_texts_zip_none_no_content_key():
    """zip_bytes=None 時不出 content 鍵，僅 name + description。"""
    out = skill_embedding_service.build_embedding_texts(
        "my-skill", "my description", None, max_chars=8000
    )
    assert out == {"name": "my-skill", "description": "my description"}


def test_build_embedding_texts_bad_zip_no_content_key():
    """損毀 bytes（BadZipFile）時不出 content 鍵，僅 name + description。"""
    out = skill_embedding_service.build_embedding_texts(
        "my-skill", "my description", b"not-a-zip-file", max_chars=8000
    )
    assert out == {"name": "my-skill", "description": "my description"}


def test_build_embedding_texts_empty_name_and_description_no_keys():
    """name / description 為空字串時不出對應鍵。"""
    zip_bytes = _make_zip({"SKILL.md": b"skill content"})
    out = skill_embedding_service.build_embedding_texts(
        "", "", zip_bytes, max_chars=8000
    )
    assert out == {"content": "skill content"}


def test_build_embedding_texts_truncates_content_to_max_chars():
    """超長檔案內容截斷至 max_chars（僅 content 段受限，name / description 不動）。"""
    zip_bytes = _make_zip({"SKILL.md": b"x" * 10000})
    max_chars = 100
    out = skill_embedding_service.build_embedding_texts(
        "n", "d", zip_bytes, max_chars=max_chars
    )
    assert out["name"] == "n"
    assert out["description"] == "d"
    assert out["content"] == "x" * max_chars


def test_build_embedding_texts_skips_non_text_extensions():
    """非 .md / .txt 檔案（如 .py）不納入 content 段。"""
    zip_bytes = _make_zip(
        {
            "script.py": b"python code here",
            "SKILL.md": b"skill content",
            "data.txt": b"txt content",
        }
    )
    out = skill_embedding_service.build_embedding_texts(
        "n", "d", zip_bytes, max_chars=8000
    )
    assert "skill content" in out["content"]
    assert "txt content" in out["content"]
    assert "python code here" not in out["content"]


def test_build_embedding_texts_skips_undecodable_file():
    """utf-8 decode 失敗的檔案跳過，其餘檔案照常納入 content。"""
    zip_bytes = _make_zip(
        {
            "bad.md": b"\xff\xfe\xfa invalid utf-8 \x80\x81",
            "SKILL.md": b"skill content",
        }
    )
    out = skill_embedding_service.build_embedding_texts(
        "n", "d", zip_bytes, max_chars=8000
    )
    assert "skill content" in out["content"]
    assert "invalid utf-8" not in out["content"]


def test_build_embedding_texts_only_non_text_files_no_content_key():
    """zip 內無任何 .md / .txt 時不出 content 鍵。"""
    zip_bytes = _make_zip({"script.py": b"python code"})
    out = skill_embedding_service.build_embedding_texts(
        "n", "d", zip_bytes, max_chars=8000
    )
    assert out == {"name": "n", "description": "d"}


# ---------------------------------------------------------------------------
# update_embedding
# ---------------------------------------------------------------------------


def _mk_skill(name: str = "my-skill", description: str = "my description"):
    return SimpleNamespace(
        skill_uid=uuid.uuid4(),
        owner_user_uid=uuid.uuid4(),
        name=name,
        description=description,
    )


def _patch_get_int(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_int(key: str, default: int, db: object) -> int:
        return default

    monkeypatch.setattr(
        skill_embedding_service.system_setting_service, "get_int", fake_get_int
    )


@pytest.mark.asyncio
async def test_update_embedding_success_replaces_all_segments(
    monkeypatch: pytest.MonkeyPatch,
):
    """成功路徑：每段各呼叫一次 embed，replace_for_skill 收到正確 (source_type, vector) 列表。"""
    llm_calls: list[dict] = []
    captured: dict = {}

    async def fake_call_llm_metered(**kwargs):
        llm_calls.append(kwargs)
        # 依段落回不同向量，驗證配對正確
        return [float(len(llm_calls))] * 1536

    async def fake_replace_for_skill(skill_uid, rows, db):
        captured["skill_uid"] = skill_uid
        captured["rows"] = rows

    _patch_get_int(monkeypatch)
    monkeypatch.setattr(
        skill_embedding_service.llm_metering,
        "call_llm_metered",
        fake_call_llm_metered,
    )
    monkeypatch.setattr(
        skill_embedding_service.skill_embedding_repository,
        "replace_for_skill",
        fake_replace_for_skill,
    )

    zip_bytes = _make_zip({"SKILL.md": b"skill content"})
    skill = _mk_skill()
    await skill_embedding_service.update_embedding(skill, zip_bytes, _FakeDB())

    # 三段 → 三次 embed，逐段配對向量
    assert len(llm_calls) == 3
    assert all(
        c["purpose"] == skill_embedding_service.llm_metering.PURPOSE_EMBEDDING
        for c in llm_calls
    )
    assert all(c["user_uid"] == str(skill.owner_user_uid) for c in llm_calls)
    assert [c["text"] for c in llm_calls] == [
        "my-skill",
        "my description",
        "skill content",
    ]

    assert captured["skill_uid"] == str(skill.skill_uid)
    assert captured["rows"] == [
        ("name", [1.0] * 1536),
        ("description", [2.0] * 1536),
        ("content", [3.0] * 1536),
    ]


@pytest.mark.asyncio
async def test_update_embedding_zip_none_embeds_two_segments(
    monkeypatch: pytest.MonkeyPatch,
):
    """zip_bytes=None 時僅 name / description 兩段 → 兩次 embed、兩列 rows。"""
    llm_calls: list[dict] = []
    captured: dict = {}
    vector = [0.1] * 1536

    async def fake_call_llm_metered(**kwargs):
        llm_calls.append(kwargs)
        return vector

    async def fake_replace_for_skill(skill_uid, rows, db):
        captured["rows"] = rows

    _patch_get_int(monkeypatch)
    monkeypatch.setattr(
        skill_embedding_service.llm_metering,
        "call_llm_metered",
        fake_call_llm_metered,
    )
    monkeypatch.setattr(
        skill_embedding_service.skill_embedding_repository,
        "replace_for_skill",
        fake_replace_for_skill,
    )

    await skill_embedding_service.update_embedding(_mk_skill(), None, _FakeDB())

    assert len(llm_calls) == 2
    assert captured["rows"] == [("name", vector), ("description", vector)]


@pytest.mark.asyncio
async def test_update_embedding_llm_failure_abandons_batch_without_raise(
    monkeypatch: pytest.MonkeyPatch,
):
    """任一段 embed raise → 整批放棄（replace_for_skill 零呼叫）且不拋錯。"""
    llm_calls: list[dict] = []
    replace_called: list = []

    async def fake_call_llm_metered(**kwargs):
        llm_calls.append(kwargs)
        if len(llm_calls) == 2:
            # 第二段（description）失敗
            raise RuntimeError("embedding provider down")
        return [0.1] * 1536

    async def fake_replace_for_skill(skill_uid, rows, db):
        replace_called.append(rows)

    _patch_get_int(monkeypatch)
    monkeypatch.setattr(
        skill_embedding_service.llm_metering,
        "call_llm_metered",
        fake_call_llm_metered,
    )
    monkeypatch.setattr(
        skill_embedding_service.skill_embedding_repository,
        "replace_for_skill",
        fake_replace_for_skill,
    )

    # 不應 raise
    await skill_embedding_service.update_embedding(_mk_skill(), None, _FakeDB())
    assert replace_called == []


@pytest.mark.asyncio
async def test_update_embedding_no_texts_skips_replace_without_raise(
    monkeypatch: pytest.MonkeyPatch,
):
    """texts 全空（name / description 空且無 zip）→ 不呼叫 embed 與 replace 也不拋錯。"""
    llm_calls: list = []
    replace_called: list = []

    async def fake_call_llm_metered(**kwargs):
        llm_calls.append(kwargs)
        return [0.1] * 1536

    async def fake_replace_for_skill(skill_uid, rows, db):
        replace_called.append(rows)

    _patch_get_int(monkeypatch)
    monkeypatch.setattr(
        skill_embedding_service.llm_metering,
        "call_llm_metered",
        fake_call_llm_metered,
    )
    monkeypatch.setattr(
        skill_embedding_service.skill_embedding_repository,
        "replace_for_skill",
        fake_replace_for_skill,
    )

    # 不應 raise
    await skill_embedding_service.update_embedding(
        _mk_skill(name="", description=""), None, _FakeDB()
    )
    assert llm_calls == []
    assert replace_called == []
