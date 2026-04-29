"""llm_call_log repository（v1.3.0）。

提供：
- log(): 單筆寫入（缺漏欄位走 DB DEFAULT；寫入失敗僅 log error 不 raise，避免 metrics 壞掉拖垮主流程）
- aggregate_cost(): 給 admin endpoint 用，依 range_key + group_by 動態組 SQL

設計依據：docs/Arch/01-observability-and-metrics.md §5-5
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_call_log import LlmCallLog

logger = logging.getLogger(__name__)


# range_key → SQL WHERE 子句的對應；皆以 ts 欄位過濾
_RANGE_WHERE: dict[str, str] = {
    "today": "ts >= CURRENT_DATE",
    "7d": "ts >= NOW() - INTERVAL '7 days'",
    "30d": "ts >= NOW() - INTERVAL '30 days'",
    "month": "ts >= DATE_TRUNC('month', NOW())",
}

# group_by → 對應到 SQL 的欄位名（防止 SQL injection，僅 whitelist）
_GROUP_COLUMN: dict[str, str] = {
    "route": "route",
    "model": "model",
    "user": "user_uid::text",
    "session": "session_uid::text",
    "purpose": "purpose",
}


async def log(payload: dict, db: AsyncSession) -> None:
    """單筆寫入；缺漏欄位走 DB DEFAULT。任何 DB 錯誤僅 log，不 raise。

    payload 接受彈性 dict；本函式只會挑 LlmCallLog model 接受的欄位寫入。
    """
    try:
        # 過濾未知欄位
        allowed_fields = {
            "session_uid",
            "user_uid",
            "agent_uid",
            "purpose",
            "route",
            "model",
            "input_tokens",
            "output_tokens",
            "cache_creation_tokens",
            "cache_read_tokens",
            "actual_cost_usd",
            "baseline_cost_usd",
            "latency_ms",
            "rag_hit_count",
            "rag_max_score",
            "error",
        }
        clean: dict[str, object] = {
            k: v for k, v in (payload or {}).items() if k in allowed_fields
        }
        entity = LlmCallLog(**clean)
        db.add(entity)
        await db.flush()
    except Exception as exc:  # 落入 metrics 自我保護
        logger.warning(
            "llm_call_log 寫入失敗（已忽略，避免拖垮主流程）: %s / payload=%s",
            exc,
            {k: v for k, v in (payload or {}).items() if k != "error"},
        )


async def aggregate_cost(
    range_key: str, group_by: str, db: AsyncSession
) -> dict:
    """彙總 actual / baseline 成本，依 range_key + group_by 切片。

    回傳格式對齊 docs/Arch §5-5：
    ``{ total_actual, total_baseline, saved, saved_pct, breakdown: [...] }``

    若 range_key / group_by 不在 whitelist：回空結構（不 raise）。
    """
    where_clause = _RANGE_WHERE.get(range_key)
    group_col = _GROUP_COLUMN.get(group_by)
    empty: dict[str, object] = {
        "total_actual": Decimal("0"),
        "total_baseline": Decimal("0"),
        "saved": Decimal("0"),
        "saved_pct": 0.0,
        "breakdown": [],
    }
    if where_clause is None or group_col is None:
        return empty

    # 1) 取總計
    total_sql = text(
        f"""
        SELECT COALESCE(SUM(actual_cost_usd), 0)   AS total_actual,
               COALESCE(SUM(baseline_cost_usd), 0) AS total_baseline
        FROM llm_call_log
        WHERE {where_clause}
        """
    )
    try:
        total_row = (await db.execute(total_sql)).mappings().first()
    except Exception as exc:
        logger.warning("aggregate_cost 總計查詢失敗: %s", exc)
        return empty

    total_actual = Decimal(str(total_row["total_actual"] or 0))
    total_baseline = Decimal(str(total_row["total_baseline"] or 0))
    saved = total_baseline - total_actual
    saved_pct = (
        float(saved / total_baseline * 100)
        if total_baseline > 0
        else 0.0
    )

    # 2) 取 breakdown
    breakdown_sql = text(
        f"""
        SELECT {group_col}                              AS key,
               COALESCE(SUM(actual_cost_usd), 0)        AS actual,
               COALESCE(SUM(baseline_cost_usd), 0)      AS baseline,
               COUNT(*)                                  AS calls
        FROM llm_call_log
        WHERE {where_clause}
        GROUP BY {group_col}
        ORDER BY actual DESC
        """
    )
    try:
        rows = (await db.execute(breakdown_sql)).mappings().all()
    except Exception as exc:
        logger.warning("aggregate_cost breakdown 查詢失敗: %s", exc)
        rows = []

    breakdown: list[dict] = []
    for row in rows:
        key_val = row["key"]
        breakdown.append(
            {
                "key": str(key_val) if key_val is not None else "(null)",
                "actual": Decimal(str(row["actual"] or 0)),
                "baseline": Decimal(str(row["baseline"] or 0)),
                "calls": int(row["calls"] or 0),
            }
        )

    return {
        "total_actual": total_actual,
        "total_baseline": total_baseline,
        "saved": saved,
        "saved_pct": round(saved_pct, 2),
        "breakdown": breakdown,
    }
