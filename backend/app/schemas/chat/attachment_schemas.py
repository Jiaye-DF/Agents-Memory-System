from __future__ import annotations

from pydantic import BaseModel


class ChatAttachmentResponse(BaseModel):
    """單一附件對外表示（list 摘要 / 關聯資源回應均使用）。"""

    chat_attachment_uid: str
    chat_session_uid: str
    file_name: str
    file_type: str
    file_size: int
    created_at: str


class ChatAttachmentListData(BaseModel):
    items: list[ChatAttachmentResponse]
