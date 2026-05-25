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
