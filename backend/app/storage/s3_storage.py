"""S3 物件儲存共用 module。

提供 5 個對外函式：
- ``build_key(domain, entity_uid, filename)``：組出 S3 object key
- ``put_object(key, body, content_type)``：上傳 bytes
- ``get_object(key)``：下載為 bytes
- ``mark_deleted(key)``：軟刪除（加 S3 tag）
- ``exists(key)``：判斷 object 是否存在

Key 命名規則：``{domain}/{entity_uid}/{filename}``，domain ∈ ``{skills, scripts, attachments}``。

軟刪除採用 S3 object tagging：單一 tag ``status=deleted``（無括號；S3 tag value
字元集禁用括號）。實際物件不立即刪除，後續由 bucket lifecycle 處理。

Client 採 lazy init：第一次呼叫對外函式時才建立 boto3 client；缺 access key /
secret / bucket 任一者 → ``RuntimeError``。
"""

import asyncio
import re
import uuid
from typing import Literal

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

_client = None

# 路徑字元（含目錄跳脫）替換為底線
_PATH_CHAR_RE = re.compile(r"\.\.|[\\/]")
# ASCII 控制字元（含 DEL），不影響 Unicode 中文 / 內部空格
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def _get_client():
    global _client
    if _client is not None:
        return _client
    if (
        not settings.AWS_ACCESS_KEY_ID
        or not settings.AWS_SECRET_ACCESS_KEY
        or not settings.S3_BUCKET
    ):
        raise RuntimeError("S3 憑證或 bucket 未設定")
    _client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    return _client


def _sanitize_filename(filename: str) -> str:
    cleaned = _PATH_CHAR_RE.sub("_", filename)
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    if not cleaned:
        raise ValueError("檔名為空或全為非法字元")
    return cleaned


def build_key(
    domain: Literal["skills", "scripts", "attachments"],
    entity_uid: str | uuid.UUID,
    filename: str,
) -> str:
    safe = _sanitize_filename(filename)
    return f"{domain}/{entity_uid}/{safe}"


async def put_object(key: str, body: bytes, content_type: str) -> None:
    await asyncio.to_thread(
        _get_client().put_object,
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
    )


async def get_object(key: str) -> bytes:
    resp = await asyncio.to_thread(
        _get_client().get_object,
        Bucket=settings.S3_BUCKET,
        Key=key,
    )
    return await asyncio.to_thread(resp["Body"].read)


async def mark_deleted(key: str) -> None:
    await asyncio.to_thread(
        _get_client().put_object_tagging,
        Bucket=settings.S3_BUCKET,
        Key=key,
        Tagging={"TagSet": [{"Key": "status", "Value": "deleted"}]},
    )


async def exists(key: str) -> bool:
    try:
        await asyncio.to_thread(
            _get_client().head_object,
            Bucket=settings.S3_BUCKET,
            Key=key,
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
