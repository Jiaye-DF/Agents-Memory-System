"""skill_service.semantic_search 單測（v1.6.0 Phase 10-1）。

mock llm_metering / skill_repository / system_setting_service，驗證：
- enabled=false / query 空 → early-return 空結果且零次 embedding 呼叫
- analyze_enabled=false → items 有值、ai_reason 全 None、零次 analyze 呼叫
- analyze LLM 失敗 → 降級（items 照回、ai_reason 全 None）
- analyze 回 index/reason → 正確回填、越界 index 忽略
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# 跳過測試若 pgvector 未裝（import 鏈經過 app.models.skill → pgvector）
pgvector = pytest.importorskip("pgvector")  # noqa: F841

from app.services import llm_metering, skill_service  # noqa: E402


class _FakeDB:
    """假 DB session；本測試不會實際查詢，僅做型別占位。"""


def _mk_skill(name: str = "skill-a"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        skill_uid=uuid.uuid4(),
        owner_user_uid=uuid.uuid4(),
        owner=None,
        name=name,
        description=f"{name} description",
        original_filename=f"{name}.zip",
        file_size=1024,
        visibility="public",
        is_active=True,
        favorite_count=0,
        download_count=0,
        created_at=now,
        updated_at=now,
    )


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    top_k: int = 8,
    min_score: float = 0.5,
    analyze_enabled: bool = True,
    analyze_top_n: int = 5,
    analyze_model: str = "anthropic/claude-haiku-4-5",
) -> None:
    async def fake_get_bool(key: str, default: bool, db: object) -> bool:
        if key == "skill.rag.enabled":
            return enabled
        if key == "skill.rag.analyze_enabled":
            return analyze_enabled
        return default

    async def fake_get_int(key: str, default: int, db: object) -> int:
        if key == "skill.rag.top_k":
            return top_k
        if key == "skill.rag.analyze_top_n":
            return analyze_top_n
        return default

    async def fake_get_float(key: str, default: float, db: object) -> float:
        if key == "skill.rag.min_score":
            return min_score
        return default

    async def fake_get(key: str, default: str | None, db: object) -> str | None:
        if key == "skill.rag.analyze_model":
            return analyze_model
        return default

    monkeypatch.setattr(
        skill_service.system_setting_service, "get_bool", fake_get_bool
    )
    monkeypatch.setattr(
        skill_service.system_setting_service, "get_int", fake_get_int
    )
    monkeypatch.setattr(
        skill_service.system_setting_service, "get_float", fake_get_float
    )
    monkeypatch.setattr(skill_service.system_setting_service, "get", fake_get)


def _patch_llm(
    monkeypatch: pytest.MonkeyPatch,
    *,
    embedding: list[float] | None = None,
    analyze_result: list | None = None,
    analyze_exc: Exception | None = None,
) -> AsyncMock:
    """回傳 AsyncMock 版 call_llm_metered，依 purpose 分派。"""

    async def _side_effect(**kwargs):
        purpose = kwargs["purpose"]
        if purpose == llm_metering.PURPOSE_EMBEDDING:
            return embedding if embedding is not None else [0.1] * 1536
        if purpose == llm_metering.PURPOSE_SKILL_ANALYZE:
            if analyze_exc is not None:
                raise analyze_exc
            return analyze_result
        raise AssertionError(f"非預期 purpose: {purpose}")

    mock = AsyncMock(side_effect=_side_effect)
    monkeypatch.setattr(skill_service.llm_metering, "call_llm_metered", mock)
    return mock


def _patch_repos(
    monkeypatch: pytest.MonkeyPatch, rows: list[tuple]
) -> None:
    async def fake_search_similar(vector, top_k, min_score, user_uid, db):
        return rows

    async def fake_is_favorited_bulk(user_uid, item_type, item_uids, db):
        return set()

    async def fake_get_tags_bulk(item_type, item_uids, db):
        return {}

    monkeypatch.setattr(
        skill_service.skill_repository, "search_similar", fake_search_similar
    )
    monkeypatch.setattr(
        skill_service.user_favorite_repository,
        "is_favorited_bulk",
        fake_is_favorited_bulk,
    )
    monkeypatch.setattr(
        skill_service.entity_tag_repository, "get_tags_bulk", fake_get_tags_bulk
    )


def _analyze_calls(mock: AsyncMock) -> list:
    return [
        c
        for c in mock.call_args_list
        if c.kwargs.get("purpose") == llm_metering.PURPOSE_SKILL_ANALYZE
    ]


@pytest.mark.asyncio
async def test_semantic_search_disabled_returns_empty_without_llm(
    monkeypatch: pytest.MonkeyPatch,
):
    """skill.rag.enabled=false 時回空結果且完全不呼叫 LLM。"""
    _patch_settings(monkeypatch, enabled=False)
    llm_mock = _patch_llm(monkeypatch)

    out = await skill_service.semantic_search(
        str(uuid.uuid4()), "找一個能寄信的 skill", None, _FakeDB()
    )

    assert out == {"items": [], "analysis": None}
    llm_mock.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_search_empty_query_returns_empty_without_llm(
    monkeypatch: pytest.MonkeyPatch,
):
    """query 空字串（含純空白）時回空結果且完全不呼叫 LLM。"""
    _patch_settings(monkeypatch)
    llm_mock = _patch_llm(monkeypatch)

    for query in ("", "   "):
        out = await skill_service.semantic_search(
            str(uuid.uuid4()), query, None, _FakeDB()
        )
        assert out == {"items": [], "analysis": None}
    llm_mock.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_search_analyze_disabled_items_without_reason(
    monkeypatch: pytest.MonkeyPatch,
):
    """analyze_enabled=false 時 items 照回、ai_reason 全 None、零次 analyze 呼叫。"""
    _patch_settings(monkeypatch, analyze_enabled=False)
    llm_mock = _patch_llm(monkeypatch)
    skill_a, skill_b = _mk_skill("skill-a"), _mk_skill("skill-b")
    _patch_repos(monkeypatch, [(skill_a, 0.9), (skill_b, 0.7)])

    out = await skill_service.semantic_search(
        str(uuid.uuid4()), "找一個能寄信的 skill", None, _FakeDB()
    )

    assert len(out["items"]) == 2
    assert out["items"][0]["name"] == "skill-a"
    assert out["items"][0]["score"] == 0.9
    assert all(it["ai_reason"] is None for it in out["items"])
    assert _analyze_calls(llm_mock) == []


@pytest.mark.asyncio
async def test_semantic_search_analyze_failure_degrades_gracefully(
    monkeypatch: pytest.MonkeyPatch,
):
    """analyze LLM raise 時 items 照回、ai_reason 全 None（降級不拋錯）。"""
    _patch_settings(monkeypatch)
    _patch_llm(monkeypatch, analyze_exc=RuntimeError("llm down"))
    skill_a, skill_b = _mk_skill("skill-a"), _mk_skill("skill-b")
    _patch_repos(monkeypatch, [(skill_a, 0.9), (skill_b, 0.7)])

    out = await skill_service.semantic_search(
        str(uuid.uuid4()), "找一個能寄信的 skill", None, _FakeDB()
    )

    assert len(out["items"]) == 2
    assert all(it["ai_reason"] is None for it in out["items"])


@pytest.mark.asyncio
async def test_semantic_search_analyze_backfills_reason_and_ignores_bad_index(
    monkeypatch: pytest.MonkeyPatch,
):
    """analyze 回傳 index/reason 正確回填，越界 index 與非法 entry 忽略。"""
    _patch_settings(monkeypatch)
    llm_mock = _patch_llm(
        monkeypatch,
        analyze_result=[
            {"index": 0, "reason": "完全符合寄信需求"},
            {"index": 99, "reason": "越界應忽略"},
            {"index": True, "reason": "bool index 應忽略"},
            "not-a-dict",
        ],
    )
    skill_a, skill_b = _mk_skill("skill-a"), _mk_skill("skill-b")
    _patch_repos(monkeypatch, [(skill_a, 0.9), (skill_b, 0.7)])

    out = await skill_service.semantic_search(
        str(uuid.uuid4()), "找一個能寄信的 skill", None, _FakeDB()
    )

    assert out["items"][0]["ai_reason"] == "完全符合寄信需求"
    assert out["items"][1]["ai_reason"] is None
    assert len(_analyze_calls(llm_mock)) == 1


@pytest.mark.asyncio
async def test_semantic_search_analyze_payload_limited_to_top_n(
    monkeypatch: pytest.MonkeyPatch,
):
    """analyze payload 只送前 analyze_top_n 筆，且帶 name / description / score。"""
    _patch_settings(monkeypatch, analyze_top_n=1)
    llm_mock = _patch_llm(monkeypatch, analyze_result=[])
    skill_a, skill_b = _mk_skill("skill-a"), _mk_skill("skill-b")
    _patch_repos(monkeypatch, [(skill_a, 0.9), (skill_b, 0.7)])

    await skill_service.semantic_search(
        str(uuid.uuid4()), "找一個能寄信的 skill", None, _FakeDB()
    )

    calls = _analyze_calls(llm_mock)
    assert len(calls) == 1
    payload = calls[0].kwargs["skills_payload"]
    assert payload == [
        {"name": "skill-a", "description": "skill-a description", "score": 0.9}
    ]
    assert calls[0].kwargs["model"] == "anthropic/claude-haiku-4-5"


@pytest.mark.asyncio
async def test_semantic_search_top_k_capped_at_max(
    monkeypatch: pytest.MonkeyPatch,
):
    """呼叫端 top_k 超過上限時裁切至 RAG_TOP_K_MAX。"""
    _patch_settings(monkeypatch, analyze_enabled=False)
    _patch_llm(monkeypatch)
    captured: dict = {}

    async def fake_search_similar(vector, top_k, min_score, user_uid, db):
        captured["top_k"] = top_k
        return []

    monkeypatch.setattr(
        skill_service.skill_repository, "search_similar", fake_search_similar
    )

    out = await skill_service.semantic_search(
        str(uuid.uuid4()), "查詢", 999, _FakeDB()
    )

    assert captured["top_k"] == skill_service.RAG_TOP_K_MAX
    assert out == {"items": [], "analysis": None}
