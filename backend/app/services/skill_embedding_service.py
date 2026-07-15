"""Skill Embedding 生成服務（v1.6.2 多向量 1:N）。

責任：
- 依 name / description / ZIP 內 .md / .txt 內容切成三段文字，各自獨立 embedding
- 逐段呼叫 `llm_metering.call_llm_metered(PURPOSE_EMBEDDING)` 產生向量，
  經 `skill_embedding_repository.replace_for_skill` 同 transaction 全量替換
- 失敗只 log warning，不 raise（不擋 upload / update 主流程）；任一段 embed 失敗
  即整批放棄，不做半套替換
"""

from __future__ import annotations

import io
import logging
import zipfile

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill
from app.repositories import skill_embedding_repository
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


def _extract_zip_text(zip_bytes: bytes | None, max_chars: int) -> str:
    """解出 ZIP 內 .md / .txt 文字（截 max_chars）；ZIP 不可用或無內容回空字串。"""
    if zip_bytes is None:
        return ""

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
        return ""

    return "\n\n".join(parts)[:max_chars]


def build_embedding_texts(
    name: str,
    description: str,
    zip_bytes: bytes | None,
    max_chars: int,
) -> dict[str, str]:
    """切出 name / description / content 三段文字；空段不出該鍵。"""
    texts: dict[str, str] = {}
    if name:
        texts["name"] = name
    if description:
        texts["description"] = description
    content = _extract_zip_text(zip_bytes, max_chars)
    if content:
        texts["content"] = content
    return texts


async def update_embedding(
    skill: Skill, zip_bytes: bytes | None, db: AsyncSession
) -> None:
    """產生各段向量並全量替換該 skill 的 skill_embedding rows；失敗只 log warning，絕不 raise。"""
    try:
        max_chars = await system_setting_service.get_int(
            "skill.rag.embed_content_max_chars",
            DEFAULT_EMBED_CONTENT_MAX_CHARS,
            db,
        )
        texts = build_embedding_texts(
            skill.name, skill.description, zip_bytes, max_chars
        )
        if not texts:
            # 防呆：無任何可 embed 文字時不動既有 rows
            logger.warning(
                "skill embedding 無可用文字, 略過重建 skill_uid=%s", skill.skill_uid
            )
            return

        rows: list[tuple[str, list[float]]] = []
        for source_type, segment_text in texts.items():
            vector = await llm_metering.call_llm_metered(
                purpose=llm_metering.PURPOSE_EMBEDDING,
                user_uid=str(skill.owner_user_uid),
                text=segment_text,
            )
            rows.append((source_type, vector))

        await skill_embedding_repository.replace_for_skill(
            str(skill.skill_uid), rows, db
        )
    except Exception as exc:
        # 任一段 embed 失敗即整批放棄（不做半套替換）, 只 warning 不擋主流程
        logger.warning(
            "skill embedding 更新失敗（整批放棄, 不做部分替換）skill_uid=%s: %s",
            skill.skill_uid,
            exc,
        )
