# 提交當前分支所有變更

將當前分支的所有變更（包含新增、修改、刪除的檔案）一次性提交到 Git。
**不需要詢問使用者確認，直接執行所有步驟。**

## 執行步驟

1. 執行 `git status` 查看當前分支與所有變更檔案。如果沒有任何變更，告知使用者「沒有需要提交的變更」並結束。

2. 執行 `git diff --stat` 和 `git diff --cached --stat` 快速了解變更範圍。

3. 執行 `git log --oneline -5` 參考近期 commit 訊息風格。

4. **依 [docs/Design-Base/90-code-fixed.md](../../docs/Design-Base/90-code-fixed.md) 判斷是否須寫入 `fixed.md`**：

   - 若本次變更**符合下列任一情境**，須在當前進行版本的 `docs/Tasks/v{X.Y}/fixed.md` 新增條目（檔案不存在則建立）：
     - 修補 bug（功能不符預期、報錯、UI 異常）
     - 修正設定 / 環境變數 / docker-compose / migration 等基礎設施錯誤
     - 修正既有規格實作偏差
     - 第三方相依升級 / API 變動造成的 breaking change 修補
     - 效能 / 安全性回填修正
   - **不需寫入**的情境（直接跳到步驟 5）：
     - 純粹依 `tasks-v*.md` 規格的新功能實作
     - 純文件修訂、註解 / 格式調整
     - 不改變行為的重命名 / 重構
   - 寫入規則：
     - 條目以二級標題 `## N. <簡述>` 開頭，標題尾端標註 `〔YYYY-MM-DD HH:MM:SS〕`（時區 `Asia/Taipei`，現在時間取自系統）
     - 必備區塊：`**問題**` / 根因敘述 / `**修正**` / `**影響檔案**`
     - 條目編號 `N` 接續該檔既有最大編號 +1（檔案為新建則從 1 起）
     - 當前版本判定優先順序：當前 git 分支若為 `dev-vX.Y` 取 `vX.Y`；否則取 `docs/Tasks/v*/` 下最新版本資料夾
   - 寫入完成後將 `fixed.md` 一併納入下一步 `git add -A` 的提交範圍

5. 根據變更內容（含步驟 4 的 `fixed.md` 異動，若有），自動撰寫 commit message，格式規則：
   - 前綴使用 `(AI)` 標記，例如：`(AI) Add: 新增使用者管理功能`
   - 使用中文撰寫描述
   - 前綴類型參考：`Add:` 新功能、`Modify:` 修改、`Fix:` 修復、`Refactor:` 重構、`Docs:` 文件
   - 若步驟 4 有寫入 `fixed.md`，commit 類型優先選 `Fix:` 並於描述帶入修正主題

6. 直接執行以下命令提交所有變更（不需等待使用者確認）：

   ```
   git add -A
   git commit -m "(AI) <類型>: <描述>"
   ```

7. 提交完成後，推送到當前分支的遠端：

   ```
   git push origin <當前分支名稱>
   ```

8. 執行 `git status` 確認結果，並顯示提交摘要；若步驟 4 有寫入 `fixed.md`，於摘要中標明「📝 已新增 fixed.md 條目 #N」。

## 注意事項

- 全程自動執行，不需要詢問使用者確認
- Commit message 使用中文撰寫，開頭加上 `(AI)` 標記
- 提交後自動推送到當前分支的遠端
- 如果有 `.env`、credentials 等敏感檔案，警告使用者並排除
- 不要加上 Co-Authored-By
- 步驟 4 的 `fixed.md` 寫入須符合 [docs/Design-Base/90-code-fixed.md](../../docs/Design-Base/90-code-fixed.md)；不確定是否該寫時保守判定為「需要寫」並列出根因為何不明（讓使用者後續可手動清掉）
