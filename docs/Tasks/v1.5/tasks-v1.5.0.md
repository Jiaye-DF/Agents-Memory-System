# v1.5.0 任務規格：檔案儲存全面切換 S3（取代本地 volume）

> **狀態：待實作**

> 前置：[propose-v1.5.0.md](propose-v1.5.0.md)
> 後續候選：S3 bucket lifecycle 規則、presigned URL 直連下載、volume mount 拔除

## 版本目標

一次性完整取代 volume 儲存方案；S3 物件形狀沿用既有 service 的打包策略（skill / script 上傳時打包為單一 .zip、chat attachment 為單檔），**不改變 upload / download API 對前端的契約**，只把儲存後端從 disk 換 S3。

本版部署完成後：

- 三個既有上傳領域全部走 S3
- DB 三表 `file_path` 改名為 `storage_key`，內容由 disk 路徑換為單一 S3 object key
- 既有 disk 上的所有檔案直接搬遷上 S3（檔案內容不動，僅 key 換新格式）
- `main.py` 拔除 volume 預建邏輯

### 範圍內

- 後端依賴：`boto3` + dev `moto[s3]`
- 後端設定：`config.py` 加 4 個 AWS 欄位
- 後端模組：`backend/app/storage/s3_storage.py`（5 函式底座）
- **Flyway V52**：三表欄位重命名 + COMMENT 更新
- **Model 重命名**：`file_path` → `storage_key`
- **三 service 切換**：upload / download / delete 的 disk IO 換成 S3
- **Router 層**：Skills / Scripts `FileResponse` → `Response(content=bytes)`
- **軟刪除整合**：delete entrypoints 多呼 `s3_storage.mark_deleted`
- **一次性搬遷腳本**：disk → S3，idempotent + `--dry-run`
- `main.py` `_ensure_upload_dirs()` 移除
- 單元測試 + 手動 smoke

### 範圍外

- docker-compose `backend-data:/app/data` volume mount **保留**（過渡期備援）
- S3 bucket lifecycle（自動歸檔 / 過期）
- Presigned URL 直連下載
- 改變 upload / download API 對前端的契約（不變）

---

## 前置現況

- **既有 Flyway 最大版本**：`V51__rename_owner_uid_to_owner_user_uid.sql`，本 task 起算 **V52**
- **既有檔案路徑欄位**：
  - [`models/skill.py:21`](../../../backend/app/models/skill.py) `file_path: String(500)`
  - [`models/script.py:22`](../../../backend/app/models/script.py) `file_path: String(500)`
  - [`models/chat_attachment.py:24`](../../../backend/app/models/chat_attachment.py) `file_path: Text`
- **既有 service IO 點**：
  - [`skill_service.py:205`](../../../backend/app/services/skill_service.py)（create write_bytes）、L355（download 回 file_path）、L326（delete）
  - [`script_service.py`](../../../backend/app/services/script_service.py)（create / L495 download / L486 soft_delete）
  - [`chat_attachment_service.py:145`](../../../backend/app/services/chat_attachment_service.py)（create write_bytes）、L203 / L268（read_bytes）
- **既有 router 對應**：
  - [`skills/router.py:138`](../../../backend/app/api/v1/skills/router.py) → `FileResponse(file_path, ...)`
  - [`scripts/router.py:166`](../../../backend/app/api/v1/scripts/router.py) → `FileResponse(...)`
  - [`chat/router.py:477`](../../../backend/app/api/v1/chat/router.py) → `StreamingResponse(io.BytesIO(data))`
- **既有 lifespan 鉤子**：[`main.py:27`](../../../backend/app/main.py) `_ensure_upload_dirs()`
- **既有 settings**：AWS 4 欄位**尚未**加入 `Settings` class（env 檔已就緒）
- **既無**：`boto3` 依賴、`backend/app/storage/` / `backend/scripts/` 目錄

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | DB 欄位命名 | `file_path` → `storage_key`（Flyway V52 三表同步）|
| 2 | `storage_key` 語意 | 三表皆為**單一完整 S3 object key**（非 prefix）|
| 3 | S3 物件形狀 | 沿用既有 service 打包策略：Skill / Script = 單一 .zip；Chat Attachment = 單檔（**對前端契約零變更**）|
| 4 | 既有資料處理 | 保留 + 搬遷；既有 disk 上的單一 .zip 直接 cp 到 S3, 內容不動 |
| 5 | Module 位置 | `backend/app/storage/s3_storage.py` |
| 6 | Module 函式 | 5 個：`build_key` / `put_object` / `get_object` / `mark_deleted` / `exists` |
| 7 | Client init 時機 | Lazy；缺憑證 → 第一次呼叫 raise `RuntimeError` |
| 8 | Key 命名規則 | `{domain}/{entity_uid}/{filename}`；domain ∈ `{skills, scripts, attachments}` |
| 9 | Filename 清理 | 移除 `\` / `/` / `..`（替換為 `_`）、過濾控制字元、保留 Unicode（含中文）與內部空格 |
| 10 | Soft-delete tag | **`status=deleted`**（無括號；S3 tag value 字元集禁用括號）|
| 11 | 同步 / 非同步 | boto3 sync API 一律包 `await asyncio.to_thread(...)` |
| 12 | Download 回傳格式 | Skills / Scripts 從 `FileResponse` 改 `Response(content=bytes)`；Chat Attachments 維持 `StreamingResponse(io.BytesIO(...))`, 來源換 S3 |
| 13 | Update 覆蓋策略 | Skills / Scripts 若 service 支援 update：直接覆蓋同 key（bucket versioning 自動留歷史）；filename 變動 → 新 key put + 舊 key `mark_deleted` |
| 14 | 部署順序 | Flyway V52 → backend 啟動 → 手動跑搬遷 → 驗證 → 完成；計入「計劃內 outage window」|
| 15 | volume mount 處置 | 本版**保留** `backend-data:/app/data`（搬遷腳本仍要讀, 穩定後下版本拔）|
| 16 | 不引入的依賴 | aioboto3、multipart upload（檔案 < 50 MB 不需要）|

---

## Phase 0：依賴與設定

### 0-1 後端依賴

- [x] [`pyproject.toml`](../../../backend/pyproject.toml) `dependencies` 加 `"boto3>=1.34"`
- [x] `[project.optional-dependencies].dev` 加 `"moto[s3]>=5.0"`

### 0-2 後端 settings

- [x] [`config.py`](../../../backend/app/core/config.py) `Settings` 加 4 欄位
  - `AWS_ACCESS_KEY_ID: str = ""`
  - `AWS_SECRET_ACCESS_KEY: str = ""`
  - `AWS_REGION: str = "ap-northeast-1"`
  - `S3_BUCKET: str = ""`
- [x] 不加 validator（空值合法）

### 0-3 環境變數

- [x] 4 個 env 檔已更新（前置作業完成）

---

## Phase 1：S3 共用 module

### 1-1 套件骨架

- [x] 新建 `backend/app/storage/__init__.py`
- [x] 新建 `backend/app/storage/s3_storage.py`

### 1-2 Client lazy init

- [x] 模組層 `_client = None`
- [x] `_get_client()`：首次呼叫建立, 後續複用；缺憑證 → raise `RuntimeError`

### 1-3 對外函式（5 個）

- [x] `build_key(domain: Literal["skills","scripts","attachments"], entity_uid: str | uuid.UUID, filename: str) -> str`
- [x] `_sanitize_filename(filename: str) -> str`（規則見決策 #9；結果為空 → `ValueError`）
- [x] `async put_object(key, body: bytes, content_type: str)` → boto3 put_object 包 to_thread
- [x] `async get_object(key) -> bytes` → response["Body"].read()
- [x] `async mark_deleted(key)` → put_object_tagging `[{"Key":"status","Value":"deleted"}]`
- [x] `async exists(key) -> bool` → head_object；ClientError 404 → False；其他 raise

### 1-4 Module docstring

- [x] 頂部 docstring 簡述：5 函式、key 命名規則、軟刪除 tag

---

## Phase 2：Flyway V52

### 2-1 Migration SQL

- [x] 新建 `migrations/sql/V52__rename_file_path_to_storage_key.sql`
  ```sql
  ALTER TABLE skill RENAME COLUMN file_path TO storage_key;
  ALTER TABLE script RENAME COLUMN file_path TO storage_key;
  ALTER TABLE chat_attachment RENAME COLUMN file_path TO storage_key;

  COMMENT ON COLUMN skill.storage_key IS 'S3 object key, 格式: skills/{skill_uid}/{filename}.zip';
  COMMENT ON COLUMN script.storage_key IS 'S3 object key, 格式: scripts/{script_uid}/{filename}.zip';
  COMMENT ON COLUMN chat_attachment.storage_key IS 'S3 object key, 格式: attachments/{chat_attachment_uid}/{filename}';
  ```
- [x] 僅改名稱與註解, 內容值不動（搬遷腳本後續會把 disk 路徑換成 S3 key）

---

## Phase 3：Model / Schema 重命名

### 3-1 Model

- [x] [`models/skill.py`](../../../backend/app/models/skill.py) `file_path` → `storage_key`
- [x] [`models/script.py`](../../../backend/app/models/script.py) `file_path` → `storage_key`
- [x] [`models/chat_attachment.py`](../../../backend/app/models/chat_attachment.py) `file_path` → `storage_key`

### 3-2 全專案 reference

- [x] grep `\.file_path` 在 `backend/app/`：把 model 屬性引用全改 `.storage_key`
  - 區分 local 變數 `file_path = ...`（不動）vs `obj.file_path`（要改）
- [x] grep `file_path` 在 schemas / repositories：同步改名

---

## Phase 4：三 service 切換

### 4-1 `skill_service.create_skill`

- [x] [L191-218](../../../backend/app/services/skill_service.py) 改寫
- [x] 保留既有 zip 打包邏輯（`is_single_zip` 判斷、`_build_zip(entries)`、`_check_zip_bomb`）
- [x] 把「寫 disk」段換成 S3：
  ```python
  # 既有：
  skill_dir = Path(settings.SKILLS_UPLOAD_DIR) / str(skill_uid)
  skill_dir.mkdir(parents=True, exist_ok=True)
  zip_path = skill_dir / f"{base}.zip"
  zip_path.write_bytes(zip_content)

  # 新：
  key = s3_storage.build_key("skills", skill_uid, f"{base}.zip")
  await s3_storage.put_object(key, zip_content, "application/zip")
  ```
- [x] `_check_zip_bomb(zip_path, max_size)`：改成讀 bytes 版本 `_check_zip_bomb_inmem(zip_content, max_size)`（從記憶體驗, 不再 round trip）—（已直接改 `_check_zip_bomb(zip_content, max_size)` 簽名為 in-memory 版，因 caller 僅 skill_service 兩處，無需另增 `_inmem` 函式）
- [x] DB 寫入：`"storage_key": key`（取代 `"file_path": str(zip_path)`）

### 4-2 `skill_service.download_skill`

- [x] [L355](../../../backend/app/services/skill_service.py) 改寫；介面回 `tuple[bytes, str]` = `(content, download_name)`
  ```python
  try:
      data = await s3_storage.get_object(skill.storage_key)
  except ClientError as e:
      if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
          raise AppError("檔案不存在, 請聯繫管理員", 404, 404)
      raise
  download_name = f"{os.path.splitext(skill.original_filename)[0]}.zip"
  return data, download_name
  ```

### 4-3 `skill_service.get_file_tree`

- [x] [L379](../../../backend/app/services/skill_service.py)：原本讀 disk zip 解析；改為先 `await s3_storage.get_object(skill.storage_key)` 取 bytes, 後續用 `zipfile.ZipFile(io.BytesIO(data))` 解析（其他邏輯不變）

### 4-4 `skill_service.delete_skill`

- [x] [L326](../../../backend/app/services/skill_service.py)
- [x] 設定 `is_deleted=True` 後追加：
  ```python
  try:
      await s3_storage.mark_deleted(skill.storage_key)
  except Exception:
      logger.warning("mark_deleted 失敗 key=%s", skill.storage_key, exc_info=True)
  ```
- [x] mark_deleted 失敗**不**回滾 DB（後續可手動補 / lifecycle 處理）

### 4-5 `script_service` 同步改寫

- [x] create / download / `soft_delete_script` 套同樣 pattern；domain 改 `"scripts"`

### 4-6 `chat_attachment_service.create_attachments`

- [x] [L138-167](../../../backend/app/services/chat_attachment_service.py) 改寫
  ```python
  for uf, content, ext, mime in staged:
      attachment_uid = uuid.uuid4()
      filename = uf.filename or f"{attachment_uid}{ext}"
      key = s3_storage.build_key("attachments", attachment_uid, filename)
      await s3_storage.put_object(key, content, mime)
      attachment = await chat_attachment_repository.create({
          ...
          "storage_key": key,
      }, db)
  ```
- [x] 不再用 `ym = ...; base_dir = Path(...) / ym` 邏輯
- [x] 注意：attachment 改用**使用者原始 filename**（非 `{uuid}{ext}`），對齊 propose §4-2

### 4-7 `chat_attachment_service.get_attachment_content` / `load_for_prompt`

- [x] [L174 / L222](../../../backend/app/services/chat_attachment_service.py) 改寫：
  - `Path(attachment.file_path).read_bytes()` → `await s3_storage.get_object(attachment.storage_key)`
  - 404 處理由 boto3 ClientError 轉成 AppError

### 4-8 集中進入點驗證

- [x] grep 確認三 service 內無 `.read_bytes()` / `.write_bytes()` 處理使用者上傳資料
- [x] grep 確認三 service 內無 `Path(...).mkdir`、`SKILLS_UPLOAD_DIR` / `ATTACHMENTS_UPLOAD_DIR` 引用（搬遷腳本除外）

---

## Phase 5：Router 層

### 5-1 Skills download

- [x] [`skills/router.py:129-138`](../../../backend/app/api/v1/skills/router.py)
  ```python
  data, download_name = await skill_service.download_skill(...)
  return Response(
      content=data,
      media_type="application/zip",
      headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
  )
  ```
- [x] 移除 `FileResponse` import（若無其他用途）

### 5-2 Scripts download

- [x] [`scripts/router.py:166`](../../../backend/app/api/v1/scripts/router.py) 套同樣 pattern

### 5-3 Chat Attachments download / preview

- [x] [`chat/router.py:477`](../../../backend/app/api/v1/chat/router.py) 維持 `StreamingResponse(io.BytesIO(data), ...)`, data 來源換 S3, 介面不變 —（router 介面零變更；service 內 `get_attachment_content` 已於 Phase 4-7 切換 S3）

---

## Phase 6：`main.py` 清理

- [x] [`main.py:27-38`](../../../backend/app/main.py) 移除 `_ensure_upload_dirs` 整段
- [x] [L43](../../../backend/app/main.py) lifespan 內呼叫一併移除
- [x] 移除 `from pathlib import Path`（若無其他用途）
- [x] `SKILLS_UPLOAD_DIR` / `ATTACHMENTS_UPLOAD_DIR` 暫保留在 `config.py`（搬遷腳本仍要用）

---

## Phase 7：一次性搬遷腳本

### 7-1 腳本骨架

- [x] 新建 `backend/scripts/__init__.py`
- [x] 新建 `backend/scripts/migrate_storage_to_s3.py`
- [x] CLI：`--dry-run` / `--domain skills,scripts,attachments` / `--limit N`

### 7-2 處理邏輯

- [x] 連 DB（重用 `app.core.database.AsyncSessionLocal`）
- [x] 對每個 domain：
  - 撈所有 row（含 `is_deleted=True`）
  - 已遷移判斷：`storage_key` 不以 `data/` 開頭 → 跳過
  - 否則進入搬遷
- [x] 搬遷單筆（**所有 domain 都是「直接 cp」, 無展開**）：
  1. `disk_path = Path(row.storage_key)`；不存在 → 記 failed + skip
  2. `content = disk_path.read_bytes()`
  3. 計算新 key：
     - Skill：`build_key("skills", skill_uid, basename(disk_path))`（例 `skills/{uid}/foo.zip`）
     - Script：`build_key("scripts", script_uid, basename(disk_path))`
     - Chat Attachment：`build_key("attachments", attachment_uid, row.file_name)` ← 用 `file_name` 不是 disk 上的 `{uuid}{ext}`
  4. `await s3_storage.put_object(new_key, content, mime)`
     - Skill / Script mime = `"application/zip"`
     - Attachment mime = `row.file_type`
  5. `is_deleted=True` → `await s3_storage.mark_deleted(new_key)`
  6. UPDATE `storage_key = new_key`（同一 transaction commit）

### 7-3 輸出

- [x] 過程列印：`[OK] skill abc → skills/abc/foo.zip` / `[SKIP] script def (已遷移)` / `[FAIL] attachment ghi: 檔案不存在`
- [x] 結束印彙總 + `failed_uids.txt`（含 domain / uid / 原因）

### 7-4 執行

- [x] 本機：`python -m scripts.migrate_storage_to_s3 --dry-run`
- [x] 容器：`docker compose exec backend python -m scripts.migrate_storage_to_s3 --dry-run`
- [x] Coolify：透過 "Execute command in container"

---

## Phase 8：單元測試 + 手動 smoke

### 8-1 Storage module

- [x] `tests/storage/test_s3_storage.py`（moto mock）
  - `build_key` 正常 / 接受 UUID
  - `_sanitize_filename` 路徑字元 / Unicode / 控制字元
  - `put_object` + `get_object` round trip
  - `mark_deleted` 後 `get_object_tagging` 驗 `status=deleted`
  - `exists` true / false
  - lazy init 缺憑證 raise

### 8-2 Service 切換後測試

- [x] `tests/services/test_skill_service.py` / `test_script_service.py` / `test_chat_attachment_service.py`：原本讀寫 disk 的 fixture / assertion 改為 mock S3（`moto.mock_aws`）—（既有 `backend/tests/services/` 僅 `test_classifier_service.py` / `test_rag_rrf_fuse.py`，無 skill / script / chat_attachment service 測試可改；S3 行為改由 8-1 直接覆蓋, 不為此版補建空殼測試）
- [ ] `pytest backend/tests -v` 全綠 —（人工驗證；需先 `pip install moto[s3] boto3`）

### 8-3 手動 smoke（真實 AWS）

- [ ] 對 `agents-platform-test-datas` 跑：
  - 上傳 skill → AWS Console 看到 `skills/{uid}/foo.zip`
  - download skill → 內容一致
  - delete skill → S3 object 加 `status=deleted` tag
  - 上傳 attachment（含中文檔名）→ console 看到正確 key
  - `aws s3 rm s3://agents-platform-test-datas/...` → AccessDenied

---

## Phase 9：部署順序與驗收

> ⚠️ Flyway V52 跑完 → 搬遷腳本跑完之間, 既有檔案 download 會 404。**夜間低峰部署 + 事先公告**。

### 9-1 部署順序（Coolify）

- [ ] **Step 1**：merge 本 task PR 到 `main`
- [ ] **Step 2**：Coolify 拉新 image 部署（Flyway 自動跑 V52）
- [ ] **Step 3**：Coolify console 進 backend container, 跑：
  ```bash
  python -m scripts.migrate_storage_to_s3 --dry-run
  python -m scripts.migrate_storage_to_s3
  ```
- [ ] **Step 4**：驗 `failed_uids.txt` 為空或可接受
- [ ] **Step 5**：抽樣下載驗證
- [ ] **Step 6**：宣告完成

### 9-2 驗收清單

- [ ] Phase 0 ~ 8 所有 checkbox 完成
- [ ] `pytest backend/tests -v` 全綠
- [ ] Flyway V52 已跑, `\d skill` 看到 `storage_key`
- [ ] AWS Console 對應 bucket 三個 prefix 結構皆存在
- [ ] 軟刪除一筆 skill 後, S3 object 加 `status=deleted` tag
- [ ] 既有所有資料可正常下載
- [ ] `_ensure_upload_dirs` 已從 `main.py` 拔除
- [ ] docker-compose `backend-data` volume mount **仍存在**

### 9-3 Rollback

- 程式碼層 rollback：不建議（model 屬性名已改, 上一版會 5xx）
- 推薦：forward fix —— 修問題後重新 deploy；搬遷腳本 idempotent 可重跑
- 預防：merge 前完整在測試環境跑過 §8-3 手動 smoke
