# 後端規範

> 技術棧與版本定義參閱 [00-overview.md § 後端](00-overview.md#後端)

---

## 目錄結構與分層

```text
backend/app/
├── main.py                 # FastAPI 進入點
├── api/
│   ├── deps.py             # 共用依賴（DB session、當前使用者）
│   └── v1/
│       ├── router.py       # v1 總路由（掛載各資源路由）
│       ├── agents/         # Agent 管理
│       ├── skills/         # Skills 管理
│       ├── scripts/        # Script 管理（zip 打包資源）
│       ├── chat/           # 對話領域（projects / sessions / messages / memories）
│       ├── admin/          # admin 專屬（users / roles / llm-models / settings 等）
│       ├── auth/           # 登入驗證
│       ├── agent_languages/# Agent 語言清單（唯讀）
│       ├── agent_templates/# Agent 範本清單（唯讀）
│       ├── dashboard/      # 儀錶板（排行榜等）
│       ├── models/         # LLM 模型清單（唯讀）
│       ├── settings/       # 系統設定（公開部分唯讀）
│       ├── social/         # 收藏 / 社群互動（與 agents/skills/scripts 共享路徑前綴）
│       └── health.py       # 健康檢查
├── core/
│   ├── config.py           # Settings（Pydantic BaseSettings）
│   ├── database.py         # Engine、SessionLocal、連線池
│   ├── redis.py            # Redis 連線管理
│   ├── response.py         # ApiResponse / success() / failure()
│   └── exceptions.py       # AppError、全域例外 Handler
├── models/                 # SQLAlchemy ORM 模型
├── schemas/                # Pydantic Request / Response Schema（結構對映 api/v1/）
│   ├── agents/
│   ├── skills/
│   ├── scripts/
│   ├── chat/
│   ├── admin/
│   ├── auth/
│   ├── agent_languages/
│   ├── agent_templates/
│   ├── dashboard/
│   ├── models/             # LLM 模型相關 Schema（對映 api/v1/models/）
│   ├── settings/           # 系統設定相關 Schema（對映 api/v1/settings/）
│   ├── social/             # 收藏 / 社群互動 Schema（對映 social router）
│   ├── common.py           # 跨資源共用（如 VisibilityRequest）
│   └── response.py         # ApiResponse 共用 Schema
├── services/               # 業務邏輯
├── repositories/           # 資料存取（SQL 查詢）
├── clients/                # 第三方服務 Client
│   ├── openrouter/
│   ├── line/
│   └── telegram/
├── engine/                 # Agent 引擎 / RAG Pipeline
└── workers/                # 非同步任務 worker（Redis queue 消費者，由 lifespan 啟動）
```

### 分層呼叫規則

```text
api → services → repositories → models
         ↓
      clients（第三方服務）
```

- **禁止**跨層呼叫（如 api 層直接呼叫 repositories、services 直接操作 ORM model 的 query）
- `clients/` 只由 `services` 層呼叫

### 非同步 Worker

- `workers/` 由 FastAPI `lifespan` 啟動為 `asyncio.Task`，從 Redis queue 消費任務
- worker 可直接使用 `repositories`（自建 `AsyncSession`），但**禁止**反向被 `api` / `services` 呼叫
- 任務失敗須走重試 + DLQ（死信佇列），不阻塞使用者請求

---

## API 路由

- 所有 API 統一前綴 `/api/v1`
- 路徑使用 **kebab-case 複數**：`/api/v1/agent-configs`、`/api/v1/memories`
- 路徑參數使用 UID（UUID），**禁止**使用資料庫內部 `pid`

```python
# 正確
@router.get("/api/v1/agents/{agent_uid}")

# 錯誤
@router.get("/api/v1/agent/{id}")
```

### 多層資源

- 多層資源以巢狀 kebab-case 複數表達，例：`/api/v1/chat/projects`、`/api/v1/chat/sessions/{chat_session_uid}/messages`
- 前綴 `chat/` 為領域命名空間（對話領域），內部資源仍維持 kebab-case 複數（`projects`、`sessions`、`messages`、`memories`）
- 動作型端點可用動詞後綴，例：`POST /api/v1/chat/sessions/{uid}/move`（移動 session 至 project / 設為游離）

---

## Lifespan

- FastAPI **必須**使用 `lifespan` context manager 管理應用程式生命週期，**禁止**使用已棄用的 `on_event("startup")` / `on_event("shutdown")`
- 所有啟動與關閉時需執行的邏輯（DB 連線池、HTTP Client、排程器等）皆集中於 `lifespan` 內

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 啟動：初始化資源
    await database.connect()
    yield
    # 關閉：釋放資源
    await database.disconnect()

app = FastAPI(lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
```

---

## Swagger 文件

- FastAPI 初始化時**必須**明確設定 `docs_url="/api/docs"`
- **禁止**使用 `/swagger`、`/docs`、`/openapi` 等其他路徑

---

## 統一回應格式

所有 API 回應皆透過 `ApiResponse` 包裝，固定包含以下四個欄位：

| 欄位            | 型別           | 說明                                          |
| --------------- | -------------- | --------------------------------------------- |
| `success`       | `bool`         | 請求是否成功                                  |
| `data`          | `dict \| null` | 成功時的回傳資料（物件），失敗時為 `null`     |
| `detail`        | `str \| null`  | 失敗時的使用者可讀訊息，成功時為 `null`       |
| `response_code` | `int`          | 業務狀態碼（如 `200`、`400`、`404`）          |

```json
// 成功
{
  "success": true,
  "data": { "agent_uid": "xxx", "name": "My Agent" },
  "detail": null,
  "response_code": 200
}

// 失敗
{
  "success": false,
  "data": null,
  "detail": "找不到指定的 Agent",
  "response_code": 404
}
```

提供 helper 函式：

- `success(data, response_code=200)` — 成功回應
- `failure(detail, response_code=400, status_code=400)` — 失敗回應

路由**禁止**使用 `dict` 作為 response type，**必須**使用 Pydantic 模型。

### `data` 欄位規則

- `data` 只能是 `null` 或 `dict`（前端接收為 `null` 或 `Object`）
- **禁止** `data` 直接為 Array，若需回傳列表須包裝於物件內

```json
// 正確 — 列表包裝在物件的 key 中
{
  "success": true,
  "data": {
    "agents": [
      { "agent_uid": "aaa", "name": "Agent A" },
      { "agent_uid": "bbb", "name": "Agent B" }
    ],
    "total": 2
  },
  "detail": null,
  "response_code": 200
}

// 錯誤 — data 直接為 Array
{
  "success": true,
  "data": [
    { "agent_uid": "aaa", "name": "Agent A" },
    { "agent_uid": "bbb", "name": "Agent B" }
  ],
  "detail": null,
  "response_code": 200
}
```

### `detail` 安全規則

`detail` 僅提供使用者可理解的訊息，**禁止**洩漏以下內容：

- SQL 語句或資料庫錯誤明細（如 `SELECT * FROM ...`、`column "xxx" does not exist`）
- 資料表名稱、欄位名稱等資料庫結構資訊
- Python traceback 或內部堆疊資訊
- 第三方服務原始錯誤回應
- Token、密碼、API Key

未預期錯誤一律回傳通用訊息（如 `"伺服器發生錯誤，請稍後再試"`），原始錯誤詳情僅記錄於 log。

### 豁免端點

- **SSE 串流端點**（`text/event-stream`，例 `POST /chat/sessions/{uid}/messages`）豁免 `ApiResponse` 包裝；錯誤以 `event: error\ndata: {...}\n\n` 事件回報，連線建立前的錯誤仍走標準 HTTP status code + `ApiResponse`
- **檔案下載端點**（非 JSON body，例 `GET /agents/{uid}/download`）豁免 `ApiResponse` 包裝，使用 `StreamingResponse` / `Response` 直接回 body；錯誤走標準 HTTP status code + `ApiResponse`
- 豁免僅適用於上述類別，其他端點**禁止**自行豁免

---

## 關聯資源回應

Response 只要含「對其他資源的引用」，**必須**同時回傳該資源的識別碼（`*_uid`）與顯示欄位（`name` / `title` / `username` 等人類可讀名稱），**禁止**只回 uid 讓前端自行查名稱（見 [10-frontend.md § 識別碼顯示](10-frontend.md#識別碼顯示)）。

### 單一關聯（1:1 / N:1）

平鋪 uid + 顯示欄位：

```json
// 正確
{ "agent_uid": "...", "owner_uid": "...", "owner_username": "alice" }

// 錯誤 — 前端拿到 owner_uid 無法顯示名字
{ "agent_uid": "...", "owner_uid": "..." }
```

### 多對多關聯（N:M）

以物件陣列回傳，**禁止**只回 uid 陣列：

```json
// 正確
{ "agent_uid": "...", "skills": [{ "skill_uid": "...", "name": "翻譯 Skill" }] }

// 錯誤 — 前端要拿到 name 得再打一次 /skills
{ "agent_uid": "...", "skill_uids": ["..."] }
```

若需保留 uid-only 欄位供表單使用，採 additive（`skill_uids` + `skills` 併存），**禁止**以 `skill_uids` 取代 `skills`。

### 批次預取（列表端點）

列表 API 回多筆含關聯資源的資料時，**必須**批次預取（`get_*_summary_map` 模式），**禁止** N+1：

```python
# 正確 — 一次 IN 查詢
skills_map = await agent_repository.get_skills_summary_map(
    [str(a.agent_uid) for a in page.items], db
)

# 錯誤 — 迴圈內逐個查
for a in page.items:
    skills = await agent_repository.get_skills_summary(str(a.agent_uid), db)
```

### 關聯資源狀態

- 關聯資源已軟刪除（`is_deleted = TRUE`）：JOIN 時過濾掉，**不**回傳該筆；**禁止**回「(已刪除)」佔位
- 關聯資源不存在（FK 完整性破損）：視同軟刪除處理
- 關聯 name 為空字串：正常回傳，由前端決定 fallback 文字

### 請求 body 仍收 uid

`*CreateRequest` / `*UpdateRequest` 仍使用 uid 陣列（如 `skill_uids: list[str]`），由後端寫入後**自行查名稱**填回 response，不要求請求端提供 name。

---

## 例外處理

全域註冊三個例外 Handler：

| 例外類型                 | 處理方式                                  |
| ------------------------ | ----------------------------------------- |
| `AppError`               | 自定義業務錯誤，回傳對應 code 與 detail   |
| `RequestValidationError` | Pydantic 驗證失敗，回傳欄位級錯誤訊息     |
| `Exception`              | 未預期錯誤，記錄 traceback 後回傳通用錯誤 |

---

## CORS 設定

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # 從環境變數讀取
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- `allow_credentials` 固定為 `True`
- `allow_origins` 從環境變數 `CORS_ORIGINS` 讀取，**禁止**寫死

---

## Logging

- 使用 Python 標準 `logging` 模組或 `loguru`
- 記錄例外時使用 `logger.exception(...)` 以保留完整 traceback
- Log 中**禁止**出現 Token、密碼、API Key 等敏感資訊明文
- 第三方服務回應若含敏感欄位，須在記錄前過濾

---

## 第三方服務 Client

- 所有外部服務呼叫集中於 `clients/` 目錄，依服務分子目錄
- 使用 `httpx.AsyncClient` 進行非同步 HTTP 呼叫
- Client 須處理逾時、重試、錯誤轉換（將第三方錯誤轉為 `AppError`）
- **禁止**在 `services` 或 `api` 層直接呼叫外部 HTTP 端點

---

## 測試

- 資料庫相關測試**禁止** mock SQL 查詢，須使用測試資料庫執行實際查詢
- 第三方外部服務使用 `respx` 或 `MockTransport` 進行 mock
- 測試檔案放置於 `backend/tests/`，結構對映 `app/` 目錄

---

## 命名慣例

| 對象            | 慣例             | 範例                                  |
| --------------- | ---------------- | ------------------------------------- |
| 模組/檔案       | snake_case       | `agent_service.py`                    |
| 類別            | PascalCase       | `AgentService`                        |
| 函式/變數       | snake_case       | `get_agent_by_uid`                    |
| 常數            | SCREAMING_SNAKE  | `MAX_RETRY_COUNT`                     |
| API 路徑        | kebab-case 複數  | `/api/v1/agent-configs`               |
| 環境變數        | SCREAMING_SNAKE  | `OPENROUTER_API_KEY`                  |
| Pydantic Schema | PascalCase＋後綴 | `AgentCreateRequest`、`AgentResponse` |

### 函式定義規則

所有函式**必須**遵循 Python type hints 規範（PEP 484），明確標註參數型別與回傳型別：

```python
# 正確
async def get_agent_by_uid(agent_uid: str, db: AsyncSession) -> AgentResponse:
    ...

def calculate_similarity(embedding_a: list[float], embedding_b: list[float]) -> float:
    ...

# 錯誤 — 缺少型別標註
async def get_agent_by_uid(agent_uid, db):
    ...
```

- **禁止**省略參數型別或回傳型別
- **禁止**使用 `Any`，若型別不確定使用 `object` 或具體的 `Union` / `Protocol`
  - **異質容器** `dict[str, ...]` / `list[...]`（log payload、settings 字典、LLM usage 等）值型不齊時，使用 `dict[str, object]` / `list[object]`
  - **泛型 `**kwargs`**（passthrough 至下層 client 的 metering wrapper、log helper 等）使用 `**kwargs: object`
  - **DB session 透傳** 一律 import `from sqlalchemy.ext.asyncio import AsyncSession` 標註，**禁止**用 `Any` 偷懶
  - **跨型別 ORM 物件**（如三層記憶 `ChatMemory | ProjectMemory | UserMemory`）使用具名 `Protocol` 定義所需的最小欄位集合
- 回傳 `None` 的函式須明確標註 `-> None`
- 使用 Python 3.12+ 內建泛型語法（`list[str]`、`dict[str, int]`），**禁止**使用 `typing.List`、`typing.Dict`
