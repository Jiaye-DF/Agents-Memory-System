"""一次性搬遷腳本：把 disk 上的檔案內容直接 cp 到 S3, 並把 DB storage_key 換為新 S3 key。

用法::

    python -m scripts.migrate_storage_to_s3 --dry-run
    python -m scripts.migrate_storage_to_s3
    python -m scripts.migrate_storage_to_s3 --domain skills,scripts --limit 10
    docker compose exec backend python -m scripts.migrate_storage_to_s3 --dry-run

設計重點：
- Idempotent：`storage_key` 不以 ``data/`` 開頭視為已遷移, 自動跳過
- 三 domain 皆「直接 cp」（不解壓 / 不重打包）
- Skill / Script mime = ``application/zip``；Attachment mime = ``row.file_type``
- Chat Attachment 的 S3 filename 使用 ``row.file_name``（原始檔名）, 不是 disk 上的 ``{uuid}{ext}``
- failed 寫入當前工作目錄 ``failed_uids.txt``（覆蓋）, 單筆失敗不影響其他筆
"""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.chat_attachment import ChatAttachment
from app.models.script import Script
from app.models.skill import Skill
from app.storage import s3_storage

DOMAIN_CHOICES = ("skills", "scripts", "attachments")

DOMAIN_CONFIG = {
    "skills": {
        "model": Skill,
        "uid_attr": "skill_uid",
        "mime": "application/zip",
        "use_original_filename": False,
    },
    "scripts": {
        "model": Script,
        "uid_attr": "script_uid",
        "mime": "application/zip",
        "use_original_filename": False,
    },
    "attachments": {
        "model": ChatAttachment,
        "uid_attr": "chat_attachment_uid",
        "mime": None,
        "use_original_filename": True,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="搬遷 disk 上既有檔案到 S3, 並 UPDATE DB storage_key"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列印, 不打 S3 / 不 UPDATE DB",
    )
    parser.add_argument(
        "--domain",
        default=",".join(DOMAIN_CHOICES),
        help=f"逗號分隔, 預設 {','.join(DOMAIN_CHOICES)}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="每 domain 上限筆數（debug 用）, 預設無限",
    )
    return parser.parse_args()


def _basename_for_domain(domain: str, row) -> str:
    if DOMAIN_CONFIG[domain]["use_original_filename"]:
        return row.file_name
    return Path(row.storage_key).name


def _mime_for_domain(domain: str, row) -> str:
    mime = DOMAIN_CONFIG[domain]["mime"]
    if mime is not None:
        return mime
    return row.file_type


async def _migrate_domain(
    domain: str,
    dry_run: bool,
    limit: int | None,
    summary: dict,
    failed: list,
) -> None:
    cfg = DOMAIN_CONFIG[domain]
    model = cfg["model"]
    uid_attr = cfg["uid_attr"]

    counters = {"ok": 0, "skip": 0, "fail": 0}
    summary[domain] = counters

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(model))
        rows = result.scalars().all()
        if limit is not None:
            rows = rows[:limit]

        for row in rows:
            uid = getattr(row, uid_attr)
            uid_str = str(uid)

            if not row.storage_key.startswith("data/"):
                counters["skip"] += 1
                print(f"[SKIP] {domain[:-1]} {uid_str} (已遷移)")
                continue

            disk_path = Path(row.storage_key)
            if not disk_path.exists():
                counters["fail"] += 1
                reason = "檔案不存在"
                failed.append((domain, uid_str, reason))
                print(f"[FAIL] {domain[:-1]} {uid_str}: {reason}")
                continue

            try:
                content = disk_path.read_bytes()
                filename = _basename_for_domain(domain, row)
                new_key = s3_storage.build_key(domain, uid, filename)
                mime = _mime_for_domain(domain, row)

                if not dry_run:
                    await s3_storage.put_object(new_key, content, mime)
                    if row.is_deleted:
                        await s3_storage.mark_deleted(new_key)
                    row.storage_key = new_key
                    await session.commit()

                counters["ok"] += 1
                print(f"[OK] {domain[:-1]} {uid_str} → {new_key}")
            except Exception as exc:
                if not dry_run:
                    await session.rollback()
                counters["fail"] += 1
                reason = f"{type(exc).__name__}: {exc}"
                failed.append((domain, uid_str, reason))
                print(f"[FAIL] {domain[:-1]} {uid_str}: {reason}")


def _print_summary(summary: dict) -> None:
    print("\n===== 搬遷彙總 =====")
    total = {"ok": 0, "skip": 0, "fail": 0}
    for domain, counters in summary.items():
        print(
            f"{domain:>12s}: OK={counters['ok']}  "
            f"SKIP={counters['skip']}  FAIL={counters['fail']}"
        )
        for k in total:
            total[k] += counters[k]
    print(
        f"{'TOTAL':>12s}: OK={total['ok']}  "
        f"SKIP={total['skip']}  FAIL={total['fail']}"
    )


def _write_failed(failed: list) -> None:
    out = Path("failed_uids.txt")
    with out.open("w", encoding="utf-8") as f:
        for domain, uid, reason in failed:
            f.write(f"{domain}\t{uid}\t{reason}\n")
    print(f"\nfailed_uids.txt 已寫入（{len(failed)} 筆）→ {out.resolve()}")


async def main() -> None:
    args = parse_args()

    raw_domains = [d.strip() for d in args.domain.split(",") if d.strip()]
    for d in raw_domains:
        if d not in DOMAIN_CHOICES:
            raise SystemExit(
                f"未知 domain: {d}（可選: {','.join(DOMAIN_CHOICES)}）"
            )

    print(
        f"== migrate_storage_to_s3 == "
        f"dry_run={args.dry_run} domains={raw_domains} limit={args.limit}"
    )

    summary: dict = {}
    failed: list = []

    for domain in raw_domains:
        print(f"\n--- domain: {domain} ---")
        await _migrate_domain(domain, args.dry_run, args.limit, summary, failed)

    _print_summary(summary)
    _write_failed(failed)


if __name__ == "__main__":
    asyncio.run(main())
