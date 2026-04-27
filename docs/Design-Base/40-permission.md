# 權限規範

## 角色定義

角色由獨立的 `user_role` 資料表管理，user 資料表透過 `role_uid` 關聯。初始內建兩種角色：

| 角色   | name     | 說明                                     |
| ------ | -------- | ---------------------------------------- |
| 管理員 | `admin`  | 系統管理權限，可管理所有使用者與系統設定 |
| 成員   | `member` | 一般使用權限，僅可操作自身資源           |

- 預設註冊角色為 `member`
- 角色新增、修改、停用僅限 `admin` 操作
- 設計須支援未來擴展新角色（如 `viewer`、`operator` 等），無須改動程式碼結構

### `user_role` 資料表

```sql
CREATE TABLE user_role (
    pid            BIGSERIAL    PRIMARY KEY,
    user_role_uid  UUID         NOT NULL DEFAULT gen_random_uuid(),
    name           VARCHAR(50)  NOT NULL,
    description    VARCHAR(200),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_user_role_user_role_uid ON user_role (user_role_uid);
CREATE UNIQUE INDEX uq_user_role_name ON user_role (name) WHERE is_deleted = FALSE;

COMMENT ON TABLE  user_role                   IS '使用者角色定義表';
COMMENT ON COLUMN user_role.pid               IS '內部自增主鍵';
COMMENT ON COLUMN user_role.user_role_uid     IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN user_role.name              IS '角色名稱（如 admin、member）';
COMMENT ON COLUMN user_role.description       IS '角色說明';
COMMENT ON COLUMN user_role.is_active         IS '是否啟用';
COMMENT ON COLUMN user_role.is_deleted        IS '是否軟刪除';
COMMENT ON COLUMN user_role.created_at        IS '建立時間';
COMMENT ON COLUMN user_role.updated_at        IS '更新時間（Trigger 自動維護）';

-- 初始資料
INSERT INTO user_role (name, description) VALUES
    ('admin',  '系統管理員，可管理所有使用者與系統設定'),
    ('member', '一般成員，僅可操作自身資源');
```

### user 資料表關聯

user 資料表以 `role_uid` 欄位關聯 `user_role`：

```sql
ALTER TABLE "user"
    ADD COLUMN role_uid UUID NOT NULL,
    ADD CONSTRAINT fk_user_user_role
        FOREIGN KEY (role_uid) REFERENCES user_role (user_role_uid);

COMMENT ON COLUMN "user".role_uid IS '所屬角色 UID（關聯 user_role）';
```

### 角色管理 API（admin 專屬）

| 方法     | 路徑                                    | 說明         |
| -------- | --------------------------------------- | ------------ |
| `GET`    | `/api/v1/admin/roles`                   | 取得角色列表 |
| `POST`   | `/api/v1/admin/roles`                   | 新增角色     |
| `PATCH`  | `/api/v1/admin/roles/{user_role_uid}`   | 修改角色     |
| `DELETE` | `/api/v1/admin/roles/{user_role_uid}`   | 停用角色     |

---

## 請求驗證流程

每次 API 請求皆須經過以下驗證，依序執行，任一步驟失敗即中止並回傳對應錯誤：

```text
請求進入
  │
  ▼
1. 驗證 Access Token 是否有效
  │ 失敗 → 401 Unauthorized
  ▼
2. 從 Token payload 取得 user_uid + role
  │
  ▼
3. 檢查該端點所需角色是否符合
  │ 不符合 → 403 Forbidden
  ▼
4. 進入業務邏輯
```

- 步驟 3 的角色檢查**直接比對 Token 中的 role name**，不額外查詢資料庫
- Token 簽發時須將 `role`（role name）寫入 payload（登入與 refresh 時從資料庫 JOIN `user_role` 讀取最新角色名稱）

---

## 端點權限對照

### 公開端點（不需認證）

| 端點                                | 說明         |
| ----------------------------------- | ------------ |
| `POST /api/v1/auth/register`        | 註冊         |
| `POST /api/v1/auth/login`           | 登入         |
| `POST /api/v1/auth/reset-password`  | 重設密碼     |
| `GET  /api/v1/health`               | 健康檢查     |

### member + admin 共用端點

| 端點                                                    | 說明                                                                       |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| `POST   /api/v1/auth/logout`                            | 登出                                                                       |
| `POST   /api/v1/auth/refresh`                           | 換發 Token                                                                 |
| `/api/v1/agents/*`                                      | Agent 管理（讀 / 下載：擁有者 + admin + visibility=public；改：擁有者 + admin；刪 / 切可見性：僅擁有者）|
| `/api/v1/skills/*`                                      | Skills 管理（讀 / 下載：擁有者 + admin + visibility=public；改：擁有者 + admin；刪 / 切可見性：僅擁有者）|
| `/api/v1/scripts/*`                                     | Script 管理（讀 / 下載：擁有者 + admin + visibility=public；改：擁有者 + admin；刪：僅擁有者；含 `GET /scripts/public` 公開瀏覽）|
| `/api/v1/chat/*`                                        | 對話 / 記憶管理（projects / sessions / messages / memories；僅限自身資源） |
| `POST   /api/v1/{agents,skills,scripts}/{uid}/favorite` | 收藏（idempotent；軟刪後再呼叫即復活）                                     |
| `DELETE /api/v1/{agents,skills,scripts}/{uid}/favorite` | 取消收藏（軟刪 `user_favorite`）                                           |
| `GET    /api/v1/users/me/favorites`                     | 我的收藏列表（支援 tombstone 顯示已刪除來源）                              |
| `GET    /api/v1/dashboard/*`                            | 儀錶板（如 `GET /dashboard/rankings` 排行榜）                              |
| `GET    /api/v1/agent-templates`                        | 取得啟用中的 Agent 範本清單（唯讀）                                        |
| `GET    /api/v1/models`                                 | 取得啟用中的 LLM 模型清單（唯讀）                                          |
| `GET    /api/v1/agent-languages`                        | 取得啟用中的 Agent 語言清單（唯讀）                                        |
| `GET    /api/v1/settings/public`                        | 取得 `is_public = TRUE` 的系統設定字典                                     |

### admin 專屬端點

| 端點                              | 說明                                       |
| --------------------------------- | ------------------------------------------ |
| `/api/v1/admin/users/*`           | 使用者管理（查詢、停用、角色變更）         |
| `/api/v1/admin/roles/*`           | 角色管理（新增、修改、停用角色）           |
| `/api/v1/admin/llm-models/*`      | LLM 模型清單管理（新增、編輯、啟停、刪除） |
| `/api/v1/admin/agent-languages/*` | Agent 語言清單管理（含預設語言切換）       |
| `/api/v1/admin/agent-templates/*` | Agent 範本管理（新增、編輯、停用）         |
| `/api/v1/admin/settings/*`        | 系統設定管理（含 `is_public` 切換）        |

---

## 實作方式

### 依賴注入

透過 FastAPI Depends 實作認證與權限檢查，定義於 `api/deps.py`：

```python
from fastapi import Depends, HTTPException, status

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    """驗證 Access Token，回傳 payload（含 user_uid、role）"""
    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return payload

def require_role(*allowed_roles: str):
    """產生角色檢查依賴，支援傳入多個允許的角色名稱"""
    async def checker(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return current_user
    return checker
```

### 路由使用

```python
# member + admin 皆可存取（已登入即可）
@router.get("/api/v1/agents")
async def list_agents(current_user: TokenPayload = Depends(get_current_user)) -> ApiResponse:
    ...

# 僅 admin 可存取
@router.get("/api/v1/admin/users")
async def list_users(current_user: TokenPayload = Depends(require_role("admin"))) -> ApiResponse:
    ...

# 未來擴展：多角色皆可存取
@router.get("/api/v1/some-resource")
async def some_resource(current_user: TokenPayload = Depends(require_role("admin", "operator"))) -> ApiResponse:
    ...
```

---

## 資源存取控制

- `member` 僅可操作自身擁有的資源，查詢時**必須**以 Token 中的 `user_uid` 過濾
- **禁止** `member` 透過修改路徑參數存取他人資源（Repository 層須驗證資源所有權）
- `admin` 可存取所有使用者的資源
- 可見性開放：`agent` / `skill` / `script` 三種資源若 `visibility = 'public'`，**所有登入使用者**可讀（GET 詳情 / 下載 / 列入收藏），但**改 / 刪 / 切可見性**仍受下表規範
- **刪除一律走軟刪除**（`is_deleted = TRUE`），且**僅擁有者本人**可刪 — `admin` 亦不代刪。`agent` / `skill` 的「切可見性」同樣僅擁有者可操作

| 動作 | 擁有者 | admin | 公開資源（visibility=public）非擁有者 | 私人資源非擁有者 |
| --- | --- | --- | --- | --- |
| GET 詳情 / 下載 | ✅ | ✅ | ✅ | ❌（404） |
| PATCH / PUT 修改 | ✅ | ✅ | ❌（403） | ❌（404） |
| DELETE 軟刪 | ✅ | ❌（403） | ❌（403） | ❌（404） |
| 切可見性 | ✅ | ❌（403） | ❌（403） | ❌（404） |

```python
# Repository 層範例：member 僅取自身資源
async def get_agents_by_user(
    self, user_uid: str, db: AsyncSession
) -> list[Agent]:
    stmt = select(Agent).where(
        Agent.owner_uid == user_uid,
        Agent.is_deleted == False,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

---

## 回應格式

權限錯誤回應遵循 [20-backend.md § 統一回應格式](20-backend.md#統一回應格式)，`response_code` 使用 `401`（未認證）/ `403`（權限不足），**禁止**在 `detail` 中揭露所需角色或當前角色資訊。
