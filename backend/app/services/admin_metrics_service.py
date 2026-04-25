"""Admin metrics service（v1.3.0）。

職責：把 ``llm_call_log_repository.aggregate_cost`` 的結果轉成
``CostMetricsResponse`` 可序列化的 dict（floats / Decimals 都對齊 schema）。

設計依據：docs/Arch/01-observability-and-metrics.md §5-5
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import llm_call_log_repository

logger = logging.getLogger(__name__)


async def get_cost_metrics(
    range_key: str, group_by: str, db: AsyncSession
) -> dict:
    """讀取成本 metrics；空資料時回零值結構（不 raise）。"""
    raw = await llm_call_log_repository.aggregate_cost(range_key, group_by, db)

    breakdown = [
        {
            "key": item["key"],
            "actual": item["actual"],
            "baseline": item["baseline"],
            "calls": item["calls"],
        }
        for item in raw.get("breakdown", [])
    ]

    return {
        "range": range_key,
        "group_by": group_by,
        "total_actual_usd": raw.get("total_actual", Decimal("0")),
        "total_baseline_usd": raw.get("total_baseline", Decimal("0")),
        "saved_usd": raw.get("saved", Decimal("0")),
        "saved_pct": float(raw.get("saved_pct", 0.0) or 0.0),
        "breakdown": breakdown,
    }
