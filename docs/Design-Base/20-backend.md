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
│       ├── memories/       # 記憶管理
│       ├── conversations/  # 對話管理
│       ├── auth/           # 登入驗證
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
│   ├── memories/
│   ├── conversations/
│   ├── auth/
│   └── response.py         # ApiResponse 共用 Schema
├── services/               # 業務邏輯
├── repositories/           # 資料存取（SQL 查詢）
├── clients/                # 第三方服務 Client
│   ├── openrouter/
│   ├── line/
│   └── telegram/
└── engine/                 # Agent 引擎 / RAG Pipeline
```

### 分層呼叫規則

```text
api → services → repositories → models
         ↓
      clients（第三方服務）
```

- **禁止**跨層呼叫（如 api 層直接呼叫 repositories、services 直接操作 ORM model 的 query）
- `clients/` 只由 `services` 層呼叫

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
- 回傳 `None` 的函式須明確標註 `-> None`
- 使用 Python 3.12+ 內建泛型語法（`list[str]`、`dict[str, int]`），**禁止**使用 `typing.List`、`typing.Dict`
