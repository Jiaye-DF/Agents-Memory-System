"""路由分類器（v1.3.4）單元測試。

僅覆蓋規則引擎邏輯與 baseline 估算；DB 互動透過 monkeypatch 隔離
``system_setting_service`` 的存取，避免依賴實際 PostgreSQL。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.services import classifier_service


class _FakeDB:
    """假 DB session；本測試不會實際查詢，僅做型別占位。"""


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    model: str = "rule-based",
    cheap_model: str = "anthropic/claude-haiku-4-5",
    skip_template: str = "收到,繼續~",
    thresholds: dict[str, Any] | None = None,
) -> None:
    if thresholds is None:
        thresholds = dict(classifier_service.DEFAULT_THRESHOLDS)

    async def fake_get_bool(key: str, default: bool, db: object) -> bool:
        if key == "classifier.enabled":
            return enabled
        return default

    async def fake_get(key: str, default: str | None, db: object) -> str | None:
        if key == "classifier.model":
            return model
        if key == "classifier.cheap_model":
            return cheap_model
        if key == "classifier.skip_response_template":
            return skip_template
        return default

    async def fake_get_json(
        key: str, default: dict | list | None, db: object
    ) -> dict | list | None:
        if key == "classifier.thresholds":
            return thresholds
        return default

    monkeypatch.setattr(
        classifier_service.system_setting_service, "get_bool", fake_get_bool
    )
    monkeypatch.setattr(
        classifier_service.system_setting_service, "get", fake_get
    )
    monkeypatch.setattr(
        classifier_service.system_setting_service, "get_json", fake_get_json
    )


@pytest.mark.asyncio
async def test_greeting_whitelist_hits_skip(monkeypatch: pytest.MonkeyPatch):
    _patch_settings(monkeypatch)
    decision = await classifier_service.classify(
        "hi",
        attachments=None,
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "skip"
    assert decision["matched_rule"].startswith("greeting_whitelist:hi")


@pytest.mark.asyncio
async def test_greeting_whitelist_chinese(monkeypatch: pytest.MonkeyPatch):
    _patch_settings(monkeypatch)
    decision = await classifier_service.classify(
        "你好",
        attachments=None,
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "skip"
    assert "greeting_whitelist" in decision["matched_rule"]


@pytest.mark.asyncio
async def test_pure_emoji_skip(monkeypatch: pytest.MonkeyPatch):
    # min_length=0 才能讓 emoji 規則先生效（否則 emoji 字長小於 min_length 會先被攔）
    thresholds = dict(classifier_service.DEFAULT_THRESHOLDS)
    thresholds["min_length"] = 0
    _patch_settings(monkeypatch, thresholds=thresholds)
    decision = await classifier_service.classify(
        "👍🎉",
        attachments=None,
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "skip"
    assert decision["matched_rule"] == "emoji_only"


@pytest.mark.asyncio
async def test_short_message_below_min_length_skip(
    monkeypatch: pytest.MonkeyPatch,
):
    thresholds = dict(classifier_service.DEFAULT_THRESHOLDS)
    thresholds["min_length"] = 10
    # 把 whitelist 清掉，避免短字串先命中 greeting
    thresholds["greeting_whitelist"] = []
    _patch_settings(monkeypatch, thresholds=thresholds)
    decision = await classifier_service.classify(
        "??",
        attachments=None,
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "skip"
    assert decision["matched_rule"].startswith("min_length:")


@pytest.mark.asyncio
async def test_short_qa_routes_to_cheap(monkeypatch: pytest.MonkeyPatch):
    _patch_settings(monkeypatch)
    decision = await classifier_service.classify(
        "請問什麼是 RAG?",
        attachments=None,
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "cheap"
    assert decision["matched_rule"] == "short_qa"


@pytest.mark.asyncio
async def test_long_message_routes_to_expensive(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_settings(monkeypatch)
    long_text = "請幫我詳細分析以下這段文字並給我結構化的回覆。" * 5
    decision = await classifier_service.classify(
        long_text,
        attachments=None,
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "expensive"


@pytest.mark.asyncio
async def test_many_history_turns_routes_to_expensive(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_settings(monkeypatch)
    # 短訊息但歷史輪次過多 → 不視為簡單問答
    decision = await classifier_service.classify(
        "繼續吧",
        attachments=None,
        history_turns=20,
        db=_FakeDB(),
    )
    # "繼續吧" 不在 whitelist、長度 3 不小於 min_length=3、無 emoji-only，
    # 但 history_turns 過多 → 不會走 cheap，落入 expensive
    assert decision["route"] == "expensive"


@pytest.mark.asyncio
async def test_classifier_disabled_routes_all_to_expensive(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_settings(monkeypatch, enabled=False)
    decision = await classifier_service.classify(
        "hi",  # 即便是 greeting，disabled 時也應走 expensive
        attachments=None,
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "expensive"
    assert decision["reason"] == "classifier_disabled"


@pytest.mark.asyncio
async def test_image_attachment_force_expensive(monkeypatch: pytest.MonkeyPatch):
    _patch_settings(monkeypatch)
    decision = await classifier_service.classify(
        "hi",  # 即使是 greeting + 圖片 → 走 expensive
        attachments=[
            {"kind": "image", "uid": "img-1", "file_name": "a.png"},
        ],
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "expensive"
    assert decision["matched_rule"] == "image_attachment"
    assert decision["reason"] == "multimodal_force"


@pytest.mark.asyncio
async def test_image_attachment_force_overrides_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    """multimodal 強制路由必須優先於 classifier.enabled。"""
    _patch_settings(monkeypatch, enabled=False)
    decision = await classifier_service.classify(
        "",
        attachments=[{"kind": "image"}],
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "expensive"
    assert decision["matched_rule"] == "image_attachment"


@pytest.mark.asyncio
async def test_pure_image_no_text_routes_expensive(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_settings(monkeypatch)
    decision = await classifier_service.classify(
        "",
        attachments=[{"kind": "image"}],
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "expensive"
    assert decision["matched_rule"] == "image_attachment"


@pytest.mark.asyncio
async def test_pdf_attachment_does_not_force_expensive(
    monkeypatch: pytest.MonkeyPatch,
):
    """僅 PDF 附件 + greeting 不觸發強制路由，應走 skip 規則。"""
    _patch_settings(monkeypatch)
    decision = await classifier_service.classify(
        "hi",
        attachments=[{"kind": "pdf", "uid": "pdf-1"}],
        history_turns=0,
        db=_FakeDB(),
    )
    assert decision["route"] == "skip"


def test_estimate_baseline_for_skip_empty_string():
    # 空字串不可除以零或 raise
    cost = classifier_service.estimate_baseline_for_skip("")
    assert isinstance(cost, Decimal)
    assert cost >= Decimal("0")


def test_estimate_baseline_for_skip_pure_emoji():
    cost = classifier_service.estimate_baseline_for_skip("👍")
    assert isinstance(cost, Decimal)
    assert cost >= Decimal("0")


def test_estimate_baseline_for_skip_normal_text():
    cost = classifier_service.estimate_baseline_for_skip(
        "請問你能幫我做什麼？" * 10
    )
    assert isinstance(cost, Decimal)
    # 有 input + output token 估算後成本應大於 0（前提：model_prices.yaml 載入到 expensive 單價）
    # 若 yaml 不在或未含 expensive model，會回 0；此處只 assert 非負
    assert cost >= Decimal("0")
