"""Admin metrics 相關 Pydantic schema（v1.3.0）。

對應 endpoint：``GET /api/v1/admin/metrics/cost``
設計依據：docs/Arch/01-observability-and-metrics.md §5-5
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# range_key / group_by 的允許值（同時用在 Query 與 service 內 whitelist）
RangeKey = Literal["today", "7d", "30d", "month"]
GroupByKey = Literal["route", "model", "user", "session", "purpose"]


class CostBreakdownItem(BaseModel):
    """單一切片的成本明細。"""

    key: str = Field(..., description="切片鍵（依 group_by；NULL 值顯示為 '(null)'）")
    actual: Decimal = Field(..., description="實際花費 USD")
    baseline: Decimal = Field(..., description="counterfactual baseline 花費 USD")
    calls: int = Field(..., description="呼叫次數")


class CostMetricsResponse(BaseModel):
    """``GET /api/v1/admin/metrics/cost`` 的 response。"""

    range: RangeKey = Field(..., description="查詢區間")
    group_by: GroupByKey = Field(..., description="切片維度")
    total_actual_usd: Decimal = Field(..., description="實際總花費 USD")
    total_baseline_usd: Decimal = Field(
        ..., description="假設全走 expensive 模型會花的 USD（counterfactual）"
    )
    saved_usd: Decimal = Field(..., description="省下的金額 USD（baseline - actual）")
    saved_pct: float = Field(..., description="省下的百分比（0 ~ 100）")
    breakdown: list[CostBreakdownItem] = Field(
        default_factory=list, description="依 group_by 切片後的明細，按 actual desc 排序"
    )
