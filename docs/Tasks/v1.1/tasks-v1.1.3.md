# v1.1.3 任務規格：Skills 編輯

> **狀態：已完成（commit 37aa3ba, 2026-04-21）**

## 版本目標

讓 Skill 擁有者可以在上傳後修改內容：支援「重新上傳整包」（覆蓋整份 zip）與「線上編輯單一檔案」（文字檔直接改後回寫 zip），並在觸發前顯示「此 Skill 目前被 N 個 Agent 使用」提醒使用者影響範圍。

### 範圍內

- `GET /api/v1/skills/{uid}/usage`：取得引用此 Skill 的 Agent 清單
- `POST /api/v1/skills/{uid}/reupload`：整包重新上傳（沿用上傳邏輯，覆蓋 `file_path`）
- `PUT /api/v1/skills/{uid}/file?path=...`：單檔內容更新（限文字檔白名單）
- 前端 Skill 詳情頁（`/skills/{uid}`）：
  - 「重新上傳」按鈕
  - Code viewer 每個檔案加「編輯」切換成 textarea
  - 觸發前呼叫 usage 顯示影響 Agent 數
- 樂觀鎖：編輯單檔時以 `updated_at` 比對，衝突回 409

### 範圍外

- 版本歷史 / 回滾（需自行保留本地副本）
- 新增 / 刪除 / 改檔名（需走「重新上傳整包」）
- 二進位檔線上編輯
- 權限代理（admin 代他人編輯）→ v1.2+

---

## 前置現況

- v1.0 已實作 Skill 上傳、下載、檔案樹、單檔預覽
- `skill_service.upload_skill` 接受 `list[UploadFile]`，自動包成 zip
- `get_file_content` 已處理二進位 / 超大檔偵測
- Agent ↔ Skill 多對多關聯表已存在（v1.0 `agent_skill`）

---

## 已確認決策

| #   | 決策                       | 結論                                                                 |
| --- | -------------------------- | -------------------------------------------------------------------- |
| 1   | 編輯權限                   | 僅擁有者；admin 不可代改                                              |
| 2   | 可編輯副檔名白名單          | `.md` / `.txt` / `.json` / `.yaml` / `.yml` / `.py` / `.ts` / `.js` / `.sh` |
| 3   | 單檔大小上限               | 500 KB（等同預覽上限 `FILE_PREVIEW_MAX_BYTES`）                       |
| 4   | 編碼                       | UTF-8；非 UTF-8 內容回 400                                            |
| 5   | 並發控制                   | 樂觀鎖：request body 帶 `expected_updated_at`，DB 值不符回 409         |
| 6   | Cascade 策略               | 不做。Agents 僅引用 `skill_uid`，內容變更即時生效                      |
| 7   | Usage 清單內容             | 只回 agent_uid / agent_name / owner_username，不回私人設定             |

---

## Phase 1：後端

### 1-1 Schema（擴充 `app/schemas/skills/schemas.py`）

- [x] `SkillUsageItem`：`agent_uid`、`agent_name`、`owner_username`、`visibility`
- [x] `SkillUsageResponse`：`{ items: list[SkillUsageItem], count: int }`
- [x] `SkillFileUpdateRequest`：
  - `content: str`（必填，長度 ≤ 500 KB）
  - `expected_updated_at: str`（ISO8601，樂觀鎖比對）

### 1-2 Repository

- [x] `agent_repository.list_by_skill_uid(skill_uid, db) -> list[Agent]`
  - `SELECT agent.* FROM agent JOIN agent_skill ON ... WHERE agent_skill.skill_uid = ? AND agent.is_deleted = false`

### 1-3 Service

於 `skill_service.py` 新增：

- [x] `async def get_usage(skill_uid, user_uid, role, db) -> dict`
  - 驗證存取權（擁有者 or admin or public）
  - 回傳 Agent 清單 + `count`

- [x] `async def reupload_skill(skill_uid, user_uid, role, files, db) -> dict`
  - 驗證**擁有者**（不可 admin 代改）
  - 檢查 `expected_updated_at`（從 query / form 取）
  - 沿用 `upload_skill` 的 zip 處理邏輯（抽為 `_build_zip(files) -> bytes`）
  - 覆蓋原 `file_path` 檔案
  - 更新 `chat_skill`（不對）→ 更新 `skill` 記錄：`file_size` / `original_filename` / `updated_at`
  - 回傳 `_skill_to_dict(skill)`

- [x] `async def update_file_content(skill_uid, user_uid, path, content, expected_updated_at, db) -> dict`
  - 驗證擁有者
  - 驗證 `path` 副檔名在白名單
  - 驗證 `content` 長度 ≤ 500KB
  - 驗證 UTF-8（已是 str，skip）
  - 讀取 zip → 保留其他檔案 → 替換指定檔 → 寫回同一 `file_path`
  - 樂觀鎖：若 DB 的 `updated_at.isoformat()` ≠ `expected_updated_at` → 409
  - 更新 `file_size` / `updated_at`
  - 回傳 `{ file_path, size, updated_at, new_content_preview: content[:200] }`

- [x] `_rebuild_zip(zip_path: str, update_path: str, new_content: bytes) -> int`
  - 讀現 zip → 寫臨時 zip → 替換或更新目標檔案 → atomic rename
  - 回傳新的 file_size

### 1-4 Router（`app/api/v1/skills/router.py`）

| 方法 | 端點                                              | 說明                          |
| ---- | ------------------------------------------------- | ----------------------------- |
| GET  | `/api/v1/skills/{uid}/usage`                      | 列出引用此 Skill 的 Agent     |
| POST | `/api/v1/skills/{uid}/reupload`                   | 整包重新上傳（multipart/form） |
| PUT  | `/api/v1/skills/{uid}/file?path=...`              | 單檔內容更新（JSON body）     |

- [x] 全部掛 `get_current_user`
- [x] `reupload` 接 `list[UploadFile]`，與 `POST /api/v1/skills` 同形式
- [x] `PUT file` body：`SkillFileUpdateRequest`
- [x] 更新後清空可能的 cache（目前 `get_file_content` 無 cache，skip）

### 1-5 錯誤情境

- [x] 非擁有者（含 admin）→ 403
- [x] `path` 副檔名不在白名單 → 400「此檔案類型不支援線上編輯，請使用『重新上傳整包』」
- [x] `content` 超 500 KB → 400
- [x] 樂觀鎖失敗 → 409「檔案已被更新，請重新載入後再編輯」
- [x] zip 內不存在指定 path → 404

---

## Phase 2：前端

### 2-1 型別 & RTK Query（`store/skillsApi.ts`）

- [x] `SkillUsageItem` / `SkillUsageResponse`（`types/skills.ts`）
- [x] `useGetSkillUsageQuery(skillUid)`
- [x] `useReuploadSkillMutation`（類似 `useUploadSkillMutation`）
- [x] `useUpdateSkillFileMutation({ skillUid, path, body: { content, expected_updated_at } })`
- [x] Mutation 成功後 `invalidatesTags: ["Skills"]`（包含 tree 與 file content）

### 2-2 Skill 詳情頁強化（`app/(main)/skills/[uid]/page.tsx`）

- [x] 頁首「操作」區加「重新上傳」按鈕（僅擁有者顯示）
  - 點擊 → 開 modal，顯示 usage 數：「目前有 N 個 Agent 使用此 Skill，更新後會立即套用」
  - 使用者確認後，開啟與 `/skills/upload` 相同的上傳表單（可選 files / folder）
  - 送出呼叫 `reupload`

- [x] Code viewer 右上加「編輯」按鈕（僅擁有者 + 檔案在白名單 + 大小 ≤ 500KB）
  - 點擊 → textarea 取代 SyntaxHighlighter，內容可編輯
  - 下方「儲存」/「取消」兩個按鈕
  - 儲存時呼叫 `updateSkillFile`，帶 `expected_updated_at`（來自 `useGetSkillQuery` 的 `skill.updated_at`）
  - 儲存成功 → Dialog「已儲存」→ 切回檢視模式 → invalidate tags 刷新
  - 409 錯誤 → Dialog「檔案已被更新，請重新載入後再編輯」

### 2-3 使用量 Dialog 元件

- [x] `components/SkillUsageDialog.tsx`（或直接內嵌於 page.tsx）
  - 觸發重新上傳 / 編輯前呼叫
  - 顯示 agent 清單（卡片或列表），每項顯示 `agent_name` + `owner_username`
  - 「繼續」+「取消」按鈕

### 2-4 白名單常數（`utils/editableExtensions.ts`）

- [x] `EDITABLE_EXTENSIONS = new Set([".md", ".txt", ".json", ".yaml", ".yml", ".py", ".ts", ".js", ".sh"])`
- [x] `isEditable(filename: string): boolean`

---

## Phase 3：驗收

- [x] 擁有者於 Skill 詳情頁可看到「重新上傳」與「編輯」按鈕
- [x] 非擁有者（含 admin）看不到按鈕，且直接打 API 會 403
- [x] 重新上傳後 `skill.file_size` / `original_filename` / `updated_at` 正確更新
- [x] 單檔編輯後，zip 內其他檔案保持不變
- [x] 編輯時若他人同時改動，第二位送出 409 並提示
- [x] `.exe` / `.png` 檔案不顯示編輯按鈕，強打 API 回 400
- [x] 超過 500 KB 的檔案編輯被擋下
- [x] 上傳 / 編輯前 usage Dialog 正確顯示影響的 Agent 數
- [x] 關聯 Agent 立即讀到新內容（無需重啟 / 重建 agent）
