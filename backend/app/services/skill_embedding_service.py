"""Skill Embedding 生成服務（v1.6.0）。

責任：
- 組 embedding 文字（name + description + ZIP 內 .md / .txt 檔案內容）
- 呼叫 `llm_metering.call_llm_metered(PURPOSE_EMBEDDING)` 產生向量並寫回 `skill.embedding`
- 失敗只 log warning，不 raise（不擋 upload / update 主流程）
"""

from __future__ import annotations

import io
import logging
import zipfile

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill
from app.repositories import skill_repository
from app.services import llm_metering, system_setting_service

logger = logging.getLogger(__name__)

DEFAULT_EMBED_CONTENT_MAX_CHARS = 8000

_TEXT_EXTENSIONS = (".md", ".txt")


def _sort_key(info: zipfile.ZipInfo) -> tuple[int, str]:
    """排序權重：SKILL.md → README.md → 其餘依路徑字典序（basename 不分大小寫）。"""
    basename = info.filename.rsplit("/", 1)[-1].lower()
    if basename == "skill.md":
        priority = 0
    elif basename == "readme.md":
        priority = 1
    else:
        priority = 2
    return (priority, info.filename)


def build_embedding_text(
    name: str,
    description: str,
    zip_bytes: bytes | None,
    max_chars: int,
) -> str:
    base = f"{name}\n\n{description}"
    if zip_bytes is None:
        return base

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            infos = [
                info
                for info in zf.infolist()
                if not info.is_dir()
                and info.filename.lower().endswith(_TEXT_EXTENSIONS)
            ]
            infos.sort(key=_sort_key)
            parts: list[str] = []
            for info in infos:
                try:
                    parts.append(zf.read(info.filename).decode("utf-8"))
                except Exception:
                    continue
    except zipfile.BadZipFile:
        return base

    content = "\n\n".join(parts)[:max_chars]
    if not content:
        return base
    return f"{base}\n\n{content}"


async def update_embedding(
    skill: Skill, zip_bytes: bytes | None, db: AsyncSession
) -> None:
    """產生並寫回 skill.embedding；失敗只 log warning，絕不 raise。"""
    try:
        max_chars = await system_setting_service.get_int(
            "skill.rag.embed_content_max_chars",
            DEFAULT_EMBED_CONTENT_MAX_CHARS,
            db,
        )
        embedding_text = build_embedding_text(
            skill.name, skill.description, zip_bytes, max_chars
        )
        vector = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_EMBEDDING,
            user_uid=str(skill.owner_user_uid),
            text=embedding_text,
        )
        await skill_repository.update_obj(skill, {"embedding": vector}, db)
    except Exception as exc:
        logger.warning(
            "skill embedding 更新失敗 skill_uid=%s: %s", skill.skill_uid, exc
        )
