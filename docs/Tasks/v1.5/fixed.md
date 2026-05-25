# v1.5 修正記錄

> 實作 v1.5.0「檔案儲存全面切換 S3」過程中，自驗階段陸續發現的規格漏項與基礎設施缺漏修正。

---

## 1. Phase 3 grep 漏掉兩處 disk IO 點 — memory_worker / chat_service  〔2026-05-25 13:35:03〕

**問題**：v1.5.0 Phase 3 規格只列出三個 service 為改名範圍（skill_service / script_service / chat_attachment_service），但 `.file_path` 屬性引用其實還散落在 worker 與其他 service。Wave 2 派遣 agent 雖然把屬性名稱全 grep 改成 `.storage_key`，但其中兩處實際上是把 model 屬性當作 disk 路徑直接 IO，需要連同 IO backend 一起換 S3。改名動作完成、但底層 IO 沒切，導致：

```python
# backend/app/workers/memory_worker.py (改名後仍寫成)
path = Path(a.storage_key)        # storage_key 已是 S3 key，不是 disk path
if not path.exists():
    continue
raw = path.read_bytes()           # 必爆 FileNotFoundError
```

```python
# backend/app/services/chat_service.py:_skill_prompt_text (改名後仍寫成)
zip_path = skill.storage_key
if not zip_path or not Path(zip_path).exists():   # 同上問題
    return header
with zipfile.ZipFile(zip_path, "r") as zf:        # zip 開不了
```

根因：tasks-v1.5.0.md §3-2 的影響檔案清單只列了三個 service，未涵蓋 `workers/memory_worker.py` 與 `services/chat_service.py`。Agent 嚴格按規格範圍處理，雖然替屬性名改完了，但屬性的「實際用途是 disk IO」這個面向沒納入檢查，造成兩條 silent leak。Wave 3 的 4-8「集中進入點驗證」只 grep 三個 service 內的 `.read_bytes()` / `.write_bytes()`，沒擴及 worker 層，所以這兩條也躲過 service 層的驗證。最後在我做最終 grep 巡檢時才掃出來。

**修正**：

1. `memory_worker.py`：`Path(a.storage_key).read_bytes()` → `await s3_storage.get_object(a.storage_key)`；外層 `try` block 既有的 `except Exception` 能吃到 `ClientError`，所以無須另外處理 404；連帶移除唯一的 `from pathlib import Path` import。
2. `chat_service.py:_skill_prompt_text`：把「`Path(zip_path).exists()` 守門 + `zipfile.ZipFile(zip_path)`」改成「`await s3_storage.get_object(skill.storage_key)` 拿 bytes + `zipfile.ZipFile(io.BytesIO(zip_bytes))` 解析」；新增 `from botocore.exceptions import ClientError` 對 `NoSuchKey` 走「回傳 header 不附 md 內容」的 graceful 退化；連帶移除 `from pathlib import Path`。

**影響檔案**：

- `backend/app/workers/memory_worker.py`
- `backend/app/services/chat_service.py`

**驗證方式**：本地實跑 `python -m scripts.migrate_storage_to_s3` 把既有 skill 搬上 S3 後，呼叫 `skill_service.get_file_tree()` 與 S3 read round-trip 皆通；`grep -nE "Path\(|\.read_bytes|\.write_bytes" backend/app/` 在 service / worker 層應該為零命中（剩下唯一一處是 `services/llm_pricing.py:38` 讀 codebase 內 `model_prices.yaml` 設定檔，與 storage 無關，正確保留）。

**殘留 / 後續**：日後 task spec 規範變更欄位語意時，影響範圍清單應同步涵蓋 worker 層、跨 service 引用、以及任何把該欄位視為「path / URL / 外部資源 handle」直接消費的程式碼。建議下一次同類重構的 task 模板加註：「grep `\.<old_name>` 必須 union grep `<old_name>\b` 與 worker / scripts / repositories / schemas 全域，且需逐筆判斷『改名稱』還是『連 IO 一起換』」。

---

## 2. docker-compose.dev.yml backend 未掛載 AWS 環境變數  〔2026-05-25 13:35:03〕

**問題**：v1.5.0 把 4 個 AWS 變數加進 `.env.example` / `.env` / `config.py.Settings`，但忘了在 `docker-compose.dev.yml` backend service 的 `environment:` 區段做 host → container 的 passthrough。Container 內 `settings.AWS_ACCESS_KEY_ID` / `S3_BUCKET` 等永遠是空字串，雖然啟動時 lazy init 不會炸，但第一次 S3 呼叫會立刻 raise：

```text
RuntimeError: S3 憑證或 bucket 未設定
```

根因：tasks-v1.5.0.md §0-3 把「環境變數補齊」勾掉時是指 `.env*` 檔案層級，沒延伸到「container 是否真的吃得到」這層。compose dev.yml backend 的 `environment:` 是 explicit passthrough（不是 `env_file:` 自動帶入），新增 settings 鍵 → 必須手動補一份對應的 `${KEY:-}` 映射。本專案 compose 一向採用 explicit passthrough 風格（便於明確控管哪些變數會跨入 container），但這也意味著新增 settings 都要做這道手續，而 task spec 沒列。

**修正**：`docker-compose.dev.yml` 的 backend `environment:` 區段補 4 行：

```yaml
AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:-}
AWS_REGION: ${AWS_REGION:-ap-northeast-1}
S3_BUCKET: ${S3_BUCKET:-}
```

**影響檔案**：

- `docker-compose.dev.yml`

**驗證方式**：`docker compose -f docker-compose.dev.yml exec -T backend python -c "from app.core.config import settings; print(settings.S3_BUCKET)"` 應該印出 `agents-platform-dev-datas`（或當下 `.env` 的值），不再是空字串。

**殘留 / 後續**：正式環境部署在 Coolify，env passthrough 由 Coolify 介面而非 compose 控制，須使用者自行確認 v1.5 部署前已在 Coolify 的 Environment Variables 頁面新增上述 4 鍵（test / prod 兩組獨立 IAM User + bucket）。

— **更正**：本段「殘留 / 後續」當時的判斷誤——Coolify 雖然在 UI 設定 env，但 deploy 時仍是用 `docker-compose.yml` 這個 base compose 檔，env 必須透過 compose 的 `${KEY}` 映射才會跨入 container，並不是 Coolify 直接 inject。後續實際在 prod backend container 內跑 `python -m scripts.migrate_storage_to_s3` 時依然炸 `S3 憑證或 bucket 未設定`，由 §3 接續修復。

---

## 3. docker-compose.yml（正式環境）未掛載 AWS 環境變數 + migrate_storage_to_s3 fail 後 MissingGreenlet  〔2026-05-25 16:33:08〕

**問題**：兩個串連的問題：

**(a)** v1.5.0 在 §2 已補了 `docker-compose.dev.yml` 的 AWS env passthrough，但**正式環境用的 `docker-compose.yml`** 沒同步補上。Coolify 部署底層仍是用 `docker-compose.yml`，env 必須透過 compose 的 `${KEY}` explicit 映射才會跨入 container（§2「殘留 / 後續」當時誤判 Coolify 會繞過 compose）。實際在 prod backend container 內跑 migration script 噴：

```text
[FAIL] skill 88c98db8-0287-4bff-b581-0e6a6dd9e910: RuntimeError: S3 憑證或 bucket 未設定
```

**(b)** Migration script `_migrate_domain` 在單筆 fail → `await session.rollback()` 後，下一輪迴圈 `for row in rows:` 第一行 `uid = getattr(row, uid_attr)` 觸發了 SQLAlchemy 對該 row 的 lazy load（rollback 會把 session 內 attached objects 都 expire），但因現在不在 greenlet 上下文，直接炸：

```text
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.
```

導致 script 整個 abort，連 `failed_uids.txt` 與彙總都沒寫，第 1 筆失敗就連帶把後面所有筆遺失追蹤訊息。

根因：
- (a) §2 修 compose 時只盯著 dev 檔，沒檢查 prod 檔；同時對 Coolify 的 deploy 機制誤判
- (b) script 採用單一 session + 全部 row 都 attached 的設計，rollback 的副作用未隔離；應該讓 fetched rows 一律與 session 解綁，更新時用 `merge()` 把單筆 reattach、commit 後立刻 `expunge`，這樣任何一筆的 rollback 不會污染其他 row

**修正**：

1. `docker-compose.yml` backend service `environment:` 區段補 4 行（與 `docker-compose.dev.yml` 對齊）：

```yaml
AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:-}
AWS_REGION: ${AWS_REGION:-ap-northeast-1}
S3_BUCKET: ${S3_BUCKET:-}
```

2. `backend/scripts/migrate_storage_to_s3.py:_migrate_domain`：拿到 `rows = list(result.scalars().all())` 後立刻 `session.expunge_all()` 讓 rows 跟 session 解綁；更新單筆時用 `merged = await session.merge(row)` reattach、寫入 `merged.storage_key = new_key`、`await session.commit()`、立刻 `session.expunge(merged)`。這樣任何一筆失敗的 rollback 不會擴散到其他 row 的屬性存取。

**影響檔案**：

- `docker-compose.yml`
- `backend/scripts/migrate_storage_to_s3.py`

**驗證方式**：
- (a) 重 deploy 後在 backend container 內 `python -c "from app.core.config import settings; print(settings.S3_BUCKET)"` 應印出 bucket 名（非空字串）。
- (b) 在 dev 內故意造一筆 `storage_key` 不存在的記錄 + 一筆正常記錄，跑 `python -m scripts.migrate_storage_to_s3`，預期：失敗筆走 [FAIL] 寫進 `failed_uids.txt`、正常筆走 [OK] 完成，**整個 script 跑完印出彙總**，不再 traceback。

**殘留 / 後續**：
- 之後 task spec 涉及新增 settings 鍵時，影響範圍清單應同步要求檢查 `docker-compose.yml` **與** `docker-compose.dev.yml` 兩個 compose 的 `environment:` 區段（本專案 explicit passthrough 風格）。
- §2 對 Coolify deploy 機制的誤判已在本條更正，未來其他「正式環境 env 設定」需求請以 `docker-compose.yml` 為 source of truth，Coolify UI 設定的 `.env` 必須透過 compose 映射才會跨入 container。
