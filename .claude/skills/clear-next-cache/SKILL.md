---
name: clear-next-cache
description: 清除前端 Next.js / Turbopack 的 build cache（`frontend/.next` 與 `frontend/tsconfig.tsbuildinfo`），用於修復 Turbopack 404、stale routing manifest、HMR 異常、舊 type cache 等情境。觸發時機：使用者輸入 `/clear-next-cache` 或要求「清前端 cache」、「清 Next.js cache」、「清 .next」、「修 Turbopack 404」、「修前端 stale build」、「重建前端 build」。
---

# clear-next-cache

清除前端 Next.js / Turbopack cache 並（必要時）重啟前端 container。

## 何時使用此 skill

對應 [docs/Tasks/v1.1/fixed.md §5](../../../docs/Tasks/v1.1/fixed.md) 場景 — Turbopack 的 routing manifest 在多輪檔案 edit + container restart 後沒正確更新，導致動態路由 404。也適用於：

- `/path/[uid]/edit` 等動態路由 404，但 `page.tsx` 明確存在
- HMR 不更新、頁面顯示舊內容
- TS server 殘留舊 type，編譯報錯但程式碼正確
- `next build` 後行為與預期不符

## 執行方式

直接以 `Bash` 工具執行此 skill 目錄內的腳本：

```bash
bash .claude/skills/clear-next-cache/clear-cache.sh
```

腳本會自動：

1. 偵測 frontend container（`docker compose ps`）是否在跑
2. **container 在跑** → `docker compose stop frontend`（避免 next dev 還活著時 `.next` 被刪 → ENOENT log race）→ host 端 `rm -rf` → `docker compose start frontend`
3. **container 沒跑** → 直接 `rm -rf frontend/.next frontend/tsconfig.tsbuildinfo`
4. 一律從 host 端清檔案（`./frontend` 是 bind mount，host 與 container 同視野）
5. 回報處理摘要

## 重要原則

- **僅清 build cache，不動 `node_modules`**：`node_modules` 如需重裝請走 `npm install` 或 docker run（見此專案 frontend 的 anonymous volume 設計）
- **不需詢問使用者確認**：cache 清除是無破壞性操作，可重新生成
- 腳本須在 repo 根目錄執行；若 cwd 不正確，腳本會自動向上找含 `frontend/` 的目錄
- 執行後請提示使用者：等 `next dev` 重新編譯（首次編譯會稍慢）即可恢復