"""skill_embedding_service 單測（v1.6.0 Phase 10-1）。

純函式 `build_embedding_text` 與 `update_embedding` 的失敗降級；
不依賴 DB / LLM，zip 以 io.BytesIO + zipfile 動態建構，
DB 互動透過 monkeypatch 隔離（對齊 test_classifier_service 慣例）。
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
# build_embedding_text
# ---------------------------------------------------------------------------


def test_build_embedding_text_normal_combination():
    """正常組合 name + description + zip 內文字檔，SKILL.md 內容優先出現。"""
    zip_bytes = _make_zip(
        {
            "notes.md": b"notes content",
            "SKILL.md": b"skill content",
            "README.md": b"readme content",
        }
    )
    out = skill_embedding_service.build_embedding_text(
        "my-skill", "my description", zip_bytes, max_chars=8000
    )
    assert out.startswith("my-skill\n\nmy description")
    assert "skill content" in out
    assert "readme content" in out
    assert "notes content" in out
    # 優先序：SKILL.md → README.md → 其餘依路徑
    assert out.index("skill content") < out.index("readme content")
    assert out.index("readme content") < out.index("notes content")


def test_build_embedding_text_zip_none_falls_back_to_base():
    """zip_bytes=None 時退化為只含 name + description。"""
    out = skill_embedding_service.build_embedding_text(
        "my-skill", "my description", None, max_chars=8000
    )
    assert out == "my-skill\n\nmy description"


def test_build_embedding_text_bad_zip_falls_back_to_base():
    """損毀 bytes（BadZipFile）時退化為只含 name + description。"""
    out = skill_embedding_service.build_embedding_text(
        "my-skill", "my description", b"not-a-zip-file", max_chars=8000
    )
    assert out == "my-skill\n\nmy description"


def test_build_embedding_text_truncates_content_to_max_chars():
    """超長檔案內容截斷至 max_chars（base 之外的內容段長度受限）。"""
    zip_bytes = _make_zip({"SKILL.md": b"x" * 10000})
    max_chars = 100
    out = skill_embedding_service.build_embedding_text(
        "n", "d", zip_bytes, max_chars=max_chars
    )
    base = "n\n\nd"
    assert out.startswith(base + "\n\n")
    content = out[len(base) + 2 :]
    assert len(content) == max_chars
    assert content == "x" * max_chars


def test_build_embedding_text_skips_non_text_extensions():
    """非 .md / .txt 檔案（如 .py）不納入 embedding 文字。"""
    zip_bytes = _make_zip(
        {
            "script.py": b"python code here",
            "SKILL.md": b"skill content",
            "data.txt": b"txt content",
        }
    )
    out = skill_embedding_service.build_embedding_text(
        "n", "d", zip_bytes, max_chars=8000
    )
    assert "skill content" in out
    assert "txt content" in out
    assert "python code here" not in out


def test_build_embedding_text_skips_undecodable_file():
    """utf-8 decode 失敗的檔案跳過，其餘檔案照常納入。"""
    zip_bytes = _make_zip(
        {
            "bad.md": b"\xff\xfe\xfa invalid utf-8 \x80\x81",
            "SKILL.md": b"skill content",
        }
    )
    out = skill_embedding_service.build_embedding_text(
        "n", "d", zip_bytes, max_chars=8000
    )
    assert "skill content" in out
    assert "invalid utf-8" not in out


def test_build_embedding_text_only_non_text_files_falls_back_to_base():
    """zip 內無任何 .md / .txt 時退化為只含 name + description。"""
    zip_bytes = _make_zip({"script.py": b"python code"})
    out = skill_embedding_service.build_embedding_text(
        "n", "d", zip_bytes, max_chars=8000
    )
    assert out == "n\n\nd"


# ---------------------------------------------------------------------------
# update_embedding
# ---------------------------------------------------------------------------


def _mk_skill():
    return SimpleNamespace(
        skill_uid=uuid.uuid4(),
        owner_user_uid=uuid.uuid4(),
        name="my-skill",
        description="my description",
    )


@pytest.mark.asyncio
async def test_update_embedding_success_writes_vector(
    monkeypatch: pytest.MonkeyPatch,
):
    """成功路徑：embedding 向量透過 update_obj 寫回 skill。"""
    vector = [0.1] * 1536
    captured: dict = {}

    async def fake_get_int(key: str, default: int, db: object) -> int:
        return default

    async def fake_call_llm_metered(**kwargs):
        captured["llm_kwargs"] = kwargs
        return vector

    async def fake_update_obj(skill, update_data, db):
        captured["update_data"] = update_data
        return skill

    monkeypatch.setattr(
        skill_embedding_service.system_setting_service, "get_int", fake_get_int
    )
    monkeypatch.setattr(
        skill_embedding_service.llm_metering,
        "call_llm_metered",
        fake_call_llm_metered,
    )
    monkeypatch.setattr(
        skill_embedding_service.skill_repository, "update_obj", fake_update_obj
    )

    skill = _mk_skill()
    await skill_embedding_service.update_embedding(skill, None, _FakeDB())

    assert captured["update_data"] == {"embedding": vector}
    assert (
        captured["llm_kwargs"]["purpose"]
        == skill_embedding_service.llm_metering.PURPOSE_EMBEDDING
    )
    assert captured["llm_kwargs"]["user_uid"] == str(skill.owner_user_uid)


@pytest.mark.asyncio
async def test_update_embedding_llm_failure_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
):
    """LLM 失敗時只 log warning 不 raise，且不寫回 embedding。"""
    update_called: list = []

    async def fake_get_int(key: str, default: int, db: object) -> int:
        return default

    async def fake_call_llm_metered(**kwargs):
        raise RuntimeError("embedding provider down")

    async def fake_update_obj(skill, update_data, db):
        update_called.append(update_data)
        return skill

    monkeypatch.setattr(
        skill_embedding_service.system_setting_service, "get_int", fake_get_int
    )
    monkeypatch.setattr(
        skill_embedding_service.llm_metering,
        "call_llm_metered",
        fake_call_llm_metered,
    )
    monkeypatch.setattr(
        skill_embedding_service.skill_repository, "update_obj", fake_update_obj
    )

    # 不應 raise
    await skill_embedding_service.update_embedding(_mk_skill(), None, _FakeDB())
    assert update_called == []
