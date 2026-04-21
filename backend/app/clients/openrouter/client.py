import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.chat.memory_schemas import MemoryExtractResult

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# Anthropic 的 structured output 不支援 maxItems / maxLength，
# 故 schema 只宣告型別；數量與長度上限在 prompt 指示並於 parse 後強制截斷
MEMORY_EXTRACT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
        },
        "entities": {
            "type": "array",
            "items": {"type": "string"},
        },
        "topic": {"type": "string"},
        "is_actionable": {"type": "boolean"},
    },
    "required": ["keywords", "entities", "topic", "is_actionable"],
    "additionalProperties": False,
}

MEMORY_MAX_KEYWORDS = 20
MEMORY_MAX_ENTITIES = 20
MEMORY_MAX_TOPIC_LEN = 200

MEMORY_EXTRACT_SYSTEM_PROMPT = (
    "你是對話記憶抽取器。請從以下對話片段中擷取關鍵資訊，"
    "並以嚴格的 JSON 物件回覆，欄位為："
    "keywords（重點關鍵字，最多 20 個）、"
    "entities（人名 / 組織 / 地點 / 專有名詞，最多 20 個）、"
    "topic（主題摘要，最多 200 字）、"
    "is_actionable（是否包含可持續追蹤的資訊，true/false）。"
    "不要加任何額外文字或 markdown。"
)


async def fetch_model_ids() -> set[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPENROUTER_MODELS_URL)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("OpenRouter 模型清單取得失敗: %s", exc)
        raise AppError(
            detail="無法連線至 OpenRouter 驗證模型，請稍後再試",
            response_code=503,
            status_code=503,
        ) from exc

    data = payload.get("data") or []
    return {
        item["id"].lower()
        for item in data
        if isinstance(item.get("id"), str)
    }


async def stream_chat_completion(
    messages: list[dict],
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict]:
    """
    呼叫 OpenRouter Chat Completions 的 SSE streaming 端點，逐個 yield chunk。
    最後一個 chunk 可能帶 usage 資訊。
    """
    if not settings.OPENROUTER_API_KEY:
        raise AppError(
            detail="OPENROUTER_API_KEY 未設定，無法呼叫對話 API",
            response_code=500,
            status_code=500,
        )

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
        "X-Title": settings.OPENROUTER_APP_TITLE,
    }

    body: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", OPENROUTER_CHAT_URL, headers=headers, json=body
            ) as resp:
                if resp.status_code >= 400:
                    err_text = await resp.aread()
                    logger.warning(
                        "OpenRouter streaming 回應錯誤 %s: %s",
                        resp.status_code,
                        err_text[:500],
                    )
                    raise AppError(
                        detail=f"OpenRouter 呼叫失敗（HTTP {resp.status_code}）",
                        response_code=502,
                        status_code=502,
                    )

                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.debug("略過無法解析的 SSE 行: %s", payload[:120])
                        continue
                    yield chunk
    except AppError:
        raise
    except httpx.HTTPError as exc:
        logger.warning("OpenRouter streaming 連線失敗: %s", exc)
        raise AppError(
            detail="無法連線至 OpenRouter，請稍後再試",
            response_code=502,
            status_code=502,
        ) from exc


async def embed(text: str) -> list[float]:
    """
    呼叫 OpenRouter embeddings 端點，將文字轉為 1536 維向量。
    統一使用 OpenRouter 管理 key，避免多來源憑證分散。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise AppError(
            detail="embedding 輸入為空", response_code=400, status_code=400
        )

    if not settings.OPENROUTER_API_KEY:
        raise AppError(
            detail="OPENROUTER_API_KEY 未設定，無法呼叫 embedding API",
            response_code=500,
            status_code=500,
        )

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
        "X-Title": settings.OPENROUTER_APP_TITLE,
    }
    body = {"model": EMBEDDING_MODEL, "input": cleaned}
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                OPENROUTER_EMBEDDINGS_URL, headers=headers, json=body
            )
            if resp.status_code >= 400:
                logger.warning(
                    "OpenRouter embedding 回應錯誤 %s: %s",
                    resp.status_code,
                    resp.text[:500],
                )
                raise AppError(
                    detail=f"embedding 呼叫失敗（HTTP {resp.status_code}）",
                    response_code=502,
                    status_code=502,
                )
            payload = resp.json()
    except AppError:
        raise
    except httpx.HTTPError as exc:
        logger.warning("OpenRouter embedding 連線失敗: %s", exc)
        raise AppError(
            detail="無法連線至 OpenRouter（embedding）",
            response_code=502,
            status_code=502,
        ) from exc

    data = payload.get("data") or []
    if not data or not isinstance(data[0], dict):
        raise AppError(
            detail="embedding 回應為空",
            response_code=502,
            status_code=502,
        )
    vector = data[0].get("embedding")
    if not isinstance(vector, list):
        raise AppError(
            detail="embedding 回應格式異常",
            response_code=502,
            status_code=502,
        )
    return [float(v) for v in vector]


async def extract_memory(
    messages: list[dict], model: str
) -> MemoryExtractResult:
    """
    呼叫 OpenRouter 小模型，以 JSON schema 結構化輸出抽取記憶欄位。
    失敗直接拋 AppError 由呼叫端決定重試 / DLQ。
    """
    if not settings.OPENROUTER_API_KEY:
        raise AppError(
            detail="OPENROUTER_API_KEY 未設定，無法呼叫記憶抽取 API",
            response_code=500,
            status_code=500,
        )

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
        "X-Title": settings.OPENROUTER_APP_TITLE,
    }

    payload_messages: list[dict] = [
        {"role": "system", "content": MEMORY_EXTRACT_SYSTEM_PROMPT},
        *messages,
    ]

    body: dict = {
        "model": model,
        "messages": payload_messages,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "MemoryExtractResult",
                "strict": True,
                "schema": MEMORY_EXTRACT_JSON_SCHEMA,
            },
        },
    }

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                OPENROUTER_CHAT_URL, headers=headers, json=body
            )
            if resp.status_code >= 400:
                logger.warning(
                    "OpenRouter extract_memory 回應錯誤 %s: %s",
                    resp.status_code,
                    resp.text[:500],
                )
                raise AppError(
                    detail=f"記憶抽取 API 失敗（HTTP {resp.status_code}）",
                    response_code=502,
                    status_code=502,
                )
            payload = resp.json()
    except AppError:
        raise
    except httpx.HTTPError as exc:
        logger.warning("OpenRouter extract_memory 連線失敗: %s", exc)
        raise AppError(
            detail="無法連線至 OpenRouter（記憶抽取）",
            response_code=502,
            status_code=502,
        ) from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("OpenRouter extract_memory 回應格式異常: %s", payload)
        raise AppError(
            detail="記憶抽取回應格式異常",
            response_code=502,
            status_code=502,
        ) from exc

    try:
        data = json.loads(content) if isinstance(content, str) else content
        # 部分供應商（如 Anthropic）不支援 schema 層級 maxItems/maxLength，
        # 於此強制截斷，確保不超過 Pydantic model 的 max_length 限制
        if isinstance(data, dict):
            if isinstance(data.get("keywords"), list):
                data["keywords"] = data["keywords"][:MEMORY_MAX_KEYWORDS]
            if isinstance(data.get("entities"), list):
                data["entities"] = data["entities"][:MEMORY_MAX_ENTITIES]
            if isinstance(data.get("topic"), str):
                data["topic"] = data["topic"][:MEMORY_MAX_TOPIC_LEN]
        return MemoryExtractResult.model_validate(data)
    except Exception as exc:
        logger.warning(
            "OpenRouter extract_memory JSON 解析失敗: %s / 原文: %s",
            exc,
            str(content)[:500],
        )
        raise AppError(
            detail="記憶抽取 JSON 解析失敗",
            response_code=502,
            status_code=502,
        ) from exc
