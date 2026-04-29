# 資料庫規範

> 技術棧與版本定義參閱 [00-overview.md § 資料庫](00-overview.md#資料庫)

---

## 命名慣例

| 對象       | 慣例                   | 範例                                  |
| ---------- | ---------------------- | ------------------------------------- |
| 資料表     | 單數 snake_case        | `agent`、`memory`、`skill`            |
| 欄位       | snake_case             | `agent_uid`、`created_at`             |
| 索引       | `idx_{表}_{欄位}`      | `idx_agent_agent_uid`                 |
| 唯一索引   | `uq_{表}_{欄位}`       | `uq_user_email`、`uq_agent_agent_uid` |
| 外鍵約束   | `fk_{表}_{參考表}`     | `fk_agent_skill_agent`                |
| Trigger    | `trg_{表}_{動作}`      | `trg_agent_set_updated_at`            |

> **`{表}_uid` 唯一索引**：對外識別碼欄位（如 `agent.agent_uid`）的唯一索引一律使用完整命名 `uq_{表}_{表}_uid`（例 `uq_agent_agent_uid`、`uq_llm_model_llm_model_uid`）；**禁止**簡寫為 `uq_{表}_uid`。
>
> 即使表名本身已含 `uid` / `_id` 字尾或長度較長（如 `agentic_skill_suggestion` → `uq_agentic_skill_suggestion_agentic_skill_suggestion_uid`），仍**必須**完整重複表名，不開放例外，以維持 `grep "uq_{表}"` 直接定位的單一規則。歷史 migration 漏寫者，建立新 V 號 `ALTER INDEX RENAME TO` 修正（範例：[V49](../../migrations/sql/V49__rename_agentic_skill_suggestion_uid_index.sql)）。
>
> **`set_updated_at` Trigger**：各表的 `updated_at` 維護 Trigger 命名一律為 `trg_{表}_set_updated_at`（例 `trg_agent_set_updated_at`），不可省略 `set_` 中綴。

---

## 必備欄位

每張業務資料表**必須**包含以下六個欄位：

| 欄位         | 型別                     | 說明                                         |
| ------------ | ------------------------ | -------------------------------------------- |
| `pid`        | `BIGSERIAL PRIMARY KEY`  | 內部自增主鍵，**禁止**對外暴露               |
| `{表}_uid`   | `UUID DEFAULT gen_random_uuid()` | 對外唯一識別碼，API 路徑與前端皆使用此欄位 |
| `is_active`  | `BOOLEAN DEFAULT TRUE`   | 資料是否啟用                                 |
| `is_deleted` | `BOOLEAN DEFAULT FALSE`  | 軟刪除標記                                   |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | 建立時間                                  |
| `updated_at` | `TIMESTAMPTZ DEFAULT NOW()` | 更新時間，由 Trigger 自動維護              |

每個欄位**必須**使用 `COMMENT ON COLUMN` 加上中文說明，**禁止**省略。

### 審計表豁免（純 append-only / 快照）

少數「寫入即不可變」的表允許豁免部分必備欄位：

- 純 append-only 審計表（不編輯、不軟刪除）可省略 `updated_at`、`is_deleted`，例：`chat_message`（對話訊息，審計用）
- 一次寫入的記憶快照表（內容不更新、整筆跟隨父資源硬刪）可再省略 `is_active`，例：`chat_memory`（Session 隨 Session 軟刪時一併刪除）
- 豁免表**仍必須**保留 `pid`、`{表}_uid`、`created_at`，並於 `COMMENT ON TABLE` 中註明為「審計用 / 快照」
- 其他業務表**無**豁免

```sql
-- 範例：agent 資料表
CREATE TABLE agent (
    pid         BIGSERIAL    PRIMARY KEY,
    agent_uid   UUID         NOT NULL DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_agent_agent_uid ON agent (agent_uid);

COMMENT ON TABLE  agent                IS 'Agent 定義表';
COMMENT ON COLUMN agent.pid            IS '內部自增主鍵';
COMMENT ON COLUMN agent.agent_uid      IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN agent.name           IS 'Agent 名稱';
COMMENT ON COLUMN agent.is_active      IS '是否啟用';
COMMENT ON COLUMN agent.is_deleted     IS '是否軟刪除';
COMMENT ON COLUMN agent.created_at     IS '建立時間';
COMMENT ON COLUMN agent.updated_at     IS '更新時間（Trigger 自動維護）';
```

### 時區（重要）

- 所有 `TIMESTAMPTZ` 欄位儲存的值**即為 UTC+8 的 wall-clock 時間**，不做時區換算
- PostgreSQL session 時區設定為 `Asia/Taipei`，`NOW()` 直接寫入 UTC+8 值
- 後端讀取後序列化為 ISO 字串傳給前端；**前端禁止使用 `new Date()` / `toLocaleString` 做時區轉換**，否則會再被瀏覽器偏移一次
- 前端顯示統一使用 [`utils/datetime.ts`](../../frontend/src/utils/datetime.ts) 的 `formatDateTime()`，直接由 ISO 字串切出 `Y/M/D h:m:s`

### `updated_at` Trigger

所有業務表**必須**掛載 `set_updated_at` Trigger，確保 `updated_at` 自動更新：

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 每張表各建一個 Trigger
CREATE TRIGGER trg_agent_set_updated_at
    BEFORE UPDATE ON agent
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
```

---

## 主鍵與對外識別

- 內部主鍵使用 `pid`（`BIGSERIAL`），僅供資料庫內部關聯與索引
- 對外識別一律使用 `{表}_uid`（`UUID`），API 路徑、前端顯示皆使用 UID
- **禁止**將 `pid` 暴露於 API 回應或前端
- 外部系統的 ID（如第三方服務回傳的 id）以獨立欄位儲存（如 `remote_agent_id`），**禁止**作為本地主鍵或對外 UID

---

## 軟刪除

- 刪除操作一律使用軟刪除（設定 `is_deleted = TRUE`），**禁止**物理刪除業務資料
- SQLAlchemy 查詢**必須**預設過濾 `is_deleted == False`，避免查出已刪除資料
- Repository 層提供基礎查詢方法時須內建此過濾條件

```python
# Repository 基礎查詢範例
async def get_by_uid(self, uid: str, db: AsyncSession) -> Agent | None:
    stmt = select(Agent).where(Agent.agent_uid == uid, Agent.is_deleted == False)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

---

## 連線管理

- **必須**使用連線池，**禁止**每次請求建立新連線
- 使用 SQLAlchemy `create_async_engine` 搭配連線池參數
- 連線池參數透過環境變數設定

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

---

## 向量資料庫（pgvector）

- 使用 PostgreSQL pgvector 擴充儲存與檢索向量嵌入（Embedding）
- 向量欄位使用 `VECTOR(維度)` 型別，維度依所選嵌入模型決定
- 建立向量索引以加速相似度搜尋

```sql
-- 啟用擴充
CREATE EXTENSION IF NOT EXISTS vector;

-- 向量欄位加入業務資料表（建表結構遵循 § 必備欄位）
-- 範例：embedding VECTOR(1536)

-- HNSW 索引
CREATE INDEX idx_memory_embedding ON memory
    USING hnsw (embedding vector_cosine_ops);
```

- 語意搜尋使用餘弦相似度（`<=>`）查詢最近鄰向量
- 向量索引類型選擇：資料量小用 IVFFlat，資料量大或需高召回率用 HNSW

---

## Redis

- 用途：快取、Session 管理、任務佇列
- 連線透過 `redis.asyncio` 管理，於 lifespan 中初始化與關閉
- Key 命名統一格式：`{模組}:{資源}:{識別碼}`，例如 `session:{user_uid}`、`cache:agent:{agent_uid}`
- **必須**為所有快取 Key 設定 TTL，**禁止**無過期時間的快取

---

## Migration（Flyway）

- Migration 檔案放置於 `migrations/sql/`
- 檔名格式：`V{版號}__{描述}.sql`，版號為整數遞增，描述使用 snake_case

```text
migrations/sql/
├── V1__create_extension_pgvector.sql
├── V2__create_updated_at_function.sql
├── V3__create_user_role_table.sql
├── V4__create_user_table.sql
├── V5__create_agent_table.sql
├── V6__create_agent_skill_table.sql
└── V7__create_skill_table.sql
```

- 每個 Migration 檔案只做一件事（建表、加欄位、建索引等）
- **禁止**修改已合併至 `main` 的 Migration 檔案，需變更時建立新的 Migration
- Migration 須為冪等操作，使用 `IF NOT EXISTS` / `IF EXISTS` 防護

---

## SQLAlchemy Model 規範

- 所有 Model 繼承統一的 `Base` 類別，`Base` 內建必備欄位（`pid`、`is_active`、`is_deleted`、`created_at`、`updated_at`）
- `{表}_uid` 欄位由各 Model 自行定義（欄位名隨表名變動）
- 使用 `mapped_column` 語法（SQLAlchemy 2 風格）

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, Boolean, DateTime, func
from datetime import datetime


class Base(DeclarativeBase):
    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### 審計表獨立 DeclarativeBase 豁免

- 審計表（§ 必備欄位 § 審計表豁免）允許使用獨立 `DeclarativeBase`（例 `MessageBase`、`MemoryBase`），以排除 `updated_at` / `is_deleted` 等欄位
- 跨 base 的外鍵**僅**在 DB migration 層以 `FOREIGN KEY` constraint 保證；Python 層**禁止**使用 `ForeignKey(...)` 標記（跨 metadata 會在 `flush()` 時拋 `NoReferencedTableError`）
- 獨立 base 的 ORM 關係（如 `relationship`）亦不可跨 base，需要關聯時改用顯式 query
