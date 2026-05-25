# v1.5 Propose

> 本文件為 v1.5 的構想與討論紀錄。定稿後拆為 `tasks-v1.5.*.md` 規格文件再進行實作。
>
> 前置版本：[v1.4 propose](../v1.4/propose-v1.4.0.md)

---

## 0. 前置假設

v1.4 系列已將 `dev-v1.3` 與 `df-dev-v1.3-extended` 合一進 `dev-v1.4`／`main`, Coolify 部署管線與 DF-SSO 整合都已上線（詳見 v1.4 propose §2、§3）。

v1.5 在此基礎上處理**檔案儲存**：把目前直接寫入 Volume 的方式, 整體切到 **AWS S3**, 並把 S3 操作抽成共用 module（不可零散散在各 service 末尾）。

---

## 1. 版本目標

1. **檔案儲存移到 S3**：移除「volume mount + 本地路徑」做法, 改成 S3 object 儲存
   - 測試站 bucket：`agents-platform-test-datas`
   - 正式站 bucket：`agents-platform-prod-datas`
2. **S3 操作抽成共用 module**：新增 `app/storage/`, 給三個既有上傳領域（Skills / Scripts / Chat Attachments）共用同一支客戶端與檔案命名 / 標籤策略
3. **檔名規則統一為「人類可讀」**：以使用者輸入的檔名為 S3 object key 的尾段, 而非 UUID（目前 Chat Attachments 為 UUID, 須改）
4. **覆蓋與軟刪除策略對齊**：
   - Update → 直接覆蓋同一 S3 key（搭配 bucket versioning, 舊版自動保留可救回）
   - Delete → 採軟刪除：DB `is_deleted=true` + S3 object 加單一 tag `status=(deleted)`, **絕不**呼叫 `s3:DeleteObject`

### 範圍內

- 後端新增 `app/storage/s3_storage.py` 共用 module（upload / get / mark_deleted / 路徑命名）
- 三個既有上傳 service 全面切換：
  - [skill_service.py:205](backend/app/services/skill_service.py#L205)（Skills, `data/skills/{uid}/{filename}.zip`）
  - [script_service.py](backend/app/services/script_service.py)（Scripts, 同上 pattern）
  - [chat_attachment_service.py:139](backend/app/services/chat_attachment_service.py#L139)（Chat Attachments, 現用 `data/attachments/{YYYYMM}/{uuid}{ext}`）
- DB 三表 `file_path` 欄位語意改為「S3 object key」（不改欄位名以降低 migration churn）：
  - [skill.py:21](backend/app/models/skill.py#L21)
  - [script.py](backend/app/models/script.py)
  - [chat_attachment.py:24](backend/app/models/chat_attachment.py#L24)
- 既有資料一次性搬遷腳本：volume → S3, 同步把 `file_path` 改成新 key
- `.env.example` 補齊 AWS / S3 設定鍵, 並建立 test / prod 兩組 IAM User
- 移除 [main.py](backend/app/main.py) 內 `_ensure_upload_dirs()` 對本地路徑的依賴

### 範圍外（延後）

- v1.6+：S3 lifecycle 規則（tag=deleted 滿 N 天歸檔 Glacier, 自動 expire）
- v1.6+：CDN / 預簽 URL（presigned URL）下載加速；目前仍走 backend proxy
- v1.6+：抽象 `StorageBackend` interface 容納多 backend（MinIO / GCS）, v1.5 只做單一 AWS S3 實作, 不過度抽象

---

## 2. AWS 端：IAM 與 Bucket 設計

### 2-1 IAM Role vs IAM User 決策

本系統部署在 **Coolify（自架 VPS）**, 非 AWS EC2 / ECS / EKS / Lambda, **無法**透過 instance metadata 自動掛 IAM Role。結論：

- ❌ IAM Role：適用於應用本身跑在 AWS 基礎建設上, 此專案不適用
- ✅ **IAM User + Access Key**：唯一可行做法, 程式以 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 環境變數注入憑證

### 2-2 兩組獨立 User（test / prod 完全切開）

| User 名 | 可存取 bucket | 用途 |
| --- | --- | --- |
| `agents-platform-test-s3` | `agents-platform-test-datas` | 測試 / 開發環境專用 |
| `agents-platform-prod-s3` | `agents-platform-prod-datas` | 正式環境專用 |

不共用 key 是為了 blast radius：test 環境 key 一旦外洩, 正式資料完全不受影響。

### 2-3 最小權限 Policy（每組各一份）

僅允許 **CRU + Tagging**, 不發 `s3:DeleteObject`, 強制軟刪除走 tag 路徑：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectTagging",
        "s3:GetObject",
        "s3:GetObjectTagging",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::agents-platform-test-datas",
        "arn:aws:s3:::agents-platform-test-datas/*"
      ]
    }
  ]
}
```

- `PutObject`：建立 + 覆蓋（Update）
- `PutObjectTagging`：軟刪除標記
- `GetObject` / `GetObjectTagging`：讀取 + 讀標籤
- `ListBucket`：管理 / debug 用, 非必要可拿掉
- **無** `DeleteObject` / `DeleteObjectVersion` / `DeleteBucket*`：實體刪除權限完全切斷

### 2-4 Bucket 設定建議

| 設定 | 值 | 理由 |
| --- | --- | --- |
| **Versioning** | Enabled | 覆蓋（Update）時舊版本自動保留, 誤覆蓋可救回 |
| **Block Public Access** | All ON | 所有 object 一律走後端轉發, 不開公開存取 |
| **Default Encryption** | SSE-S3（AES-256） | 靜態加密預設打開, 不增加程式碼複雜度 |
| **Region** | 視部署延遲 / 法遵需求決定（建議 `ap-northeast-1`） | 待確認 |

---

## 3. S3 儲存共用 module 設計

> 起點：目前三個上傳 service 各自 `Path(settings.X_UPLOAD_DIR) / ...` 寫檔, 切 S3 後不可重複實作, 必須抽共用。

### 3-1 module 位置與職責

新增 `backend/app/storage/s3_storage.py`：

| 函式 | 職責 |
| --- | --- |
| `build_key(domain, entity_uid, filename) -> str` | 統一 key 命名規則（見 §4） |
| `put_object(key, body, content_type)` | Create + Update（同一 key 覆蓋, 倚賴 versioning 保留歷史） |
| `get_object(key) -> bytes` | 讀檔 |
| `mark_deleted(key)` | 加單一 tag `status=(deleted)`（軟刪除, 不刪實體；不附時間 / 操作者, 維持最簡訊號） |
| `exists(key) -> bool` | 偵測（migration / debug 用） |

實作上：

- 底層用 `boto3.client("s3")`, client 在模組層 lazy init（首次呼叫才建立, 避免無 AWS 憑證的環境啟動就炸）
- bucket name 從 `settings.S3_BUCKET` 取（test / prod 由 env 區分）
- 不做 retry / circuit breaker 抽象, boto3 預設行為已夠用
- **不** 引入 `StorageBackend` ABC：v1.5 只有一種 backend, 過早抽象（[CLAUDE.md 基本原則](../../../CLAUDE.md)）

### 3-2 三個 service 切換點

| Service | 既有寫法 | 改後 |
| --- | --- | --- |
| `skill_service.create_skill` | `zip_path = skill_dir / f"{base}.zip"; zip_path.write_bytes(...)` | `key = build_key("skills", skill_uid, f"{base}.zip"); put_object(key, zip_content, "application/zip")` |
| `script_service.create_script` | 同 Skill pattern | 同上 |
| `chat_attachment_service.create_attachments` | `file_path = base_dir / f"{attachment_uid}{ext}"` | `key = build_key("attachments", attachment_uid, original_filename); put_object(...)` |

對應的 `download` / `get_*_content` endpoint 也都改成走 `get_object(key)`。

### 3-3 下載 / 預覽路徑

維持「走後端 proxy」策略（與目前一致）：

- frontend → backend download endpoint → backend `get_object(key)` → stream 回 client
- 不在 v1.5 引入 S3 presigned URL（前端直連 S3）, 留 v1.6+ 視效能再評估
- 好處：v1.5 對 frontend 0 修改, 純後端切換

---

## 4. 檔名與 key 命名規則

### 4-1 規則

S3 object key 一律：

```
{domain}/{entity_uid}/{user_supplied_filename}
```

| Domain | 範例 key |
| --- | --- |
| Skills | `skills/3f9c.../my-helper.zip` |
| Scripts | `scripts/8b21.../backup-job.zip` |
| Chat Attachments | `attachments/c104.../會議紀錄.pdf` |

設計理由：

- **`{entity_uid}` 為前綴**：避免兩個使用者同時上傳 `report.pdf` 造成 key collision；同時 entity_uid 本身就是 DB 主鍵, 一一對應
- **檔名尾段保留原始輸入**：滿足「人類可辨識」需求, 在 S3 console 一眼能看出該物件意義
- **跨 domain 用前綴隔離**：方便日後針對單一 domain 做 lifecycle 規則 / 監控

### 4-2 既有 service 行為對齊

- Skills / Scripts：原本就有 `original_filename` 概念, 直接沿用
- Chat Attachments：**目前是 `{uuid}{ext}`, 此版改為 `{user_supplied_filename}`**
  - 同檔名上傳多次：因為 `{attachment_uid}` 不同, key 必然不同, 不會相覆蓋
  - 檔名清理：移除路徑分隔符 / 控制字元, 保留中文與空格（與 username 含空格策略一致）

### 4-3 不雜湊 / 不加時間戳

- 不加 hash / timestamp 前綴：人類可讀性優先, 唯一性已由 `{entity_uid}` 保證
- 不做 URL encode 後再存：S3 接受 UTF-8 key, boto3 會處理 encoding

---

## 5. 覆蓋（Update）與軟刪除（Delete）策略

### 5-1 Update：直接覆蓋同 key

| 步驟 | 動作 |
| --- | --- |
| 1 | service 收到 update 請求, 構造同樣的 `{domain}/{entity_uid}/{filename}` key |
| 2 | `put_object(key, new_body)` 覆蓋 |
| 3 | DB `file_path` 不變（key 不變）；若 filename 改了, 新 key 取代舊 key, 並把舊 key `mark_deleted` |
| 4 | bucket versioning 自動保留舊版本, 後台可救回但 app 看不到 |

**Filename 在 Update 改變時的處理**：

- 舊 key `mark_deleted(old_key)`（加 `status=(deleted)` tag, 不實體刪）
- 新 key `put_object(new_key, body)`
- DB `file_path` 更新為 new_key

### 5-2 Delete：軟刪除（雙端標記, 不實體刪）

| 端 | 動作 |
| --- | --- |
| DB | `is_deleted = true`（沿用 [base.py:12](backend/app/models/base.py#L12) 既有 pattern, 應用查詢自動過濾）|
| S3 | `mark_deleted(key)` → `PutObjectTagging` 加單一 tag `status=(deleted)` |

設計理由（最簡訊號）：

- 只用「有 / 沒有 `status=(deleted)` 這個 tag」這 1 bit 資訊判斷, 不存 `deleted_at` / `deleted_by`
- 操作者 / 時間若日後追查需要, **DB 才是真相來源**（`is_deleted` + 對應 audit log / `updated_at`）, S3 端不重複記
- tag value 字面用 `(deleted)`（含括號）讓 S3 console 一眼可辨, 不會與其他 generic `true` / `false` tag 混淆

兩端**都不會**呼叫 `s3:DeleteObject`：

- 應用程式不發起（API 不暴露刪除實體 endpoint）
- IAM 也不發 `DeleteObject` 權限（§2-3）, 即使程式 bug 也不可能誤刪 — 防禦深度

未來若要清理（例如歸檔超過 1 年的 `status=(deleted)` object）, 走 **bucket lifecycle rule** 自動處理（v1.6+, §1 範圍外）, 不在應用程式碼裡刪。

---

## 6. DB schema 變更

### 6-1 欄位語意改變（不改欄位名）

三表 `file_path` 欄位：

| Table | 欄位 | 既有值範例 | v1.5 後值範例 |
| --- | --- | --- | --- |
| `skill` | `file_path` | `data/skills/3f9c.../my-helper.zip` | `skills/3f9c.../my-helper.zip` |
| `script` | `file_path` | `data/scripts/8b21.../backup-job.zip` | `scripts/8b21.../backup-job.zip` |
| `chat_attachment` | `file_path` | `data/attachments/202604/c104....pdf` | `attachments/c104.../會議紀錄.pdf` |

**保留欄位名 `file_path`** 而非改名為 `storage_key`：

- 改名要動三個 model + 全部 service + 所有測試, churn 大
- 語意改變透過 docstring / commit message 紀錄即可
- 若未來真有抽象需求再一次性改

### 6-2 既有資料搬遷

一次性 migration 腳本：`migrations/scripts/v1_5_volume_to_s3.py`

| 步驟 | 動作 |
| --- | --- |
| 1 | scan `skill` / `script` / `chat_attachment` 三表, 取所有 `file_path` |
| 2 | 對每筆：讀 volume 上的本地檔 → `put_object(new_key, body)` → 更新 DB `file_path` |
| 3 | 完成後印出總筆數 / 成功 / 失敗 / 跳過清單 |
| 4 | 人工驗證若干筆可正常下載 → 切換正式部署 |

腳本特性：

- **idempotent**：以 DB `file_path` 是否已為新格式（無 `data/` 前綴）判斷, 跳過已搬遷
- **dry-run 模式**：`--dry-run` 只列印不上傳, 用來估時間 / 流量
- 不刪 volume 原檔：留作備援, 確認穩定後（v1.5.1 或下版本）再清

---

## 7. 環境變數

### 7-1 `.env.example` 新增

```bash
# === AWS S3 ===
# IAM User Access Key（test 與 prod 各一組獨立 user, 對應 bucket 隔離）
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-northeast-1

# S3 Bucket（測試 / 正式）
# test: agents-platform-test-datas
# prod: agents-platform-prod-datas
S3_BUCKET=agents-platform-test-datas
```

### 7-2 既有變數處置

| 變數 | 處置 |
| --- | --- |
| `SKILLS_UPLOAD_DIR=data/skills` | 移除（S3 取代） |
| `SKILLS_MAX_FILE_SIZE=52428800` | **保留**（仍是 size 上限, 與 backend 無關 storage 後端） |
| `ATTACHMENTS_UPLOAD_DIR=data/attachments` | 移除 |

`docker-compose.yml` 內 `backend-data:/app/data` volume 暫**保留**（搬遷腳本仍要讀舊檔, 切完且驗證穩定後再下版本拔）。

---

## 8. 影響範圍清單

| 層級 | 檔案 |
| --- | --- |
| 後端新增 | `backend/app/storage/__init__.py`、`backend/app/storage/s3_storage.py` |
| 後端修改 service | `app/services/skill_service.py`、`app/services/script_service.py`、`app/services/chat_attachment_service.py` |
| 後端修改 main | `app/main.py`（拿掉 `_ensure_upload_dirs()`） |
| 後端修改 config | `app/core/config.py`（新增 `AWS_*` / `S3_BUCKET` 設定） |
| DB | 三表 `file_path` 欄位語意調整, 無 schema migration（仍是 String/Text） |
| 搬遷腳本 | `migrations/scripts/v1_5_volume_to_s3.py`（新增, 一次性） |
| 環境變數 | `.env.example`、`.env`、`.env.test`、`.env.production` 全更新 |
| 依賴 | `backend/pyproject.toml` 新增 `boto3` |
| 部署 | `docker-compose.yml` 視需要保留 backend-data volume（過渡期） |

---

## 9. 風險與待議

| 項目 | 風險 / 待確認 |
| --- | --- |
| AWS region 選擇 | 預設 `ap-northeast-1`（東京）, 若 Coolify VPS 在歐洲機房延遲會明顯, 待確認部署地點 |
| 既有資料量 | 搬遷時間取決於 skills/scripts 累積數量, 需先實際 query 確認規模 |
| Chat Attachment 中文檔名 | 部份 boto3 / S3 console 對非 ASCII key 顯示行為要驗證, 至少 download 須能正常工作 |
| Filename collision in update | 同 entity_uid 內若改名又改回原名, 中間版本的 key 會殘留 `status=(deleted)` tag, 需 lifecycle 處理（v1.6+） |
| 搬遷期間 backend 重啟 | volume 路徑與 S3 路徑並存階段, 若 backend 剛好重啟讀到不同程式碼版本, 可能讀錯。建議「migration 腳本跑完 → 同次部署切換 service 程式碼」串成一次 deploy |
| boto3 client 連不上 AWS 時 | service 啟動不該卡, client lazy init；第一次使用才會炸 → 業務面看到 5xx, 由 Coolify alert 抓 |

---

## 10. 上線前自我檢查

- [ ] 兩組 IAM User 建好, policy 已套, AWS console 試 `aws s3 cp` 成功且無 delete 權限
- [ ] Bucket versioning / Block Public Access / SSE-S3 三項設定確認 ON
- [ ] `app/storage/s3_storage.py` 五個函式皆有單元測試（mock boto3）
- [ ] 三個 service 切換後, Skills / Scripts / Chat Attachments 三條 upload / download / update / delete 流程實機驗過
- [ ] 軟刪除：DB 撈得到 `is_deleted=true` 的記錄, S3 console 看到對應 object 已加 `status=(deleted)` tag
- [ ] 搬遷腳本 `--dry-run` 印出與實際筆數一致, 正式跑完後新舊 key 一一對應
- [ ] `.env.production` 的 `S3_BUCKET=agents-platform-prod-datas`, key 為 prod user, **絕對不要**配 test 的 bucket
