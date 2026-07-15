"""一次性回填腳本：為既有 Skill 產生多向量語意檢索 embedding（v1.6.2 部署後**必須**立即執行）。

用法::

    python -m scripts.backfill_skill_embedding --dry-run
    python -m scripts.backfill_skill_embedding
    python -m scripts.backfill_skill_embedding --limit 10
    docker compose exec backend python -m scripts.backfill_skill_embedding

設計重點：
- **v1.6.2（V59）已刪除 skill.embedding 舊欄位**, 舊向量隨欄位一併消失；部署後
  必須立即執行本腳本, 否則語意檢索回空
- 可重跑（idempotent）：只挑「``skill_embedding`` 無任何 rows 且 ``is_deleted = FALSE``」
  的 skill, 已回填者不重算
- 逐筆 get_object → update_embedding（內含逐段 embed + 全量替換）→ commit；
  單筆失敗跳過續跑
- S3 NoSuchKey（檔案遺失）→ zip 傳 ``None`` 退化為只用 name + description 建向量,
  不視為失敗（避免每次重跑都卡同一筆）, 但逐筆 log 會標示 [WARN]
- ``update_embedding`` 內部吞例外只 ``logger.warning``, 故以「該 skill 在
  ``skill_embedding`` 的 rows 數 > 0」判定成功 / 失敗
- 結尾統計總數 / 成功 / 失敗 + 失敗 uid 清單；有失敗 exit code = 1
  （範式 migrate_storage_to_s3 無 exit code 慣例, 此處為配合部署自動化補上）
"""

import argparse
import asyncio

from botocore.exceptions import ClientError
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.skill import Skill
from app.models.skill_embedding import SkillEmbedding
from app.services import skill_embedding_service
from app.storage import s3_storage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="回填既有 Skill 的多向量 embedding（只挑 skill_embedding 無 rows 者）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列印待回填清單（仍讀 S3 驗證檔案存在）, 不呼叫 embedding / 不寫 DB",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="上限筆數（debug 用）, 預設無限",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    print(f"== backfill_skill_embedding == dry_run={args.dry_run} limit={args.limit}")

    success = 0
    failed: list[tuple[str, str]] = []

    async with AsyncSessionLocal() as session:
        stmt = select(Skill).where(
            Skill.is_deleted == False,
            ~select(SkillEmbedding.pid)
            .where(SkillEmbedding.skill_uid == Skill.skill_uid)
            .exists(),
        )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        if args.limit is not None:
            rows = rows[: args.limit]
        total = len(rows)
        print(f"待回填 skill 共 {total} 筆")
        # 讓 rows 與 session 解綁；後續若單筆 rollback 不會 expire 其他 row 觸發 lazy load
        session.expunge_all()

        for i, row in enumerate(rows, 1):
            uid_str = str(row.skill_uid)
            try:
                zip_bytes: bytes | None = None
                try:
                    zip_bytes = await s3_storage.get_object(row.storage_key)
                except ClientError as exc:
                    if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                        # 檔案遺失 → 退化為只用 name + description, 不記失敗
                        print(
                            f"[WARN] {i}/{total} skill {uid_str}: "
                            f"S3 檔案不存在（{row.storage_key}）, 退化為 name + description"
                        )
                    else:
                        raise

                if args.dry_run:
                    print(
                        f"[DRY] {i}/{total} skill {uid_str} "
                        f"({row.name}) zip={'有' if zip_bytes else '無'}"
                    )
                    continue

                merged = await session.merge(row)
                await skill_embedding_service.update_embedding(
                    merged, zip_bytes, session
                )
                count_stmt = (
                    select(func.count())
                    .select_from(SkillEmbedding)
                    .where(SkillEmbedding.skill_uid == row.skill_uid)
                )
                rows_count = (await session.execute(count_stmt)).scalar_one()
                if rows_count == 0:
                    # update_embedding 內部失敗只 warning, 以無任何 rows 判定失敗
                    await session.rollback()
                    failed.append(
                        (uid_str, "update_embedding 失敗（skill_embedding 無 rows）")
                    )
                    print(f"[FAIL] {i}/{total} skill {uid_str}: skill_embedding 無 rows")
                    continue

                await session.commit()
                # commit 完立刻 detach，避免下一筆若 rollback 連帶 expire 這筆
                session.expunge(merged)
                success += 1
                print(f"[OK] {i}/{total} skill {uid_str} ({row.name}) rows={rows_count}")
            except Exception as exc:
                if not args.dry_run:
                    await session.rollback()
                reason = f"{type(exc).__name__}: {exc}"
                failed.append((uid_str, reason))
                print(f"[FAIL] {i}/{total} skill {uid_str}: {reason}")

    print("\n===== 回填彙總 =====")
    print(f"總數={total}  成功={success}  失敗={len(failed)}")
    if failed:
        print("失敗 uid 清單：")
        for uid_str, reason in failed:
            print(f"  {uid_str}\t{reason}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
