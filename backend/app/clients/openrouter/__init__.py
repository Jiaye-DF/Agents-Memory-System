"""OpenRouter client（內部 API）。

**集中進入點規範**（docs/Arch/01-observability-and-metrics.md §2-3）：

> 此模組對外暴露的 LLM 呼叫函式（``stream_chat_completion`` / ``extract_memory`` /
> ``embed`` / ``describe_image`` / ``generate_skill_suggestion``）為**內部 API**，
> 外部請呼叫 ``app.services.llm_metering.call_llm_metered`` /
> ``call_llm_metered_stream``。
>
> 任何繞過 metering wrapper 的呼叫 = 漏記 metrics = 成本 / 延遲統計失真，code review
> 必檢。本檔的 LLM 呼叫函式僅允許在 ``backend/app/services/llm_metering.py`` 內部
> 透過 ``from app.clients.openrouter import client as openrouter_client`` 使用。

工具型函式（``model_supports_vision`` / ``image_bytes_to_data_url`` /
``fetch_model_ids`` / ``EMBEDDING_MODEL`` / ``EMBEDDING_DIMENSIONS``）不涉
LLM 計費，不在集中進入點守則範圍內，可自由 import。
"""

from app.clients.openrouter.client import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    describe_image,
    embed,
    extract_memory,
    fetch_model_ids,
    image_bytes_to_data_url,
    model_supports_vision,
    generate_skill_suggestion,
    stream_chat_completion,
)

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_MODEL",
    "describe_image",
    "embed",
    "extract_memory",
    "fetch_model_ids",
    "image_bytes_to_data_url",
    "model_supports_vision",
    "generate_skill_suggestion",
    "stream_chat_completion",
]
