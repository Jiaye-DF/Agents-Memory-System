"""Admin 記憶 pipeline trace 相關 schema（v1.3.1）。

對應 endpoint：``GET /api/v1/admin/debug/memory/sessions/{session_uid}``
資料來源：Redis stream ``memory:trace:{session_uid}``（MAXLEN ~ 200, TTL 7 天）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryTraceItem(BaseModel):
    """單一 trace 紀錄。"""

    ts: str | None = Field(
        None,
        description="事件時間（ISO 8601, Asia/Taipei UTC+8）；XADD 時取 server time",
    )
    step: str = Field(..., description="階段名稱（boot / enqueue / buffer_flush / prefilter / extract / embedding / write / image_describe / dlq）")
    outcome: str = Field(..., description="事件結果（ok / retry / all_skipped / pushed / push_failed / exception）")
    duration_ms: int | None = Field(
        None, description="該階段耗時（ms），僅 extract / embedding / image_describe 等有耗時階段才寫入"
    )
    message_uids: list[str] | None = Field(
        None, description="該階段涉及的 chat_message_uid 列表"
    )
    extra: dict[str, object] | None = Field(
        None, description="階段特有欄位（attempt / reason / count / error 等）"
    )


class MemoryTraceData(BaseModel):
    """``GET /api/v1/admin/debug/memory/sessions/{uid}`` 的 response data。"""

    session_uid: str = Field(..., description="查詢的 session uid")
    count: int = Field(..., description="trace 筆數")
    items: list[MemoryTraceItem] = Field(
        default_factory=list, description="按時間升序的 trace 列表（找不到時為空）"
    )
