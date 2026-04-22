-- ============================================================
-- Snapshot V1__init.sql
-- 匯出時間：2026-04-22
-- 來源：Agents-Memory-System dev DB（已套用 V1~V32 + 當前業務資料）
--
-- 用途：將本檔複製到其他乾淨 DB 作為單一 Bootstrap migration 使用，
--       一次建立所有 schema、函式、trigger、index、FK，並寫入預設資料。
--
-- 使用方式：
--   1. 新專案以空 DB 起手，將此檔放在 migrations/sql/V1__init.sql。
--   2. 必須已安裝 pgvector extension（本檔會 CREATE EXTENSION IF NOT EXISTS vector）。
--   3. 執行 Flyway migrate 後，DB 即等同於原專案 V32 後的狀態。
--
-- 注意：
--   * 包含完整 schema（14 tables + function set_updated_at + triggers + indexes + FKs）。
--   * 包含目前業務資料（users / agents / skills / templates / system_settings 等）。
--   * 使用者 hashed_password 已保留；若不需要可在匯入後手動刪除或覆寫。
--   * 已去除 pg_dump 的 SET / \restrict / OWNER TO / GRANT 指令，由 Flyway 自行管理權限。
-- ============================================================

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent (
    pid bigint NOT NULL,
    agent_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_uid uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    language character varying(50),
    style character varying(50),
    identity character varying(200),
    role_prompt text,
    visibility character varying(10) DEFAULT 'private'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    model character varying(100),
    temperature double precision,
    max_tokens integer,
    greeting text,
    response_format character varying(20) DEFAULT 'markdown'::character varying,
    response_format_example text,
    CONSTRAINT chk_agent_visibility CHECK (((visibility)::text = ANY ((ARRAY['public'::character varying, 'private'::character varying])::text[])))
);


--
-- Name: TABLE agent; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.agent IS 'AI Agent 設定表';


--
-- Name: COLUMN agent.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.pid IS '內部自增主鍵，不對外暴露';


--
-- Name: COLUMN agent.agent_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.agent_uid IS 'Agent 的外部唯一識別碼（UUID）';


--
-- Name: COLUMN agent.owner_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.owner_uid IS '擁有者，對應 user.user_uid';


--
-- Name: COLUMN agent.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.name IS 'Agent 名稱，最長 100 字元';


--
-- Name: COLUMN agent.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.description IS 'Agent 描述說明';


--
-- Name: COLUMN agent.language; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.language IS '語言偏好，如「繁體中文」';


--
-- Name: COLUMN agent.style; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.style IS '回答風格，如「專業」、「友善」';


--
-- Name: COLUMN agent.identity; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.identity IS 'Agent 身分設定';


--
-- Name: COLUMN agent.role_prompt; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.role_prompt IS '角色系統提示詞（System Prompt）';


--
-- Name: COLUMN agent.visibility; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.visibility IS '可見性：public（公開）或 private（私人）';


--
-- Name: COLUMN agent.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.is_active IS '是否啟用';


--
-- Name: COLUMN agent.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN agent.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.created_at IS '建立時間（UTC）';


--
-- Name: COLUMN agent.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.updated_at IS '最後更新時間（UTC）';


--
-- Name: COLUMN agent.model; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.model IS '使用的 LLM 模型 ID，對應 llm_model.model_id';


--
-- Name: COLUMN agent.temperature; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.temperature IS '生成溫度，0=確定性高，2=隨機性高';


--
-- Name: COLUMN agent.max_tokens; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.max_tokens IS '單次回覆最大 Token 數';


--
-- Name: COLUMN agent.greeting; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.greeting IS 'Agent 開場白，對話開始時的第一句話';


--
-- Name: COLUMN agent.response_format; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.response_format IS '回覆格式：markdown / plain_text / json';


--
-- Name: COLUMN agent.response_format_example; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent.response_format_example IS '當 response_format=json 時，使用者提供的範例結構，附加到 system prompt 指引 LLM 輸出格式';


--
-- Name: agent_language; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_language (
    pid bigint NOT NULL,
    agent_language_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(50) NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE agent_language; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.agent_language IS 'Agent 語言偏好選項表';


--
-- Name: COLUMN agent_language.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.pid IS '內部自增主鍵，不對外暴露';


--
-- Name: COLUMN agent_language.agent_language_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.agent_language_uid IS '對外唯一識別碼（UUID）';


--
-- Name: COLUMN agent_language.code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.code IS '語系碼（如 zh-TW、en），儲存於 agent.language';


--
-- Name: COLUMN agent_language.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.name IS '顯示名稱（如 繁體中文）';


--
-- Name: COLUMN agent_language.sort_order; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.sort_order IS '下拉選單排序，數字越小越前面';


--
-- Name: COLUMN agent_language.is_default; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.is_default IS '是否為預設語言（全表唯一）';


--
-- Name: COLUMN agent_language.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.is_active IS '是否啟用，停用後不出現在 member 端清單';


--
-- Name: COLUMN agent_language.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN agent_language.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.created_at IS '建立時間';


--
-- Name: COLUMN agent_language.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_language.updated_at IS '更新時間（Trigger 自動維護）';


--
-- Name: agent_language_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_language_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_language_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_language_pid_seq OWNED BY public.agent_language.pid;


--
-- Name: agent_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_pid_seq OWNED BY public.agent.pid;


--
-- Name: agent_skill; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_skill (
    agent_uid uuid NOT NULL,
    skill_uid uuid NOT NULL
);


--
-- Name: TABLE agent_skill; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.agent_skill IS 'Agent 與 Skill 的多對多關聯表';


--
-- Name: COLUMN agent_skill.agent_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_skill.agent_uid IS '對應 agent.agent_uid';


--
-- Name: COLUMN agent_skill.skill_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_skill.skill_uid IS '對應 skill.skill_uid';


--
-- Name: agent_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_template (
    pid bigint NOT NULL,
    agent_template_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    template_key character varying(50) NOT NULL,
    label character varying(100) NOT NULL,
    description character varying(500),
    name character varying(100),
    identity character varying(200),
    language character varying(20),
    style character varying(50),
    role_prompt text,
    greeting text,
    temperature double precision,
    max_tokens integer,
    response_format character varying(20) DEFAULT 'markdown'::character varying,
    response_format_example text,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE agent_template; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.agent_template IS 'Agent 範本表（admin 統一管理，member 套用到建立 Agent 表單）';


--
-- Name: COLUMN agent_template.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.pid IS '內部自增主鍵';


--
-- Name: COLUMN agent_template.agent_template_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.agent_template_uid IS '對外唯一識別碼';


--
-- Name: COLUMN agent_template.template_key; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.template_key IS '範本識別碼（英數短名，不可重複）';


--
-- Name: COLUMN agent_template.label; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.label IS '範本在選單顯示的名稱';


--
-- Name: COLUMN agent_template.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.description IS '範本描述，同時填入 agent.description';


--
-- Name: COLUMN agent_template.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.name IS '套用至 agent.name';


--
-- Name: COLUMN agent_template.identity; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.identity IS '套用至 agent.identity';


--
-- Name: COLUMN agent_template.language; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.language IS '套用至 agent.language（對應 agent_language.code）';


--
-- Name: COLUMN agent_template.style; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.style IS '套用至 agent.style';


--
-- Name: COLUMN agent_template.role_prompt; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.role_prompt IS '套用至 agent.role_prompt';


--
-- Name: COLUMN agent_template.greeting; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.greeting IS '套用至 agent.greeting';


--
-- Name: COLUMN agent_template.temperature; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.temperature IS '套用至 agent.temperature';


--
-- Name: COLUMN agent_template.max_tokens; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.max_tokens IS '套用至 agent.max_tokens';


--
-- Name: COLUMN agent_template.response_format; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.response_format IS '套用至 agent.response_format';


--
-- Name: COLUMN agent_template.response_format_example; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.response_format_example IS '套用至 agent.response_format_example（僅 response_format=json 使用）';


--
-- Name: COLUMN agent_template.sort_order; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.sort_order IS '選單排序，數字越小越前面';


--
-- Name: COLUMN agent_template.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.is_active IS '是否啟用（停用後 member 端不顯示）';


--
-- Name: COLUMN agent_template.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.agent_template.is_deleted IS '軟刪除';


--
-- Name: agent_template_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_template_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_template_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_template_pid_seq OWNED BY public.agent_template.pid;


--
-- Name: chat_attachment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_attachment (
    pid bigint NOT NULL,
    chat_attachment_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_user_uid uuid NOT NULL,
    chat_session_uid uuid NOT NULL,
    file_name character varying(255) NOT NULL,
    file_type character varying(100) NOT NULL,
    file_size bigint NOT NULL,
    file_path text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE chat_attachment; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.chat_attachment IS '對話附件表（圖片 / 文字檔），儲存附件 metadata 與本機檔案路徑';


--
-- Name: COLUMN chat_attachment.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.pid IS '內部自增主鍵';


--
-- Name: COLUMN chat_attachment.chat_attachment_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.chat_attachment_uid IS '對外唯一識別碼（UUID）';


--
-- Name: COLUMN chat_attachment.owner_user_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.owner_user_uid IS '上傳者 user_uid';


--
-- Name: COLUMN chat_attachment.chat_session_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.chat_session_uid IS '所屬 Session UID';


--
-- Name: COLUMN chat_attachment.file_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.file_name IS '使用者上傳時的原始檔名';


--
-- Name: COLUMN chat_attachment.file_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.file_type IS 'MIME type（例：image/png、text/markdown）';


--
-- Name: COLUMN chat_attachment.file_size; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.file_size IS '檔案大小（bytes）';


--
-- Name: COLUMN chat_attachment.file_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.file_path IS '本機儲存路徑（data/attachments/{yyyymm}/{uid}.{ext}）';


--
-- Name: COLUMN chat_attachment.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.is_active IS '是否啟用';


--
-- Name: COLUMN chat_attachment.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN chat_attachment.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.created_at IS '建立時間';


--
-- Name: COLUMN chat_attachment.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_attachment.updated_at IS '更新時間（Trigger 自動維護）';


--
-- Name: chat_attachment_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_attachment_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_attachment_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_attachment_pid_seq OWNED BY public.chat_attachment.pid;


--
-- Name: chat_memory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_memory (
    pid bigint NOT NULL,
    chat_memory_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    chat_session_uid uuid NOT NULL,
    source_chat_message_uids uuid[] NOT NULL,
    keywords text[] DEFAULT '{}'::text[] NOT NULL,
    entities text[] DEFAULT '{}'::text[] NOT NULL,
    topic character varying(200),
    embedding public.vector(1536) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE chat_memory; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.chat_memory IS '對話記憶表（Session 層，隨 Session 軟刪而 hard delete）';


--
-- Name: COLUMN chat_memory.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.pid IS '內部自增主鍵';


--
-- Name: COLUMN chat_memory.chat_memory_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.chat_memory_uid IS '對外唯一識別碼（UUID）';


--
-- Name: COLUMN chat_memory.chat_session_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.chat_session_uid IS '所屬 Session UID';


--
-- Name: COLUMN chat_memory.source_chat_message_uids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.source_chat_message_uids IS '來源訊息 UID 陣列（批次摘要）';


--
-- Name: COLUMN chat_memory.keywords; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.keywords IS '關鍵字列表（小模型抽取）';


--
-- Name: COLUMN chat_memory.entities; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.entities IS '實體列表（人名 / 地點 / 概念）';


--
-- Name: COLUMN chat_memory.topic; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.topic IS '主題描述（摘要標題）';


--
-- Name: COLUMN chat_memory.embedding; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.embedding IS '向量（text-embedding-3-small，1536 維）';


--
-- Name: COLUMN chat_memory.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_memory.created_at IS '建立時間';


--
-- Name: chat_memory_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_memory_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_memory_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_memory_pid_seq OWNED BY public.chat_memory.pid;


--
-- Name: chat_message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_message (
    pid bigint NOT NULL,
    chat_message_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    chat_session_uid uuid NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    token_in integer,
    token_out integer,
    cost_usd numeric(10,6),
    model character varying(100),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    finish_reason character varying(20),
    attachment_uids uuid[],
    CONSTRAINT chk_chat_message_role CHECK (((role)::text = ANY ((ARRAY['user'::character varying, 'assistant'::character varying, 'system'::character varying, 'tool'::character varying])::text[])))
);


--
-- Name: TABLE chat_message; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.chat_message IS '對話訊息表（不可編輯、不軟刪除，審計用）';


--
-- Name: COLUMN chat_message.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.pid IS '內部自增主鍵';


--
-- Name: COLUMN chat_message.chat_message_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.chat_message_uid IS '對外唯一識別碼（UUID）';


--
-- Name: COLUMN chat_message.chat_session_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.chat_session_uid IS '所屬 Session UID';


--
-- Name: COLUMN chat_message.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.role IS '角色（user / assistant / system / tool）';


--
-- Name: COLUMN chat_message.content; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.content IS '訊息內容';


--
-- Name: COLUMN chat_message.token_in; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.token_in IS '輸入 token 數（assistant 訊息才有值）';


--
-- Name: COLUMN chat_message.token_out; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.token_out IS '輸出 token 數（assistant 訊息才有值）';


--
-- Name: COLUMN chat_message.cost_usd; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.cost_usd IS '本次請求成本（美元，assistant 訊息才有值）';


--
-- Name: COLUMN chat_message.model; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.model IS '實際呼叫的 model id（user / system 訊息為 NULL）';


--
-- Name: COLUMN chat_message.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.is_active IS '是否啟用（保留欄位，目前固定 TRUE）';


--
-- Name: COLUMN chat_message.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.created_at IS '建立時間';


--
-- Name: COLUMN chat_message.finish_reason; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.finish_reason IS 'OpenRouter finish_reason（stop / length / tool_calls 等；NULL 代表歷史訊息或非 assistant 角色）';


--
-- Name: COLUMN chat_message.attachment_uids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_message.attachment_uids IS '訊息攜帶的附件 UID 陣列（對應 chat_attachment.chat_attachment_uid），無附件時為 NULL';


--
-- Name: chat_message_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_message_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_message_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_message_pid_seq OWNED BY public.chat_message.pid;


--
-- Name: chat_project; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_project (
    pid bigint NOT NULL,
    chat_project_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_user_uid uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE chat_project; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.chat_project IS '對話 Project 容器表';


--
-- Name: COLUMN chat_project.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.pid IS '內部自增主鍵';


--
-- Name: COLUMN chat_project.chat_project_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.chat_project_uid IS '對外唯一識別碼（UUID）';


--
-- Name: COLUMN chat_project.owner_user_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.owner_user_uid IS '擁有者 user_uid';


--
-- Name: COLUMN chat_project.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.name IS 'Project 名稱（1-100 字元）';


--
-- Name: COLUMN chat_project.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.description IS 'Project 描述';


--
-- Name: COLUMN chat_project.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.is_active IS '是否啟用';


--
-- Name: COLUMN chat_project.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN chat_project.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.created_at IS '建立時間';


--
-- Name: COLUMN chat_project.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_project.updated_at IS '更新時間（Trigger 自動維護）';


--
-- Name: chat_project_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_project_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_project_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_project_pid_seq OWNED BY public.chat_project.pid;


--
-- Name: chat_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_session (
    pid bigint NOT NULL,
    chat_session_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    chat_project_uid uuid,
    agent_uid uuid NOT NULL,
    title character varying(200) DEFAULT '未命名對話'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    owner_user_uid uuid NOT NULL
);


--
-- Name: TABLE chat_session; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.chat_session IS '對話 Session 表（1 session 對 1 agent）';


--
-- Name: COLUMN chat_session.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.pid IS '內部自增主鍵';


--
-- Name: COLUMN chat_session.chat_session_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.chat_session_uid IS '對外唯一識別碼（UUID）';


--
-- Name: COLUMN chat_session.chat_project_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.chat_project_uid IS '所屬 Project UID（NULL 代表游離對話，不屬於任何 Project）';


--
-- Name: COLUMN chat_session.agent_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.agent_uid IS '綁定的 Agent UID（建立後不可變更）';


--
-- Name: COLUMN chat_session.title; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.title IS 'Session 標題，首則訊息自動帶入前 30 字';


--
-- Name: COLUMN chat_session.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.is_active IS '是否啟用';


--
-- Name: COLUMN chat_session.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN chat_session.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.created_at IS '建立時間';


--
-- Name: COLUMN chat_session.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.updated_at IS '更新時間（Trigger 自動維護）';


--
-- Name: COLUMN chat_session.owner_user_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chat_session.owner_user_uid IS 'Session 擁有者 UID（v1.1.4 起獨立於 chat_project，供游離 session 直接查擁有權）';


--
-- Name: chat_session_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_session_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_session_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_session_pid_seq OWNED BY public.chat_session.pid;


--
-- Name: llm_model; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_model (
    pid bigint NOT NULL,
    llm_model_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    provider character varying(50) NOT NULL,
    model_id character varying(100) NOT NULL,
    display_name character varying(100) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    max_output_tokens integer
);


--
-- Name: TABLE llm_model; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.llm_model IS 'LLM 模型清單，供 Agent 選用';


--
-- Name: COLUMN llm_model.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.pid IS '內部自增主鍵，不對外暴露';


--
-- Name: COLUMN llm_model.llm_model_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.llm_model_uid IS '模型的外部唯一識別碼（UUID）';


--
-- Name: COLUMN llm_model.provider; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.provider IS '模型提供商（統一為 OpenRouter，對應 tasks-v1.0.1.md §已確認決策 #1）';


--
-- Name: COLUMN llm_model.model_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.model_id IS '模型完整 ID，如 openai/gpt-4o，全站唯一';


--
-- Name: COLUMN llm_model.display_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.display_name IS '模型顯示名稱，供前端下拉選單使用';


--
-- Name: COLUMN llm_model.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.is_active IS '是否啟用，停用後不出現在選單中';


--
-- Name: COLUMN llm_model.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN llm_model.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.created_at IS '建立時間（UTC）';


--
-- Name: COLUMN llm_model.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.updated_at IS '最後更新時間（UTC）';


--
-- Name: COLUMN llm_model.is_default; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.is_default IS '是否為系統預設模型（全表唯一）';


--
-- Name: COLUMN llm_model.max_output_tokens; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_model.max_output_tokens IS '單次回覆最大 Token 數（NULL 表示未設定）';


--
-- Name: llm_model_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_model_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_model_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_model_pid_seq OWNED BY public.llm_model.pid;


--
-- Name: skill; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill (
    pid bigint NOT NULL,
    skill_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_uid uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text NOT NULL,
    file_path character varying(500) NOT NULL,
    original_filename character varying(255) NOT NULL,
    file_size bigint NOT NULL,
    visibility character varying(10) DEFAULT 'private'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_skill_visibility CHECK (((visibility)::text = ANY ((ARRAY['public'::character varying, 'private'::character varying])::text[])))
);


--
-- Name: TABLE skill; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.skill IS 'Skills 模組表';


--
-- Name: COLUMN skill.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.pid IS '內部自增主鍵，不對外暴露';


--
-- Name: COLUMN skill.skill_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.skill_uid IS 'Skill 的外部唯一識別碼（UUID）';


--
-- Name: COLUMN skill.owner_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.owner_uid IS '擁有者，對應 user.user_uid';


--
-- Name: COLUMN skill.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.name IS 'Skill 名稱，最長 100 字元';


--
-- Name: COLUMN skill.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.description IS 'Skill 功能描述（必填）';


--
-- Name: COLUMN skill.file_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.file_path IS '伺服器端檔案儲存路徑';


--
-- Name: COLUMN skill.original_filename; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.original_filename IS '使用者上傳時的原始檔名';


--
-- Name: COLUMN skill.file_size; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.file_size IS '檔案大小（位元組）';


--
-- Name: COLUMN skill.visibility; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.visibility IS '可見性：public（公開）或 private（私人）';


--
-- Name: COLUMN skill.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.is_active IS '是否啟用';


--
-- Name: COLUMN skill.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN skill.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.created_at IS '建立時間（UTC）';


--
-- Name: COLUMN skill.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.skill.updated_at IS '最後更新時間（UTC）';


--
-- Name: skill_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.skill_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: skill_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.skill_pid_seq OWNED BY public.skill.pid;


--
-- Name: system_setting; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_setting (
    pid bigint NOT NULL,
    system_setting_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    key character varying(100) NOT NULL,
    value text NOT NULL,
    value_type character varying(20) DEFAULT 'string'::character varying NOT NULL,
    description text,
    is_public boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE system_setting; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.system_setting IS '系統可調設定（key/value）表';


--
-- Name: COLUMN system_setting.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.pid IS '內部自增主鍵，不對外暴露';


--
-- Name: COLUMN system_setting.system_setting_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.system_setting_uid IS '對外唯一識別碼（UUID）';


--
-- Name: COLUMN system_setting.key; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.key IS '設定鍵（如 agent.max_skills）';


--
-- Name: COLUMN system_setting.value; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.value IS '設定值（統一以字串儲存，由服務層按 value_type 解析）';


--
-- Name: COLUMN system_setting.value_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.value_type IS '值型別（string / integer / boolean / json）';


--
-- Name: COLUMN system_setting.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.description IS '設定說明';


--
-- Name: COLUMN system_setting.is_public; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.is_public IS '是否可由 member 讀取（true 出現在 /api/v1/settings/public）';


--
-- Name: COLUMN system_setting.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.is_active IS '是否啟用';


--
-- Name: COLUMN system_setting.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.is_deleted IS '軟刪除標記';


--
-- Name: COLUMN system_setting.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.created_at IS '建立時間';


--
-- Name: COLUMN system_setting.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.system_setting.updated_at IS '更新時間（Trigger 自動維護）';


--
-- Name: system_setting_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_setting_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_setting_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_setting_pid_seq OWNED BY public.system_setting.pid;


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    pid bigint NOT NULL,
    user_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    username character varying(50) NOT NULL,
    account character varying(100) NOT NULL,
    hashed_password character varying(200) NOT NULL,
    role_uid uuid NOT NULL,
    login_fail_count integer DEFAULT 0 NOT NULL,
    locked_until timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE "user"; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public."user" IS '使用者帳號表';


--
-- Name: COLUMN "user".pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".pid IS '內部自增主鍵，不對外暴露';


--
-- Name: COLUMN "user".user_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".user_uid IS '使用者的外部唯一識別碼（UUID）';


--
-- Name: COLUMN "user".username; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".username IS '使用者顯示名稱，2-50 字元';


--
-- Name: COLUMN "user".account; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".account IS '登入帳號，≥8 字元，含字母與數字，全站唯一';


--
-- Name: COLUMN "user".hashed_password; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".hashed_password IS 'bcrypt 雜湊後的密碼，禁止明文儲存';


--
-- Name: COLUMN "user".role_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".role_uid IS '對應 user_role.user_role_uid 的外鍵';


--
-- Name: COLUMN "user".login_fail_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".login_fail_count IS '連續登入失敗次數，成功登入後歸零';


--
-- Name: COLUMN "user".locked_until; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".locked_until IS '帳號鎖定到期時間，NULL 表示未鎖定';


--
-- Name: COLUMN "user".is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".is_active IS '是否啟用，停用後無法登入';


--
-- Name: COLUMN "user".is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".is_deleted IS '軟刪除標記';


--
-- Name: COLUMN "user".created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".created_at IS '建立時間（UTC）';


--
-- Name: COLUMN "user".updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public."user".updated_at IS '最後更新時間（UTC）';


--
-- Name: user_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_pid_seq OWNED BY public."user".pid;


--
-- Name: user_role; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_role (
    pid bigint NOT NULL,
    user_role_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(50) NOT NULL,
    description character varying(200),
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE user_role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.user_role IS '使用者角色定義表';


--
-- Name: COLUMN user_role.pid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.pid IS '內部自增主鍵，不對外暴露';


--
-- Name: COLUMN user_role.user_role_uid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.user_role_uid IS '角色的外部唯一識別碼（UUID）';


--
-- Name: COLUMN user_role.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.name IS '角色名稱，如 admin、member';


--
-- Name: COLUMN user_role.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.description IS '角色說明文字';


--
-- Name: COLUMN user_role.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.is_active IS '是否啟用，停用後無法被指派';


--
-- Name: COLUMN user_role.is_deleted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.is_deleted IS '軟刪除標記，true 表示已刪除';


--
-- Name: COLUMN user_role.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.created_at IS '建立時間（UTC）';


--
-- Name: COLUMN user_role.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_role.updated_at IS '最後更新時間（UTC），由 Trigger 自動維護';


--
-- Name: user_role_pid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_role_pid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_role_pid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_role_pid_seq OWNED BY public.user_role.pid;


--
-- Name: agent pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent ALTER COLUMN pid SET DEFAULT nextval('public.agent_pid_seq'::regclass);


--
-- Name: agent_language pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_language ALTER COLUMN pid SET DEFAULT nextval('public.agent_language_pid_seq'::regclass);


--
-- Name: agent_template pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_template ALTER COLUMN pid SET DEFAULT nextval('public.agent_template_pid_seq'::regclass);


--
-- Name: chat_attachment pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_attachment ALTER COLUMN pid SET DEFAULT nextval('public.chat_attachment_pid_seq'::regclass);


--
-- Name: chat_memory pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_memory ALTER COLUMN pid SET DEFAULT nextval('public.chat_memory_pid_seq'::regclass);


--
-- Name: chat_message pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message ALTER COLUMN pid SET DEFAULT nextval('public.chat_message_pid_seq'::regclass);


--
-- Name: chat_project pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_project ALTER COLUMN pid SET DEFAULT nextval('public.chat_project_pid_seq'::regclass);


--
-- Name: chat_session pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_session ALTER COLUMN pid SET DEFAULT nextval('public.chat_session_pid_seq'::regclass);


--
-- Name: llm_model pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_model ALTER COLUMN pid SET DEFAULT nextval('public.llm_model_pid_seq'::regclass);


--
-- Name: skill pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill ALTER COLUMN pid SET DEFAULT nextval('public.skill_pid_seq'::regclass);


--
-- Name: system_setting pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_setting ALTER COLUMN pid SET DEFAULT nextval('public.system_setting_pid_seq'::regclass);


--
-- Name: user pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user" ALTER COLUMN pid SET DEFAULT nextval('public.user_pid_seq'::regclass);


--
-- Name: user_role pid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_role ALTER COLUMN pid SET DEFAULT nextval('public.user_role_pid_seq'::regclass);


--
-- Data for Name: agent; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.agent (pid, agent_uid, owner_uid, name, description, language, style, identity, role_prompt, visibility, is_active, is_deleted, created_at, updated_at, model, temperature, max_tokens, greeting, response_format, response_format_example) VALUES (2, 'd742b9df-1554-43f1-af76-edefe11407f0', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118', 'Code Reviewer', '針對使用者提供的程式碼，給出結構化且可行動的審查意見。', 'zh-TW', '嚴謹、客觀、以證據為本', '資深技術主管，負責多語言程式碼審查', '請以資深技術主管的角度審查使用者提供的程式碼。請依下列結構回覆：
- 總評（2 至 3 句概述整體品質）
- 必改（Bug、安全性、正確性）
- 建議改進（可讀性、效能、測試）
- 亮點（值得保留的優點）
審查時請指出具體行號或片段，避免空泛評論。', 'public', true, false, '2026-04-22 13:27:54.43285+00', '2026-04-22 14:04:54.819529+00', 'anthropic/claude-sonnet-4', 0.7, 8192, '您好，請貼上您想審查的程式碼，我會提供結構化的意見。', 'plain_text', NULL);
INSERT INTO public.agent (pid, agent_uid, owner_uid, name, description, language, style, identity, role_prompt, visibility, is_active, is_deleted, created_at, updated_at, model, temperature, max_tokens, greeting, response_format, response_format_example) VALUES (1, '6fafa3a2-11fc-4785-a54f-56b877d6bada', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118', 'AI 新聞助手', '抓取最新的科技新聞資料', 'zh-TW', '專業、精確、客觀', '專業科技新聞記者', '# 主要任務
- 彙整使用者指定領域（AI、半導體、雲端、資安等）的最新科技新聞
- 摘要重點、比較不同來源說法、標示時間軸
- 指出報導中的事實、推測與官方聲明之差異

# 工作流程
1. 先確認使用者關心的主題、時間範圍、想知道的深度（速覽 / 深度）
2. 回覆時以「發生了什麼 → 為什麼重要 → 各方反應」三段式組織
3. 若資料不足或時效過期，主動說明並建議查證方向

# 輸出規則
- 每則新聞附上來源名稱與發佈日期（例：TechCrunch, 2026-04-18）
- 數字、引述、人名、公司名必須精確，不確定就不寫
- 預設速覽模式（≤300 字）；使用者要求才展開深度分析

# 限制
- 不捏造新聞、不使用未具名「業內消息」作為事實
- 政治立場、公司評價保持中立；只陳述已報導的事實
- 遇到尚未發生的推測性內容，明確標註「分析／推測」
- 僅需要搜尋最新的前 3 篇即可', 'public', true, false, '2026-04-21 13:46:51.711808+00', '2026-04-22 13:26:28.821242+00', 'anthropic/claude-sonnet-4', 0.7, 1024, '你好~ 我是一位專業科技新聞記者', 'plain_text', NULL);


--
-- Data for Name: agent_language; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.agent_language (pid, agent_language_uid, code, name, sort_order, is_default, is_active, is_deleted, created_at, updated_at) VALUES (1, '0a715879-bc3b-4f85-9ebc-790f2ac1becb', 'zh-TW', '繁體中文', 1, true, true, false, '2026-04-20 14:13:39.319427+00', '2026-04-20 14:15:26.859999+00');
INSERT INTO public.agent_language (pid, agent_language_uid, code, name, sort_order, is_default, is_active, is_deleted, created_at, updated_at) VALUES (2, 'a04dd1f9-bb21-4444-9bbe-429971278c8a', 'en', 'English', 2, false, true, false, '2026-04-20 14:13:39.319427+00', '2026-04-20 14:15:30.761792+00');
INSERT INTO public.agent_language (pid, agent_language_uid, code, name, sort_order, is_default, is_active, is_deleted, created_at, updated_at) VALUES (3, 'f3c5234f-0405-49d8-bd0d-064974f306d9', 'ja', '日本語', 3, false, true, false, '2026-04-20 14:13:39.319427+00', '2026-04-20 14:15:34.542075+00');
INSERT INTO public.agent_language (pid, agent_language_uid, code, name, sort_order, is_default, is_active, is_deleted, created_at, updated_at) VALUES (4, '2c717d78-cf71-4e7e-9c0e-0ac121453a7b', 'zh-CN', '简体中文', 4, false, true, false, '2026-04-20 14:13:39.319427+00', '2026-04-20 14:15:38.937049+00');
INSERT INTO public.agent_language (pid, agent_language_uid, code, name, sort_order, is_default, is_active, is_deleted, created_at, updated_at) VALUES (5, 'e4ff56a2-6dae-43ee-8739-c3cfdde3b048', 'ko', '한국어', 5, false, true, false, '2026-04-20 14:13:39.319427+00', '2026-04-20 14:15:43.5068+00');


--
-- Data for Name: agent_skill; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.agent_skill (agent_uid, skill_uid) VALUES ('d742b9df-1554-43f1-af76-edefe11407f0', 'ec201d44-35dc-4481-8c04-71328c566dbd');


--
-- Data for Name: agent_template; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.agent_template (pid, agent_template_uid, template_key, label, description, name, identity, language, style, role_prompt, greeting, temperature, max_tokens, response_format, response_format_example, sort_order, is_active, is_deleted, created_at, updated_at) VALUES (1, '0c1f6b9f-538d-4c6c-a717-d974eac4c0e2', 'python-dev', 'Python 開發助手', '協助 Python 程式撰寫、除錯、重構與最佳化的專業助手。', 'Python 開發助手', '資深 Python 工程師，熟悉常用框架與生態系', 'zh-TW', '專業、精確、務實', '請以資深 Python 工程師的角度回答問題。回覆時：
1. 提供可執行的完整範例，並說明關鍵邏輯
2. 指出潛在的效能或可維護性問題
3. 遵守 PEP 8 與常見最佳實踐
4. 若使用者未指定版本，預設以 Python 3.11+ 為目標', '您好，我是您的 Python 開發助手，請告訴我遇到的問題或需求。', 0.3, 4096, 'markdown', NULL, 1, true, false, '2026-04-20 15:22:45.62069+00', '2026-04-21 13:50:04.644243+00');
INSERT INTO public.agent_template (pid, agent_template_uid, template_key, label, description, name, identity, language, style, role_prompt, greeting, temperature, max_tokens, response_format, response_format_example, sort_order, is_active, is_deleted, created_at, updated_at) VALUES (2, '17e35b10-e03e-47a8-aafe-c8feb387f01a', 'code-reviewer', 'Code Reviewer', '針對使用者提供的程式碼，給出結構化且可行動的審查意見。', 'Code Reviewer', '資深技術主管，負責多語言程式碼審查', 'zh-TW', '嚴謹、客觀、以證據為本', '請以資深技術主管的角度審查使用者提供的程式碼。請依下列結構回覆：
- 總評（2 至 3 句概述整體品質）
- 必改（Bug、安全性、正確性）
- 建議改進（可讀性、效能、測試）
- 亮點（值得保留的優點）
審查時請指出具體行號或片段，避免空泛評論。', '您好，請貼上您想審查的程式碼，我會提供結構化的意見。', 0.2, 4096, 'markdown', NULL, 2, true, false, '2026-04-20 15:22:45.62069+00', '2026-04-21 13:50:08.291224+00');
INSERT INTO public.agent_template (pid, agent_template_uid, template_key, label, description, name, identity, language, style, role_prompt, greeting, temperature, max_tokens, response_format, response_format_example, sort_order, is_active, is_deleted, created_at, updated_at) VALUES (3, 'fcf1e450-cd24-4bf0-b7b5-9ab588c23725', 'zh-writer', '中文寫作助手', '協助使用者潤飾、改寫、擴寫中文文案，兼顧語意與風格。', '中文寫作助手', '資深中文編輯，擅長多種文體的潤飾與改寫', 'zh-TW', '流暢、自然、符合台灣慣用語', '請擔任專業中文編輯，回覆時請：
1. 保留原文語意，不擅自加入未提及的資訊
2. 同時提供「修改後版本」與「重點調整」兩段
3. 若使用者沒指定口吻，預設以自然且友善的語氣撰寫
4. 注意使用繁體中文與台灣慣用詞彙', '您好，請貼上想潤飾的文字，我會為您調整。', 0.7, 4096, 'markdown', NULL, 3, true, false, '2026-04-20 15:22:45.62069+00', '2026-04-21 13:50:12.221405+00');
INSERT INTO public.agent_template (pid, agent_template_uid, template_key, label, description, name, identity, language, style, role_prompt, greeting, temperature, max_tokens, response_format, response_format_example, sort_order, is_active, is_deleted, created_at, updated_at) VALUES (4, '9f1ec705-0f13-4f86-996c-2fde4228a826', 'zh-en-translator', '中英翻譯', '提供中文與英文雙向翻譯，兼顧忠實、流暢與上下文。', '中英翻譯', '專業雙語譯者', 'zh-TW', '精準、自然、語境敏感', '請擔任專業雙語譯者，翻譯時請：
1. 自動判斷來源語言並翻譯至另一種語言
2. 忠於原意，必要時提供備選譯法並註記差異
3. 若原文包含專有名詞或技術術語，保留原文並附中文翻譯
4. 僅輸出譯文與必要說明，不加多餘客套話', 'Hello / 您好，請提供要翻譯的內容即可。', 0.3, 4096, 'markdown', NULL, 4, true, false, '2026-04-20 15:22:45.62069+00', '2026-04-21 13:50:15.731101+00');


--
-- Data for Name: chat_attachment; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: chat_memory; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.chat_memory (pid, chat_memory_uid, chat_session_uid, source_chat_message_uids, keywords, entities, topic, embedding, created_at) VALUES (4, '2afe806f-7c0e-442d-bc77-a94beff041ac', '2f8501f3-0eea-45cc-8f9f-cba9f6836e7b', '{8cda90f3-84dd-4e41-a8d3-2519f485314d,05d5bd24-6b80-45da-8b47-c4a1999eef9f}', '{SQL注入,FastAPI,"endpoint review",資訊洩漏,參數化查詢,非同步,依賴注入,快取,N+1查詢,HTTP請求,型別標註,例外處理,分層架構,"repository pattern","service layer"}', '{FastAPI,APIRouter,requests,AsyncSession,Redis,httpx.AsyncClient,Depends}', 'FastAPI endpoint程式碼審查，發現SQL注入漏洞、敏感資訊洩漏、缺乏型別標註、N+1查詢問題、同步HTTP呼叫阻塞、全域快取無過期機制等5項嚴重問題和5項改進建議，需要全面重構以符合安全性和架構規範', '[-0.031021118,0.024017334,0.033569336,-0.009963989,0.023880005,-0.015029907,-0.05984497,0.04083252,0.039611816,-0.02809143,0.028182983,-0.024261475,-0.056243896,-0.0004222393,0.009056091,-0.027786255,-0.018844604,-0.024353027,0.011482239,0.01966858,0.016433716,0.0059165955,0.02520752,-0.0068969727,0.0026721954,-0.013710022,0.04159546,0.02168274,-0.0068092346,-0.038970947,0.014442444,-0.025436401,0.041229248,0.047454834,0.033203125,0.00018489361,0.021087646,0.019226074,0.038269043,-0.019607544,0.042785645,0.013725281,0.010902405,0.004310608,0.018722534,0.004749298,-0.018936157,0.0049209595,-0.023162842,0.029891968,-0.060302734,-0.018997192,-0.020553589,0.01763916,0.013420105,-0.0016317368,-0.0289917,-0.015533447,0.022628784,0.05996704,0.05529785,-0.05050659,-0.039886475,-0.0007004738,-0.03778076,-0.029052734,-0.019729614,-0.018600464,0.0068969727,0.02935791,0.022979736,0.013465881,-0.022659302,-0.047058105,0.061157227,0.0010890961,0.0029010773,0.029678345,0.024215698,-0.010696411,-0.051208496,-0.008430481,0.015037537,-0.077941895,-0.0082473755,-0.034576416,-0.062347412,-0.028930664,-0.015296936,-0.022064209,-0.03186035,0.063964844,-0.015563965,-0.006259918,-0.002544403,0.031173706,0.03656006,0.012779236,-0.022277832,0.050109863,0.075927734,-0.05319214,-0.018585205,0.021438599,-0.0087509155,-0.056274414,0.008598328,-0.00049352646,-0.043426514,-0.03149414,-0.04046631,-0.024124146,-0.052215576,0.004802704,-0.0017032623,-0.022064209,-0.016357422,0.00093364716,-0.00274086,-0.009353638,0.023513794,0.0129470825,0.0028018951,-0.03527832,-0.013267517,-0.029190063,0.0284729,0.031082153,-0.036102295,0.00094509125,0.016647339,-0.029632568,0.091430664,-0.014587402,0.011444092,0.03173828,-0.04611206,0.042053223,-0.027786255,-0.02784729,0.007419586,-0.038757324,0.012893677,0.016845703,-0.023483276,0.006362915,-0.0055007935,0.0206604,-0.01713562,0.007671356,0.005706787,0.007801056,-0.06390381,0.01247406,-0.034576416,-0.027740479,0.04626465,0.00032925606,-0.04135132,0.04333496,-0.023727417,-0.012588501,-0.0073165894,0.021469116,-0.015296936,0.0047836304,-0.015075684,-0.022247314,-0.038360596,-0.02659607,-0.005016327,-0.07128906,0.053497314,-0.00844574,-0.009590149,-0.0022449493,0.020446777,-0.04598999,-0.0057144165,-0.010009766,-0.008598328,0.01737976,-0.013557434,0.022628784,-0.03805542,-0.06854248,0.0059394836,0.049194336,-0.011421204,0.014259338,-0.027160645,0.040924072,-0.0024089813,0.015289307,0.003250122,-0.07373047,-0.026626587,-0.024505615,-0.01449585,0.031982422,-0.037261963,-0.008895874,0.039154053,-0.03994751,0.0206604,-0.020065308,-0.009986877,-0.0076179504,0.017745972,-0.042144775,0.0206604,0.01121521,0.0076828003,0.022949219,-0.0022525787,0.017196655,0.03540039,-0.006324768,0.020324707,0.03439331,-0.0005044937,0.018737793,0.045440674,0.0032463074,0.0037345886,0.088378906,0.028869629,-0.017410278,-0.029525757,-0.008850098,0.0014514923,0.0024089813,-0.024429321,-0.03390503,0.006008148,-0.008773804,0.0071105957,-0.0033721924,-0.01751709,0.008972168,-0.028839111,0.0075950623,-0.028701782,0.025436401,0.0038337708,0.009490967,0.00062036514,-0.033203125,0.011230469,0.06536865,0.052459717,-0.017913818,0.031677246,-0.012260437,-0.01474762,-0.061187744,0.024459839,-0.04083252,-0.022232056,0.0014438629,0.026397705,0.03970337,0.012374878,-0.030273438,-0.019989014,-0.0149383545,0.01864624,0.038970947,-0.00919342,-0.002286911,0.020477295,0.026809692,0.006580353,-0.017822266,-0.0017442703,-0.033294678,0.004184723,-0.013442993,-0.00081300735,-0.028839111,0.010063171,-0.06512451,0.045196533,0.006931305,0.025482178,-0.010917664,0.009666443,-0.026672363,0.017929077,-0.01235199,-0.018463135,0.048065186,-0.05718994,-0.008857727,0.049041748,0.017562866,0.016845703,0.025970459,0.028305054,0.022979736,0.05203247,0.027633667,-0.039154053,0.0025863647,0.037109375,-0.018585205,0.016830444,-0.05227661,-0.034362793,-0.03149414,-0.016143799,-0.042938232,-0.021728516,-0.016143799,-0.0317688,-0.06378174,-0.011726379,-0.054901123,0.028839111,-0.033477783,-0.01676941,-0.05142212,-0.009788513,-0.015731812,0.012390137,-0.016357422,0.0011177063,0.011260986,0.023117065,-0.023406982,0.03753662,-0.08905029,0.01285553,-0.06359863,-0.029754639,-0.03186035,-0.018859863,0.025360107,0.041900635,0.033996582,-0.045837402,-0.022537231,-0.008613586,0.018508911,0.038360596,0.018432617,0.0026245117,-0.010925293,-0.005420685,0.021575928,0.009490967,0.015586853,0.026107788,0.032226562,0.02067566,-0.012763977,-0.039398193,-0.035095215,-0.05834961,-0.0028896332,-0.01638794,0.021102905,0.01828003,-0.041259766,0.027648926,0.05239868,-0.007183075,-0.030273438,-0.06439209,-0.047912598,0.0020561218,0.08483887,-0.03591919,-0.00017774105,-0.020843506,0.06161499,-0.03387451,0.047973633,0.022415161,0.008659363,0.012107849,-0.01651001,0.026184082,0.04135132,0.01108551,0.08087158,0.006931305,0.00869751,0.013473511,-0.008796692,-0.019592285,-0.03010559,0.015342712,-0.026000977,0.030975342,-0.021774292,0.03564453,0.042053223,0.010536194,0.013244629,0.04006958,-0.018310547,-0.045013428,-0.0022296906,-0.030593872,0.012649536,0.030273438,-0.011703491,0.031799316,-0.00983429,0.02947998,-0.013206482,0.032470703,0.005241394,0.047729492,-0.023269653,-0.029052734,-0.009025574,-0.010726929,0.04373169,0.03274536,-0.019515991,-0.074157715,-0.005332947,-0.03955078,0.0003142357,0.041656494,0.004722595,-0.018478394,-0.043121338,-0.01928711,-0.02798462,0.017303467,-0.024551392,-0.023101807,-0.023910522,-0.007534027,0.012214661,0.028121948,0.017425537,-0.025360107,-0.035095215,-0.03201294,0.057556152,-0.02217102,0.0030918121,-0.023803711,-0.022460938,-0.021087646,0.002204895,-0.015144348,-0.023269653,0.005115509,0.019195557,-0.029922485,-0.082214355,0.017730713,-0.029922485,0.007129669,-0.0069084167,0.022735596,0.039855957,-0.03564453,0.013999939,0.06427002,0.01675415,0.017044067,-0.01739502,0.040924072,0.01927185,0.027893066,0.042755127,0.00749588,-0.017044067,-0.038269043,0.015609741,0.0011034012,0.018737793,-0.015586853,0.0034065247,-0.020492554,-0.032684326,0.017593384,-0.023803711,0.004699707,0.14489746,-0.015960693,0.01727295,-0.009635925,0.012321472,0.014839172,0.050964355,0.07116699,-0.011009216,-0.035247803,-0.012008667,-0.05380249,-0.049194336,-0.0072746277,-0.021377563,-0.013290405,-0.041137695,-0.014305115,0.014678955,0.014785767,-0.07373047,0.01486969,-0.0115737915,0.031219482,-0.000787735,0.0211792,0.019195557,0.015052795,0.01071167,-0.013114929,0.02508545,-0.009925842,0.028961182,-0.030715942,0.012367249,0.032440186,0.0020980835,0.011047363,-0.017501831,-0.020843506,-0.014694214,-0.018325806,-0.0034389496,0.014457703,-0.010940552,0.0046081543,-0.014854431,-0.0022239685,-0.008605957,0.0062179565,-0.009651184,-0.005344391,-0.026367188,-0.03152466,0.023040771,-0.019470215,0.014152527,0.015945435,-0.027740479,-0.0149002075,-0.012145996,-0.027252197,0.0014543533,0.0069007874,0.007835388,0.008956909,-0.05368042,0.008354187,-0.001127243,0.0070343018,0.027954102,0.015625,-0.05557251,-0.019927979,-0.016052246,0.009712219,-0.021194458,0.0034332275,-0.023529053,-0.040161133,-0.026901245,-0.002161026,-0.019439697,0.01876831,-0.001036644,-0.020507812,0.009765625,-0.04135132,0.018157959,-0.0009784698,-0.019943237,0.023117065,-0.043121338,0.011932373,-0.038726807,-0.008285522,-0.034210205,0.014373779,0.0423584,-0.035583496,-0.040252686,0.045043945,-0.012084961,-0.0082473755,0.03668213,0.010749817,0.015792847,0.0013942719,-0.011329651,0.027252197,0.00013279915,-0.0004887581,0.016601562,0.00092983246,0.00020456314,0.0047912598,-0.006389618,-0.01574707,-0.01197052,-0.024261475,0.0021419525,0.01449585,-0.010215759,0.035186768,-0.033294678,0.005092621,0.006088257,0.01473999,-0.048706055,0.026000977,0.016647339,-0.01713562,0.010681152,0.012916565,-0.0037403107,-0.009262085,-0.0038471222,0.052215576,0.010063171,0.035308838,0.001086235,-0.04949951,-0.04324341,-0.01473999,-0.0020942688,-0.0074272156,0.0259552,0.0018053055,-0.027648926,0.023590088,0.023544312,-0.010879517,0.0043144226,-0.03286743,-0.048858643,0.019256592,0.0021190643,0.027770996,-0.03314209,0.027328491,-0.00730896,-0.036102295,-0.0048713684,-0.006713867,0.002090454,-0.0027122498,-0.035369873,0.010055542,-0.0104599,0.020370483,-0.018447876,0.009017944,-0.011993408,-0.0042877197,0.01423645,0.014213562,-0.010276794,-0.033050537,0.048706055,-0.023666382,0.062438965,0.013977051,0.0057144165,0.02557373,-0.016113281,-0.044647217,0.04168701,-0.012565613,0.03363037,0.029037476,-0.030059814,0.013694763,-0.021530151,0.016235352,0.054992676,-0.0059318542,0.043945312,-0.042999268,-0.02420044,0.014518738,-0.015533447,-0.020370483,0.028656006,0.023147583,0.01689148,0.0067214966,-0.006755829,0.014457703,-0.016799927,-0.020721436,0.030410767,-0.027511597,0.025268555,0.006225586,0.034057617,0.011474609,0.024505615,0.016342163,0.0020141602,-0.061157227,-0.0057525635,0.017913818,0.009529114,0.017486572,-0.022491455,-0.03656006,-0.0012731552,-0.018615723,0.031707764,-0.018844604,-0.00041937828,-0.0012674332,0.0093688965,0.014465332,-0.02859497,0.012237549,0.028182983,-0.015960693,-0.04840088,-0.015838623,-0.006072998,-0.016494751,0.022003174,-0.0047569275,0.0020961761,-0.027191162,0.01626587,-0.0042381287,0.024215698,0.015052795,-0.015090942,-0.03704834,-0.0024642944,-0.02684021,-0.025314331,0.0008401871,-0.021209717,-0.017730713,0.041015625,-0.00014555454,-0.017669678,-0.026016235,0.043945312,0.033325195,0.01423645,-0.030288696,0.0073280334,0.006412506,0.008148193,0.0013380051,-0.05218506,0.018875122,0.02571106,-0.005908966,0.0032138824,0.008560181,0.030578613,0.008308411,-0.017868042,0.01751709,-0.0028915405,-0.047058105,0.013969421,-0.0149002075,0.010612488,0.047973633,-0.02709961,0.00043821335,0.0014324188,0.050354004,-0.020690918,-0.04171753,-0.045654297,0.011169434,0.007850647,-0.00440979,0.008880615,0.013252258,-0.04309082,-0.03717041,0.04333496,-0.0068855286,0.034484863,-0.03933716,0.0041236877,0.023452759,-0.009963989,-0.007659912,-0.049560547,0.04623413,-0.00083112717,-0.028076172,-0.055267334,-0.00459671,0.012283325,-0.0001887083,-0.0011587143,0.010543823,0.01852417,0.023025513,-0.011405945,-0.00712204,0.05508423,-0.008666992,-0.013977051,-0.009101868,0.0023517609,-0.007259369,0.031082153,0.021087646,-0.006164551,0.0019779205,0.028167725,-0.030471802,0.016540527,0.049560547,-0.002286911,0.021133423,-0.015853882,-0.02331543,0.0141067505,0.0039100647,-0.027160645,-0.0012683868,0.009567261,-0.0044021606,-0.005870819,0.010643005,-0.022323608,-0.019317627,0.022476196,-0.016738892,-0.016937256,-0.0018987656,0.023345947,0.025650024,0.014282227,-0.020950317,-0.01121521,-0.013053894,-0.013252258,-0.031829834,-0.010284424,0.004878998,-0.004085541,-0.0056991577,-0.002632141,0.014656067,-0.013206482,0.027633667,0.0030574799,-0.0039863586,0.0072517395,0.02078247,0.026138306,-0.034698486,0.046417236,-0.012809753,-0.013977051,0.023071289,-0.017684937,0.013977051,0.031036377,-0.03189087,-0.00040650368,-0.028533936,-0.015365601,0.004070282,0.019622803,-0.008613586,-0.03955078,-0.022125244,0.058898926,-0.027862549,0.031219482,0.03994751,-0.03845215,-0.045532227,0.017837524,0.008644104,0.0076065063,-0.014770508,0.023880005,-0.012237549,0.0034599304,0.05404663,0.015357971,0.004711151,0.013114929,0.032287598,0.025878906,0.014541626,0.020706177,0.026138306,-0.036621094,0.020233154,-0.012229919,0.049041748,0.038909912,0.009208679,0.0070610046,0.024734497,0.023330688,0.0010089874,0.029525757,-0.00085926056,-0.03668213,0.01739502,-0.007221222,-0.006362915,-0.02947998,-0.009140015,-0.0004529953,0.04852295,-0.01574707,0.018920898,-0.019638062,0.03152466,0.02154541,0.020431519,0.015068054,-0.015335083,0.029052734,0.03479004,-0.017456055,0.013801575,0.0154953,-0.016738892,0.022644043,0.021270752,-0.015113831,0.030670166,-0.003818512,0.012832642,-0.012825012,0.0051956177,0.025100708,0.011993408,-0.043945312,0.018035889,-0.0036468506,0.015449524,0.042236328,0.009307861,-0.024749756,0.030944824,-0.023239136,0.010612488,-0.0519104,-0.049041748,-0.035491943,0.009246826,0.024307251,0.04928589,0.0051841736,-0.0309906,-0.018661499,-0.00047445297,-0.0054740906,-0.010719299,-0.025390625,-0.00497818,0.019500732,0.0014972687,0.00096559525,0.03225708,0.045043945,0.059753418,0.023803711,0.029937744,0.017044067,0.033691406,0.023452759,-0.00749588,-0.0042648315,0.028839111,0.033996582,0.004497528,-0.012680054,0.0010995865,0.019851685,0.0309906,0.009117126,0.045806885,0.026763916,0.0052986145,-0.045135498,-0.030273438,0.015426636,-0.01247406,-0.014595032,0.004875183,0.023895264,0.019973755,-0.00037026405,0.00028181076,0.02734375,-0.0060424805,-0.010124207,-0.0029506683,0.0016555786,0.05923462,-0.024459839,0.027999878,-0.0024089813,0.013336182,-0.046936035,0.014213562,0.0026111603,0.051513672,-0.00019145012,0.013252258,-0.021957397,-0.012413025,-0.0023460388,0.04095459,-0.032348633,0.039093018,-0.021942139,-0.026107788,-0.017669678,0.029785156,0.0030975342,0.05319214,0.0042152405,-0.0309906,-0.011558533,0.011451721,-0.0018644333,0.015426636,-0.005542755,0.0044288635,0.00043606758,0.010719299,0.0062942505,-0.0028896332,0.012825012,0.0362854,-0.0053710938,0.027038574,0.0158844,-0.003610611,0.0090408325,-0.011268616,0.011978149,0.02859497,-0.00053596497,0.0013856888,-0.004611969,-0.0041160583,0.008811951,0.008323669,0.001917839,0.012779236,-0.03277588,0.0103302,-0.013908386,-0.006351471,0.0015544891,-0.0007376671,0.040771484,0.0110321045,0.0021572113,0.0051956177,-0.038604736,0.019805908,-0.013404846,0.0073509216,-0.01586914,-0.02909851,0.008712769,-0.008506775,-0.0014476776,0.0101623535,0.014015198,0.0037956238,0.03765869,-0.0006489754,-0.0074806213,-0.018585205,-0.003780365,0.020568848,0.023086548,0.019943237,-0.03366089,-0.029388428,-0.01512146,-0.0016498566,0.021957397,-0.012031555,0.036743164,-0.009162903,0.024749756,0.011451721,0.021636963,0.021072388,-0.0178833,0.006175995,-0.029312134,-0.026046753,0.05493164,-0.012893677,0.012306213,-0.010910034,0.038604736,-0.0019044876,-0.01928711,0.022842407,2.5570393e-05,-0.014389038,-0.029174805,0.004753113,0.013290405,0.026321411,-0.020233154,-0.009292603,-0.012458801,0.0068092346,0.022445679,-0.006801605,-0.027770996,-0.028335571,0.053985596,-0.005542755,-0.010688782,-0.00023961067,-0.038970947,0.022964478,-0.005420685,0.014320374,-0.021316528,0.012718201,0.008560181,-0.016601562,-0.0004272461,-0.01158905,0.013801575,-0.019973755,-0.0072402954,0.0044670105,-0.036712646,-0.019805908,0.04046631,0.014549255,0.025970459,0.008888245,-0.020599365,0.01096344,0.013381958,0.0284729,-0.017120361,0.0017795563,-0.0038852692,0.023788452,-0.0014915466,0.00541687,0.016021729,0.01159668,-0.005279541,0.0362854,-0.015655518,-0.0043296814,0.012077332,0.046325684,0.034088135,0.011787415,-0.018447876,0.008476257,0.010658264,0.003742218,0.008453369,0.0569458,-0.019683838,-0.037109375,-0.018447876,0.029937744,-0.02218628,-0.0055732727,-0.035461426,0.008102417,0.017440796,-0.026443481,-0.006679535,-0.018371582,0.021469116,0.008964539,-0.010292053,0.03604126,0.020996094,0.004638672,0.019378662,0.010787964,0.014663696,0.0104522705,-0.03665161,-0.0062179565,0.0076942444,-0.037963867,-0.030029297,0.0011711121,0.018692017,-0.02017212,-0.015388489,-0.023910522,0.009689331,-0.0049476624,0.010307312,-0.002281189,-0.012039185,0.012031555,-0.0062294006,0.006313324,-0.0231781,0.022323608,-0.0045814514,-0.008102417,0.017105103,0.021881104,0.0048713684,-0.0032024384,0.022705078,-0.047210693,-0.0149383545,-0.0047836304,0.0034980774,-0.02720642,0.019424438,0.012481689,0.022125244,0.0014352798,-0.006095886,-0.017318726,-0.0035552979,0.02935791,0.01197052,0.033325195,0.013969421,-0.0129852295,0.0007162094,-0.0006942749,-0.002544403,-0.009979248,0.035888672,-0.017105103,-0.018112183,0.005050659,-0.020584106,1.2278557e-05,-0.0007824898,0.008575439,0.0060653687,0.012832642,0.0018177032,0.012649536,0.028289795,-0.017288208,-0.005874634,0.019714355,-0.0034999847,0.020050049,-0.028884888,0.001405716,-0.0015096664,0.015289307,0.0055389404,-0.032714844,-0.029220581,0.025253296,0.014518738,-0.0034713745,-0.00054216385,0.0024585724,-0.011482239,-0.022644043,-0.005332947,0.0058288574,0.025558472,0.010574341,0.017684937,-0.011413574,0.019760132,-0.026992798,0.004749298,0.011405945,0.00043058395,0.021469116,0.013336182,-0.017669678,0.005493164,-0.020889282,0.0012950897,0.013175964,-0.016601562,0.004211426,0.020690918,0.015213013,0.015792847,-0.016220093,0.026138306,-0.0016946793,0.016311646,-0.0034999847,-0.014022827,0.0017442703,0.0059776306,0.004436493,0.035888672,-0.006790161,0.002746582,0.018188477,0.017349243,0.014678955,6.055832e-05,-0.03189087,0.016494751,0.021972656,0.01197052,0.026626587,-0.011177063,-0.032348633,0.0042915344,0.021148682,-0.03845215,0.03149414,-0.012825012,-0.0075912476,0.0368042,-0.0058784485,-0.009681702,-0.010810852,-0.027770996,-0.006095886,0.0209198,0.002105713,0.030807495,0.03729248,-0.0068359375,0.024749756,-0.0048828125,0.01109314,-0.014945984,0.042419434,-0.022903442,-0.029830933,0.0423584,0.034454346,-0.02909851,0.0038967133,-0.017822266,-0.003780365,-0.018722534,0.042053223,-0.015403748,0.032592773,0.006416321,-0.02746582,0.024307251,0.02583313,0.014221191,-0.0008773804,-0.0076942444,-0.021133423,0.032104492,0.00093221664,-0.00762558,-0.018981934,-0.0062026978,0.020263672,-0.0011987686,-5.352497e-05,-0.015602112,-0.003080368,0.006866455,0.0067367554,-0.021331787,-0.032470703,0.020523071,0.024124146,0.0040397644,-0.017105103,0.021636963,0.0024375916,-0.0005354881,-0.0049476624,-0.003107071,0.024902344,0.014045715,0.0019798279,0.04647827,0.008003235,-0.0362854,-0.030151367,0.006576538,0.030776978,0.046142578,-0.021148682,0.0006432533,-0.06896973,-0.016540527,-0.022216797,0.0046463013,-0.016036987,-0.021392822,-0.022415161,-0.037902832,0.0129852295,-0.01763916,0.01763916,0.018875122,0.016738892,-0.007949829,-0.031433105,0.0034923553,0.0345459,-0.0020484924,-0.014305115,0.008392334,-0.027862549,-0.019989014,0.009544373,-0.031707764,-0.0146102905,0.0016202927,0.014198303,-0.018951416,-0.027954102,0.008590698,0.011505127,-0.011558533,0.019683838,0.00459671,0.011711121,0.023513794,0.038604736,-0.028823853,0.020507812,0.004032135,-0.0011997223,-0.008972168,-0.031021118,-0.012611389,-0.012039185,0.017959595,-0.0073280334,0.011978149,-0.03378296,0.02659607,0.035217285,0.008377075,0.012084961,0.009124756,-0.0012674332,0.018707275,0.011459351,-0.021850586,0.037139893,-0.010444641,0.008712769,-0.008674622,0.029403687,-0.0064582825,0.048431396,0.031799316,0.028244019,-0.015007019,0.018844604,0.09838867,0.010627747,0.0013399124,0.020248413,0.011581421,7.599592e-05,0.016052246,0.041290283,0.025222778,-0.013473511,0.002521515,0.011207581,0.01260376,0.027191162,-0.012916565,-0.002588272,-0.01914978,-0.0022411346,-0.012901306,-0.015991211,-0.0085372925,0.015777588,-0.010322571,0.01727295,-0.02128601,0.022491455,0.054504395,0.016540527,0.01626587,-0.032043457,-0.026000977,0.033691406,0.045715332,-0.00061798096,-0.033294678,-0.017669678,-0.019180298,0.006591797,-0.0023822784,-0.0060539246,-0.027282715,-0.0006155968,-0.029144287,0.0035171509,-0.009262085,0.028259277,0.019012451,-0.008911133,-0.008552551,-0.037261963,0.0062294006,-0.00056123734,-0.006843567,-0.014839172,-0.01159668,-0.017547607,0.0020484924,0.0059509277,0.030288696,0.0357666,-0.007286072,0.0040512085,-0.011741638,-0.04055786,-0.010116577]', '2026-04-22 13:52:23.56952+00');


--
-- Data for Name: chat_message; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (1, '137f36a6-1e1c-41a3-be58-8ef30d63d7f2', '550d410f-abe5-46e8-81a6-08f348053d05', 'user', '幫我列 2025 年下半年 AI 晶片領域最受矚目的 3 件大事，速覽模式即可。', NULL, NULL, NULL, NULL, true, '2026-04-21 15:18:32.065266+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (2, '3fbe6163-7931-4091-a6cd-c74bbab2ab36', '79c67ed4-4340-4fca-b8ac-70b4a6fe8626', 'user', '幫我列 2025 年下半年 AI 晶片領域最受矚目的 3 件大事，速覽模式就好。', NULL, NULL, NULL, NULL, true, '2026-04-21 15:21:53.891655+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (3, 'edc0f727-0081-4d25-ba4d-cd02e9c877c1', '79c67ed4-4340-4fca-b8ac-70b4a6fe8626', 'assistant', '您好，關於您詢問的 2025 年下半年 AI 晶片領域最受矚目的 3 件大事，由於目前時間點距離 2025 年下半年仍有較長一段時間，且科技發展日新月異，現在要精確預測屆時「最受矚目」的事件有一定難度。

不過，我可以根據目前的產業趨勢和各公司公開的發展藍圖，為您推測屆時可能具有高度關注度的幾個方向。請注意，這些內容屬於**分析與推測**，並非已發生的事實。

以下是依據現有資訊，推測 2025 年下半年 AI 晶片領域可能受矚目的三件事：

1.  **NVIDIA 下一代架構 AI GPU 的市場表現與生態系統擴展** (分析與推測)
    *   **發生了什麼 (預期)**：NVIDIA 通常每兩年左右推出新一代 AI GPU 架構。若依照此週期，2025 年下半年市場將密切關注其下一代（可能接替 Blackwell 架構）AI GPU 的實際出貨量、性能表現、以及在大型語言模型訓練與推論市場的佔有率。同時，其 CUDA 軟體生態系統是否能持續保持領先地位，並有效阻擊競爭者，將是關注焦點。
    *   **為什麼重要**：NVIDIA 在 AI 晶片市場長期佔據主導地位。其新產品的性能與供應狀況，將直接影響全球 AI 發展的速度與方向，並牽動數據中心建置、雲端服務供應商的資本支出。
    *   **各方反應 (預期)**：競爭對手如 AMD 和 Intel 將持續推出自家產品線以爭奪市場。雲端服務商（AWS、Google Cloud、Microsoft Azure）將評估採購策略，並可能加強自研晶片的部署。

2.  **Intel Gaudi 系列 AI 加速器的市場份額增長與企業級應用落地** (分析與推測)
    *   **發生了什麼 (預期)**：Intel 正積極推動其 Gaudi 系列 AI 加速器，並強調其性價比與開源軟體生態的優勢。2025 年下半年，市場將觀察 Gaudi 3 及其後續產品在企業級客戶、特別是需要具成本效益的數據中心部署中的實際採用情況，以及其在主流大模型訓練與推論任務上的表現。
    *   **為什麼重要**：Intel 作為傳統晶片巨頭，若能在 AI 加速器市場取得顯著進展，將有助於打破 NVIDIA 的壟斷格局，為市場提供更多元且具競爭力的選擇，進而可能降低 AI 運算成本。
    *   **各方反應 (預期)**：若 Intel 成功擴大市佔，將迫使 NVIDIA 和 AMD 重新審視其定價與產品策略。企業客戶將有更多議價空間與選擇。

3.  **邊緣 AI 晶片在生成式 AI 應用中的普及與性能突破** (分析與推測)
    *   **發生了什麼 (預期)**：隨著小型化和高效能生成式 AI 模型（如 LLaMA-3-8B 等）的發展，2025 年下半年，市場將密切關注更多專為邊緣設備（如智慧手機、PC、物聯網設備、自動駕駛車輛）設計的 AI 晶片問世，這些晶片將強調在低功耗下運行複雜生成式 AI 模型的能力。
    *   **為什麼重要**：邊緣 AI 的普及能降低雲端運算成本，提高數據隱私性，並實現更即時、個人化的 AI 體驗。這將推動 AI 從雲端走向終端設備，開啟新的應用場景。
    *   **各方反應 (預期)**：高通、聯發科、蘋果、Intel 等晶片設計公司將持續投入研發，推出性能更強、功耗更低的邊緣 AI 晶片。軟體開發者將針對這些晶片優化應用，而終端設備製造商則會將其整合到新產品中。

請注意，這些預測是基於當前的技術發展軌跡和市場預期。如果出現任何顛覆性技術突破或市場策略變動，實際情況可能會有所不同。', 350, 970, 0.002530, 'google/gemini-2.5-flash', true, '2026-04-21 15:22:05.30086+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (4, '83bc4496-39fa-491d-851b-4c230d6f36e1', '7bb990c7-f1c1-4b3b-9148-110b63679412', 'user', '輸出 2025 年最新的 3 則科技新聞訊息，簡短概要預覽即可', NULL, NULL, NULL, NULL, true, '2026-04-22 13:20:10.185007+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (5, '9128d74e-d2d5-467a-b179-d1f84b5e63d2', '7bb990c7-f1c1-4b3b-9148-110b63679412', 'assistant', '好的，由於現在是 2024 年，我無法提供 2025 年的最新科技新聞。科技新聞的時效性非常高，我只能存取到我上次更新（知識截止日期）前的資訊。

如果您想了解 **2024 年最新的科技新聞**，請告知我您感興趣的領域（例如：AI、半導體、雲端、資安等），我會為您彙整。

或者，如果您希望我針對未來的科技趨勢做一些 **推測性的分析**，我可以根據目前的發展方向進行簡要概述，但請注意這將是基於現有資訊的推斷，而非實際發生的新聞。

請您明確您的需求，謝謝！', 342, 158, 0.000498, 'google/gemini-2.5-flash', true, '2026-04-22 13:20:13.747106+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (6, 'fa903cf3-a599-4a9a-85a5-5cf5d2431ed6', '7bb990c7-f1c1-4b3b-9148-110b63679412', 'user', '輸出 2024 年最新的 3 則 AI 科技新聞訊息，簡短概要預覽即可', NULL, NULL, NULL, NULL, true, '2026-04-22 13:22:05.073964+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (7, '7df33bf5-586f-4ebd-82cc-9b353f4cfd5c', '7bb990c7-f1c1-4b3b-9148-110b63679412', 'assistant', '好的，這是我為您整理的 2024 年最新的 3 則 AI 科技新聞訊息概要：

1.  **OpenAI 推出全新語音生成模型 Voice Engine** (OpenAI Blog, 2024-03-29)
    *   **發生了什麼：** OpenAI 於 3 月 29 日公開了其最新的語音生成模型 Voice Engine，該模型僅需 15 秒的音訊樣本，就能生成與原始說話者聲音相似且具自然情感的語音。
    *   **為什麼重要：** 這項技術展示了 AI 在語音合成方面的巨大進步，未來可能應用於協助非口語人士溝通、內容創作等，但也引發了深度的倫理和安全考量，特別是關於聲音濫用和深度偽造（deepfake）的擔憂。
    *   **各方反應：** OpenAI 聲明目前以負責任的態度小規模預覽，並與政府、媒體和研究人員討論其潛在風險與安全措施，暫不全面開放。

2.  **Meta 開源大型語言模型 Llama 3 系列** (Meta AI Blog, 2024-04-18)
    *   **發生了什麼：** Meta 於 4 月 18 日正式推出並開源了其新一代大型語言模型 Llama 3 系列，包含 8B 和 70B 參數版本。據稱，這些模型在多項基準測試中表現優於同級競爭對手，並提升了推理能力和程式碼生成效率。
    *   **為什麼重要：** Llama 3 的開源策略將進一步加速 AI 領域的創新和應用，降低企業和開發者使用先進 LLM 的門檻。Meta 也將其整合到 Meta AI 助理中，擴展 AI 應用場景。
    *   **各方反應：** 業界普遍認為 Llama 3 的推出將加劇大型語言模型領域的競爭，特別是與 Google Gemini 和 OpenAI GPT 系列的較量。

3.  **Google Cloud 擴大 AI 合作夥伴生態系，強化企業級生成式 AI 應用** (Google Cloud Blog, 2024-04-09)
    *   **發生了什麼：** Google Cloud 於 4 月 9 日宣布，正積極擴大與各行業軟體供應商（ISV）的合作，將其生成式 AI 技術（如 Gemini 和 Vertex AI）整合到企業級應用中，協助客戶加速數位轉型。
    *   **為什麼重要：** 這顯示了雲端服務提供商正在積極推動 AI 企業化，透過合作夥伴生態系，將複雜的 AI 技術轉化為可直接部署的解決方案，解決企業在合規性、資料安全和客製化方面的需求。
    *   **各方反應：** 合作夥伴表示這有助於其產品注入 AI 能力，提升競爭力。分析師指出，這將是 Google Cloud 在企業 AI 市場中與 AWS 和 Microsoft Azure 競爭的關鍵策略。', 524, 686, 0.001872, 'google/gemini-2.5-flash', true, '2026-04-22 13:22:12.000101+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (8, '5631243f-4811-400c-9d98-361683be1961', 'dfe5a05a-6fcf-4b7f-9f46-fb105a09e9fa', 'user', '幫我 review 這段 FastAPI endpoint，依嚴重程度列出問題，每項說明風險 + 修法。

from fastapi import APIRouter
import requests

router = APIRouter()

_cache = {}


async def get_user_orders(user_id, db, filter_type=[]):
    """列出使用者所有訂單，可選 filter_type。"""
    query = f"SELECT * FROM orders WHERE user_id = ''{user_id}''"
    if filter_type:
        types_str = ",".join(f"''{t}''" for t in filter_type)
        query += f" AND order_type IN ({types_str})"

    rows = await db.execute(query)
    orders = rows.fetchall()

    result = []
    for order in orders:
        customer = await db.execute(
            f"SELECT * FROM customers WHERE id = {order.customer_id}"
        )
        rate = requests.get("https://api.exchangerate.host/latest").json()

        result.append({
            "order": order,
            "customer": customer.fetchone(),
            "usd_rate": rate["rates"]["USD"],
        })

    return result


@router.get("/orders/{user_id}")
async def list_orders(user_id, db=None):
    try:
        data = await get_user_orders(user_id, db)
        _cache[user_id] = data
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "detail": str(e)}', NULL, NULL, NULL, NULL, true, '2026-04-22 13:37:59.229113+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (9, '43109e98-a1c2-4c3e-81a8-4d43d5471c2f', 'dfe5a05a-6fcf-4b7f-9f46-fb105a09e9fa', 'assistant', '## 總評
這段程式碼存在嚴重的安全漏洞和架構問題，包含 SQL 注入、缺乏型別標註、不當的例外處理等多項重大缺陷。程式碼品質遠低於生產環境標準，需要全面重構。

---

## 必改（Bug、安全性、正確性）

### 🔴 **極高風險：SQL 注入漏洞**
**第 9-10 行、第 12-13 行、第 19-20 行**
```python
query = f"SELECT * FROM orders WHERE user_id = ''{user_id}''"
query += f" AND order_type IN ({types_str})"
customer = await db.execute(f"SELECT * FROM customers WHERE id = {order.customer_id}")
```
**風險**：攻擊者可透過 `user_id` 或 `filter_type` 參數執行任意 SQL 指令，可能導致資料洩露、篡改或刪除
**修法**：使用參數化查詢
```python
query = "SELECT * FROM orders WHERE user_id = :user_id"
params = {"user_id": user_id}
if filter_type:
    query += " AND order_type = ANY(:filter_types)"
    params["filter_types"] = filter_type
```

### 🔴 **高風險：缺乏型別標註**
**第 7 行、第 25 行**
**風險**：無法在開發時期發現型別錯誤，增加執行時期錯誤機率
**修法**：依據規範添加完整型別標註
```python
async def get_user_orders(
    user_id: str, 
    db: AsyncSession, 
    filter_type: list[str] = None
) -> list[dict]:

async def list_orders(
    user_id: str, 
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
```

### 🔴 **高風險：違反統一回應格式**
**第 28-31 行**
**風險**：前端無法依賴一致的 API 契約，缺少必要的 `response_code` 欄位
**修法**：使用 `success()` 和 `failure()` helper
```python
return success({"orders": data}, 200)
# 錯誤時由全域 handler 處理，不在此捕捉
```

### 🔴 **高風險：不當例外處理**
**第 26-31 行**
**風險**：`str(e)` 可能洩露資料庫錯誤、堆疊資訊等敏感資料
**修法**：移除 try-catch，讓全域例外處理器統一處理

### 🔴 **中風險：預設可變參數**
**第 7 行**
```python
def get_user_orders(user_id, db, filter_type=[]):
```
**風險**：所有呼叫共享同一個 list 實例，可能產生意外的狀態污染
**修法**：
```python
def get_user_orders(user_id: str, db: AsyncSession, filter_type: list[str] = None) -> list[dict]:
    if filter_type is None:
        filter_type = []
```

---

## 建議改進（可讀性、效能、測試）

### 🟡 **效能問題：N+1 查詢**
**第 18-21 行**
每筆訂單都執行一次 customer 查詢，當訂單數量多時效能極差
**修法**：使用 JOIN 或批次查詢
```python
query = """
SELECT o.*, c.* FROM orders', 4340, 1024, 0.028380, 'anthropic/claude-sonnet-4', true, '2026-04-22 13:38:19.753126+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (10, '8cda90f3-84dd-4e41-a8d3-2519f485314d', '2f8501f3-0eea-45cc-8f9f-cba9f6836e7b', 'user', '幫我 review 這段 FastAPI endpoint，依嚴重程度列出問題，每項說明風險 + 修法。

from fastapi import APIRouter
import requests

router = APIRouter()

_cache = {}


async def get_user_orders(user_id, db, filter_type=[]):
    """列出使用者所有訂單，可選 filter_type。"""
    query = f"SELECT * FROM orders WHERE user_id = ''{user_id}''"
    if filter_type:
        types_str = ",".join(f"''{t}''" for t in filter_type)
        query += f" AND order_type IN ({types_str})"

    rows = await db.execute(query)
    orders = rows.fetchall()

    result = []
    for order in orders:
        customer = await db.execute(
            f"SELECT * FROM customers WHERE id = {order.customer_id}"
        )
        rate = requests.get("https://api.exchangerate.host/latest").json()

        result.append({
            "order": order,
            "customer": customer.fetchone(),
            "usd_rate": rate["rates"]["USD"],
        })

    return result


@router.get("/orders/{user_id}")
async def list_orders(user_id, db=None):
    try:
        data = await get_user_orders(user_id, db)
        _cache[user_id] = data
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "detail": str(e)}', NULL, NULL, NULL, NULL, true, '2026-04-22 13:50:57.378246+00', NULL, NULL);
INSERT INTO public.chat_message (pid, chat_message_uid, chat_session_uid, role, content, token_in, token_out, cost_usd, model, is_active, created_at, finish_reason, attachment_uids) VALUES (11, '05d5bd24-6b80-45da-8b47-c4a1999eef9f', '2f8501f3-0eea-45cc-8f9f-cba9f6836e7b', 'assistant', '## 總評
此程式碼存在多項嚴重的安全漏洞和架構問題，包括 SQL 注入、資訊洩漏、效能問題等。必須進行全面重構才能投入生產環境。

## 必改（Bug、安全性、正確性）

### 1. SQL 注入漏洞 - 極高風險
**問題位置：** 第 10-14 行
```python
query = f"SELECT * FROM orders WHERE user_id = ''{user_id}''"
query += f" AND order_type IN ({types_str})"
```
**風險：** 攻擊者可透過 `user_id` 或 `filter_type` 執行任意 SQL 指令，竊取或破壞資料
**修法：** 使用參數化查詢
```python
query = "SELECT * FROM orders WHERE user_id = :user_id"
params = {"user_id": user_id}
if filter_type:
    placeholders = ",".join([f":type_{i}" for i in range(len(filter_type))])
    query += f" AND order_type IN ({placeholders})"
    params.update({f"type_{i}": t for i, t in enumerate(filter_type)})
```

### 2. 敏感資訊洩漏 - 高風險
**問題位置：** 第 31 行
```python
return {"success": False, "detail": str(e)}
```
**風險：** 將 SQL 錯誤、資料庫結構等敏感資訊直接回傳給使用者
**修法：** 記錄詳細錯誤到 log，僅回傳通用錯誤訊息
```python
logger.exception("Failed to get user orders")
return failure("伺服器發生錯誤，請稍後再試", response_code=500)
```

### 3. 缺乏型別標註 - 中風險
**問題位置：** 第 8、28 行函式定義
**風險：** 違反後端規範，影響程式碼可維護性和 IDE 支援
**修法：** 
```python
async def get_user_orders(
    user_id: str, 
    db: AsyncSession, 
    filter_type: list[str] = None
) -> list[dict]:

async def list_orders(
    user_id: str, 
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
```

### 4. 違反統一回應格式 - 中風險
**問題位置：** 第 30、32 行
**風險：** 不符合 `ApiResponse` 規範，前端無法統一處理
**修法：** 使用標準回應格式
```python
return success({"orders": data}, response_code=200)
```

### 5. 缺乏依賴注入 - 中風險
**問題位置：** 第 28 行 `db=None`
**風險：** 無法正確獲取資料庫連線，會導致 runtime error
**修法：** 
```python
async def list_orders(
    user_id: str, 
    db: AsyncSession = Depends(get_db)
):
```

## 建議改進（可讀性、效能、測試）

### 1. N+1 查詢問題 - 效能風險
**問題位置：** 第 18-20 行在迴圈中查詢客戶資料
**修法：** 使用 JOIN 或批次查詢
```python
query = """
SELECT o.*, c.* 
FROM orders o 
LEFT JOIN customers c ON o.customer_id = c.id 
WHERE o.user_id = :user_id
"""
```

### 2. 同步 HTTP 呼叫阻塞 - 效能風險
**問題位置：** 第 21 行 `requests.get`
**修法：** 使用 `httpx.AsyncClient` 並移至 `clients/` 層
```python
# 在 services 層呼叫 clients
exchange_rate = await exchange_rate_client.get_latest_rates()
```

### 3. 全域快取無過期機制 - 記憶體洩漏風險
**問題位置：** 第 6 行 `_cache = {}`
**修法：** 使用 Redis 或帶 TTL 的快取機制

### 4. 可變預設參數 - 潛在 Bug
**問題位置：** 第 8 行 `filter_type=[]`
**修法：** 
```python
def get_user_orders(user_id: str, db: AsyncSession, filter_type: list[str] = None):
    if filter_type is None:
        filter_type = []
```

### 5. 違反分層架構
**問題位置：** API 層直接執行 SQL 查詢
**修法：** 將查詢邏輯移至 `repositories` 層，業務邏輯移至 `services` 層

## 亮點
- 使用了 async/await 非同步語法
- 有基本的例外處理機制
- 函式有文檔字串說明

## 建議重構後的結構
```python
@router.get("/orders/{user_id}")
async def list_orders(
    user_id: str,
    filter_type: list[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[OrderListResponse]:
    try:
        orders = await order_service.get_user_orders(user_id, filter_type, db)
        return success({"orders": orders})
    except AppError as e:
        return failure(e.detail, e.code)
```', 4340, 1572, 0.036600, 'anthropic/claude-sonnet-4', true, '2026-04-22 13:51:23.271683+00', NULL, NULL);


--
-- Data for Name: chat_project; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: chat_session; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.chat_session (pid, chat_session_uid, chat_project_uid, agent_uid, title, is_active, is_deleted, created_at, updated_at, owner_user_uid) VALUES (1, '550d410f-abe5-46e8-81a6-08f348053d05', NULL, '6fafa3a2-11fc-4785-a54f-56b877d6bada', '測試 Agents', true, true, '2026-04-21 14:48:02.813214+00', '2026-04-21 15:21:29.031286+00', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118');
INSERT INTO public.chat_session (pid, chat_session_uid, chat_project_uid, agent_uid, title, is_active, is_deleted, created_at, updated_at, owner_user_uid) VALUES (2, '79c67ed4-4340-4fca-b8ac-70b4a6fe8626', NULL, '6fafa3a2-11fc-4785-a54f-56b877d6bada', '測試 Agents', true, true, '2026-04-21 15:21:36.197661+00', '2026-04-22 13:16:37.53089+00', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118');
INSERT INTO public.chat_session (pid, chat_session_uid, chat_project_uid, agent_uid, title, is_active, is_deleted, created_at, updated_at, owner_user_uid) VALUES (3, '7bb990c7-f1c1-4b3b-9148-110b63679412', NULL, '6fafa3a2-11fc-4785-a54f-56b877d6bada', '輸出 2025 年最新的 3 則科技新聞訊息，簡短概要預覽即', true, true, '2026-04-22 13:19:38.04697+00', '2026-04-22 13:25:23.052089+00', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118');
INSERT INTO public.chat_session (pid, chat_session_uid, chat_project_uid, agent_uid, title, is_active, is_deleted, created_at, updated_at, owner_user_uid) VALUES (4, 'dfe5a05a-6fcf-4b7f-9f46-fb105a09e9fa', NULL, 'd742b9df-1554-43f1-af76-edefe11407f0', 'Code Reviewer 測試', true, true, '2026-04-22 13:28:11.399619+00', '2026-04-22 13:49:35.807576+00', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118');
INSERT INTO public.chat_session (pid, chat_session_uid, chat_project_uid, agent_uid, title, is_active, is_deleted, created_at, updated_at, owner_user_uid) VALUES (5, '2f8501f3-0eea-45cc-8f9f-cba9f6836e7b', NULL, 'd742b9df-1554-43f1-af76-edefe11407f0', 'Code Reviewer', true, false, '2026-04-22 13:49:57.544324+00', '2026-04-22 13:53:51.334908+00', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118');


--
-- Data for Name: llm_model; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.llm_model (pid, llm_model_uid, provider, model_id, display_name, is_active, is_deleted, created_at, updated_at, is_default, max_output_tokens) VALUES (3, 'c3bf7af1-b050-4ca4-a44a-6d570d5c928f', 'OpenRouter', 'anthropic/claude-sonnet-4', 'Claude Sonnet 4', true, false, '2026-04-16 16:38:15.161904+00', '2026-04-20 15:22:45.539403+00', true, 8192);
INSERT INTO public.llm_model (pid, llm_model_uid, provider, model_id, display_name, is_active, is_deleted, created_at, updated_at, is_default, max_output_tokens) VALUES (4, 'b04ccb8d-2815-4048-b4b0-545b0797f4cb', 'OpenRouter', 'anthropic/claude-haiku-4', 'Claude Haiku 4', true, false, '2026-04-16 16:38:15.161904+00', '2026-04-20 15:22:45.539403+00', false, 8192);
INSERT INTO public.llm_model (pid, llm_model_uid, provider, model_id, display_name, is_active, is_deleted, created_at, updated_at, is_default, max_output_tokens) VALUES (1, '5f534e16-fe7c-45e6-aa6a-ddb3d7fe27cc', 'OpenRouter', 'openai/gpt-4o', 'GPT-4o', true, false, '2026-04-16 16:38:15.161904+00', '2026-04-20 15:22:45.539403+00', false, 16384);
INSERT INTO public.llm_model (pid, llm_model_uid, provider, model_id, display_name, is_active, is_deleted, created_at, updated_at, is_default, max_output_tokens) VALUES (2, '00522668-9178-445f-ac09-651596247523', 'OpenRouter', 'openai/gpt-4o-mini', 'GPT-4o Mini', true, false, '2026-04-16 16:38:15.161904+00', '2026-04-20 15:22:45.539403+00', false, 16384);
INSERT INTO public.llm_model (pid, llm_model_uid, provider, model_id, display_name, is_active, is_deleted, created_at, updated_at, is_default, max_output_tokens) VALUES (5, '6847ff80-e100-4b5b-bcbc-b428baba0358', 'OpenRouter', 'google/gemini-2.5-flash', 'Gemini 2.5 Flash', true, false, '2026-04-16 16:38:15.161904+00', '2026-04-20 15:22:45.539403+00', false, 8192);


--
-- Data for Name: skill; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.skill (pid, skill_uid, owner_uid, name, description, file_path, original_filename, file_size, visibility, is_active, is_deleted, created_at, updated_at) VALUES (1, '219d6aad-1d77-46af-98df-0dd9bb6dfd9e', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118', 'Git 提交 Commit 當前分支', '將當前工作區的所有檔案, 全部提交至當前分支', 'data/skills/219d6aad-1d77-46af-98df-0dd9bb6dfd9e/commit-all.zip', 'commit-all.md', 1490, 'public', true, false, '2026-04-20 12:46:30.99085+00', '2026-04-20 13:00:09.805856+00');
INSERT INTO public.skill (pid, skill_uid, owner_uid, name, description, file_path, original_filename, file_size, visibility, is_active, is_deleted, created_at, updated_at) VALUES (3, '04386d11-6132-4007-8520-127624c9a845', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118', 'Git 合併當前分支到 main', '將當前工作分支合併到 main (遇到衝突會詢問)', 'data/skills/04386d11-6132-4007-8520-127624c9a845/merge-main.zip', 'merge-main.md', 1111, 'public', true, false, '2026-04-20 13:23:44.531482+00', '2026-04-20 13:23:48.599195+00');
INSERT INTO public.skill (pid, skill_uid, owner_uid, name, description, file_path, original_filename, file_size, visibility, is_active, is_deleted, created_at, updated_at) VALUES (5, 'ec201d44-35dc-4481-8c04-71328c566dbd', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118', 'Design-Base 後端規則文件', '針對 Fastapi 的後端規範', 'data/skills/ec201d44-35dc-4481-8c04-71328c566dbd/Design-Base 後端規則文件.zip', 'Design-Base 後端規則文件', 4441, 'private', true, false, '2026-04-22 13:36:38.886652+00', '2026-04-22 13:36:38.886652+00');
INSERT INTO public.skill (pid, skill_uid, owner_uid, name, description, file_path, original_filename, file_size, visibility, is_active, is_deleted, created_at, updated_at) VALUES (4, 'e3a3cc6a-e46c-4989-8958-58359e72055b', '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118', '簡易 Design Base 規則包', '涵蓋專案 overview 全端 UI/UX, 登入/權限的規範文件', 'data/skills/e3a3cc6a-e46c-4989-8958-58359e72055b/Design-Base.zip', 'Design-Base', 25001, 'public', true, false, '2026-04-22 13:31:57.854013+00', '2026-04-22 14:06:16.534382+00');


--
-- Data for Name: system_setting; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (1, '2423711f-3f3e-4b3f-b31d-3dc51db1f774', 'agent.max_skills', '10', 'integer', 'Agent 可關聯的 Skills 數量上限', true, true, false, '2026-04-20 14:13:39.426253+00', '2026-04-20 15:24:28.98781+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (2, '0b4aef83-5cc6-4c5a-8a57-87b34db9a582', 'chat.max_sessions_per_project', '3', 'integer', '每個 Project 可建立的 Session 數量上限', true, true, false, '2026-04-20 15:58:34.43814+00', '2026-04-20 15:58:34.43814+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (3, '6205b56c-77a6-4245-89e1-0d589af30b46', 'chat.max_projects_per_user', '5', 'integer', '每位使用者可建立的 Project 數量上限', true, true, false, '2026-04-20 15:58:34.43814+00', '2026-04-20 15:58:34.43814+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (4, '6691dadb-5626-44f0-8bdd-0c9e342147e5', 'memory.extractor_model', 'anthropic/claude-haiku-4-5', 'string', '記憶摘要使用的 LLM model（OpenRouter id）', false, true, false, '2026-04-20 15:58:34.524471+00', '2026-04-20 15:58:34.524471+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (5, '4576edcd-730c-48ba-b5f3-73d8d3beb865', 'memory.batch_size', '5', 'integer', '記憶批次大小（每 N 則訊息觸發一次摘要）', false, true, false, '2026-04-20 15:58:34.524471+00', '2026-04-20 15:58:34.524471+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (6, 'a3349c3d-a71c-4685-a62e-4c04d3951880', 'memory.idle_seconds', '60', 'integer', '記憶批次 idle 閾值（秒，超過則立即處理 buffer）', false, true, false, '2026-04-20 15:58:34.524471+00', '2026-04-20 15:58:34.524471+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (7, 'd0242929-b0f0-4ac9-9c68-1272ec14e64b', 'memory.skip_rules', '{"min_length": 15, "greeting_whitelist": ["hi", "hello", "好", "好的", "收到", "謝謝", "ok"], "max_tokens": 2000}', 'json', '記憶預篩規則（JSON：min_length / greeting_whitelist / max_tokens）', false, true, false, '2026-04-20 15:58:34.524471+00', '2026-04-20 15:58:34.524471+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (8, '4d7f3c77-8f3d-4252-a782-72f9b34adb46', 'rag.enabled', 'true', 'boolean', '是否啟用 RAG 檢索注入 system prompt', false, true, false, '2026-04-20 15:58:34.524471+00', '2026-04-20 15:58:34.524471+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (9, '240ef25f-67cf-47dc-8624-84b8ddfcece7', 'rag.top_k', '5', 'integer', 'RAG 檢索 top-k 數量', false, true, false, '2026-04-20 15:58:34.524471+00', '2026-04-20 15:58:34.524471+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (10, 'd5e463e9-cc52-49aa-ae9d-73b108dcf3e2', 'rag.min_score', '0.7', 'string', 'RAG cosine similarity 最小分數（0.0 ~ 1.0）', false, true, false, '2026-04-20 15:58:34.524471+00', '2026-04-20 15:58:34.524471+00');
INSERT INTO public.system_setting (pid, system_setting_uid, key, value, value_type, description, is_public, is_active, is_deleted, created_at, updated_at) VALUES (11, '08159228-b54f-40a1-838f-f5bb992c5ba9', 'chat.max_orphan_sessions_per_user', '10', 'integer', '每位使用者可建立的游離 Session（不屬於任何 Project）上限；硬上限 30', true, true, false, '2026-04-21 14:18:59.489036+00', '2026-04-21 14:18:59.489036+00');


--
-- Data for Name: user; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public."user" (pid, user_uid, username, account, hashed_password, role_uid, login_fail_count, locked_until, is_active, is_deleted, created_at, updated_at) VALUES (2, '4b8c4ccf-6838-44e4-8fc1-5b3e7a895118', 'Sapphire', 'Sapphire0912', '$2b$12$SGPuvLu4lJSXe3LrkXujr.JSRrjQOnQCVHFKtXDDHTXUp39mInKPq', 'd2aa25f6-8de7-4453-9a1c-e522e128eba6', 0, NULL, true, false, '2026-04-16 16:44:51.104387+00', '2026-04-16 16:45:52.624643+00');
INSERT INTO public."user" (pid, user_uid, username, account, hashed_password, role_uid, login_fail_count, locked_until, is_active, is_deleted, created_at, updated_at) VALUES (1, '68db209f-495a-4bb8-9e6a-f4bd1b123327', 'testuser', 'testaccount01', '$2b$12$bRPaA0H7socOVMHuJ5r0iuTsUh16gHadq8C68wtr.bqNBHvhxXhGi', 'f979fbe5-7d2a-4e1b-b85b-5a597e4093e0', 0, NULL, true, false, '2026-04-16 16:42:14.744549+00', '2026-04-20 13:05:45.8814+00');


--
-- Data for Name: user_role; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.user_role (pid, user_role_uid, name, description, is_active, is_deleted, created_at, updated_at) VALUES (1, 'd2aa25f6-8de7-4453-9a1c-e522e128eba6', 'admin', '系統管理員，可管理所有使用者與系統設定', true, false, '2026-04-16 16:38:14.964693+00', '2026-04-16 16:38:14.964693+00');
INSERT INTO public.user_role (pid, user_role_uid, name, description, is_active, is_deleted, created_at, updated_at) VALUES (2, 'f979fbe5-7d2a-4e1b-b85b-5a597e4093e0', 'member', '一般成員，僅可操作自身資源', true, false, '2026-04-16 16:38:14.964693+00', '2026-04-16 16:38:14.964693+00');


--
-- Name: agent_language_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.agent_language_pid_seq', 5, true);


--
-- Name: agent_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.agent_pid_seq', 2, true);


--
-- Name: agent_template_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.agent_template_pid_seq', 4, true);


--
-- Name: chat_attachment_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chat_attachment_pid_seq', 1, false);


--
-- Name: chat_memory_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chat_memory_pid_seq', 4, true);


--
-- Name: chat_message_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chat_message_pid_seq', 11, true);


--
-- Name: chat_project_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chat_project_pid_seq', 1, false);


--
-- Name: chat_session_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chat_session_pid_seq', 5, true);


--
-- Name: llm_model_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.llm_model_pid_seq', 5, true);


--
-- Name: skill_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.skill_pid_seq', 5, true);


--
-- Name: system_setting_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.system_setting_pid_seq', 11, true);


--
-- Name: user_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.user_pid_seq', 2, true);


--
-- Name: user_role_pid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.user_role_pid_seq', 2, true);


--
-- Name: agent_language agent_language_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_language
    ADD CONSTRAINT agent_language_pkey PRIMARY KEY (pid);


--
-- Name: agent agent_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent
    ADD CONSTRAINT agent_pkey PRIMARY KEY (pid);


--
-- Name: agent_skill agent_skill_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_skill
    ADD CONSTRAINT agent_skill_pkey PRIMARY KEY (agent_uid, skill_uid);


--
-- Name: agent_template agent_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_template
    ADD CONSTRAINT agent_template_pkey PRIMARY KEY (pid);


--
-- Name: chat_attachment chat_attachment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_attachment
    ADD CONSTRAINT chat_attachment_pkey PRIMARY KEY (pid);


--
-- Name: chat_memory chat_memory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_memory
    ADD CONSTRAINT chat_memory_pkey PRIMARY KEY (pid);


--
-- Name: chat_message chat_message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT chat_message_pkey PRIMARY KEY (pid);


--
-- Name: chat_project chat_project_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_project
    ADD CONSTRAINT chat_project_pkey PRIMARY KEY (pid);


--
-- Name: chat_session chat_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_session
    ADD CONSTRAINT chat_session_pkey PRIMARY KEY (pid);


--
-- Name: llm_model llm_model_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_model
    ADD CONSTRAINT llm_model_pkey PRIMARY KEY (pid);


--
-- Name: skill skill_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill
    ADD CONSTRAINT skill_pkey PRIMARY KEY (pid);


--
-- Name: system_setting system_setting_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_setting
    ADD CONSTRAINT system_setting_pkey PRIMARY KEY (pid);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (pid);


--
-- Name: user_role user_role_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT user_role_pkey PRIMARY KEY (pid);


--
-- Name: idx_agent_owner_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_owner_uid ON public.agent USING btree (owner_uid);


--
-- Name: idx_chat_attachment_session_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_attachment_session_uid ON public.chat_attachment USING btree (chat_session_uid);


--
-- Name: idx_chat_memory_embedding_hnsw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_memory_embedding_hnsw ON public.chat_memory USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_chat_memory_session_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_memory_session_uid ON public.chat_memory USING btree (chat_session_uid);


--
-- Name: idx_chat_message_session_uid_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_message_session_uid_created_at ON public.chat_message USING btree (chat_session_uid, created_at);


--
-- Name: idx_chat_project_owner_user_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_project_owner_user_uid ON public.chat_project USING btree (owner_user_uid);


--
-- Name: idx_chat_session_agent_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_session_agent_uid ON public.chat_session USING btree (agent_uid);


--
-- Name: idx_chat_session_owner_user_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_session_owner_user_uid ON public.chat_session USING btree (owner_user_uid);


--
-- Name: idx_chat_session_project_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_session_project_uid ON public.chat_session USING btree (chat_project_uid);


--
-- Name: idx_llm_model_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_model_provider ON public.llm_model USING btree (provider);


--
-- Name: idx_skill_owner_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_skill_owner_uid ON public.skill USING btree (owner_uid);


--
-- Name: uq_agent_agent_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_agent_agent_uid ON public.agent USING btree (agent_uid);


--
-- Name: uq_agent_language_agent_language_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_agent_language_agent_language_uid ON public.agent_language USING btree (agent_language_uid);


--
-- Name: uq_agent_language_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_agent_language_code ON public.agent_language USING btree (code) WHERE (is_deleted = false);


--
-- Name: uq_agent_language_default; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_agent_language_default ON public.agent_language USING btree (is_default) WHERE ((is_default = true) AND (is_deleted = false));


--
-- Name: uq_agent_template_agent_template_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_agent_template_agent_template_uid ON public.agent_template USING btree (agent_template_uid);


--
-- Name: uq_agent_template_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_agent_template_key ON public.agent_template USING btree (template_key) WHERE (is_deleted = false);


--
-- Name: uq_chat_attachment_chat_attachment_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_chat_attachment_chat_attachment_uid ON public.chat_attachment USING btree (chat_attachment_uid);


--
-- Name: uq_chat_memory_chat_memory_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_chat_memory_chat_memory_uid ON public.chat_memory USING btree (chat_memory_uid);


--
-- Name: uq_chat_message_chat_message_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_chat_message_chat_message_uid ON public.chat_message USING btree (chat_message_uid);


--
-- Name: uq_chat_project_chat_project_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_chat_project_chat_project_uid ON public.chat_project USING btree (chat_project_uid);


--
-- Name: uq_chat_session_chat_session_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_chat_session_chat_session_uid ON public.chat_session USING btree (chat_session_uid);


--
-- Name: uq_llm_model_default; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_llm_model_default ON public.llm_model USING btree (is_default) WHERE ((is_default = true) AND (is_deleted = false));


--
-- Name: uq_llm_model_llm_model_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_llm_model_llm_model_uid ON public.llm_model USING btree (llm_model_uid);


--
-- Name: uq_llm_model_model_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_llm_model_model_id ON public.llm_model USING btree (model_id);


--
-- Name: uq_skill_skill_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_skill_skill_uid ON public.skill USING btree (skill_uid);


--
-- Name: uq_system_setting_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_system_setting_key ON public.system_setting USING btree (key) WHERE (is_deleted = false);


--
-- Name: uq_system_setting_system_setting_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_system_setting_system_setting_uid ON public.system_setting USING btree (system_setting_uid);


--
-- Name: uq_user_account; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_user_account ON public."user" USING btree (account) WHERE (is_deleted = false);


--
-- Name: uq_user_role_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_user_role_name ON public.user_role USING btree (name) WHERE (is_deleted = false);


--
-- Name: uq_user_role_user_role_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_user_role_user_role_uid ON public.user_role USING btree (user_role_uid);


--
-- Name: uq_user_user_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_user_user_uid ON public."user" USING btree (user_uid);


--
-- Name: agent_language trg_agent_language_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_agent_language_set_updated_at BEFORE UPDATE ON public.agent_language FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: agent trg_agent_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_agent_set_updated_at BEFORE UPDATE ON public.agent FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: agent_template trg_agent_template_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_agent_template_set_updated_at BEFORE UPDATE ON public.agent_template FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: chat_attachment trg_chat_attachment_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_chat_attachment_set_updated_at BEFORE UPDATE ON public.chat_attachment FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: chat_project trg_chat_project_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_chat_project_set_updated_at BEFORE UPDATE ON public.chat_project FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: chat_session trg_chat_session_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_chat_session_set_updated_at BEFORE UPDATE ON public.chat_session FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: llm_model trg_llm_model_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_llm_model_set_updated_at BEFORE UPDATE ON public.llm_model FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: skill trg_skill_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_skill_set_updated_at BEFORE UPDATE ON public.skill FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: system_setting trg_system_setting_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_system_setting_set_updated_at BEFORE UPDATE ON public.system_setting FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: user_role trg_user_role_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_user_role_set_updated_at BEFORE UPDATE ON public.user_role FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: user trg_user_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_user_set_updated_at BEFORE UPDATE ON public."user" FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: agent fk_agent_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent
    ADD CONSTRAINT fk_agent_user FOREIGN KEY (owner_uid) REFERENCES public."user"(user_uid);


--
-- Name: chat_attachment fk_chat_attachment_session; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_attachment
    ADD CONSTRAINT fk_chat_attachment_session FOREIGN KEY (chat_session_uid) REFERENCES public.chat_session(chat_session_uid);


--
-- Name: chat_attachment fk_chat_attachment_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_attachment
    ADD CONSTRAINT fk_chat_attachment_user FOREIGN KEY (owner_user_uid) REFERENCES public."user"(user_uid);


--
-- Name: chat_memory fk_chat_memory_session; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_memory
    ADD CONSTRAINT fk_chat_memory_session FOREIGN KEY (chat_session_uid) REFERENCES public.chat_session(chat_session_uid);


--
-- Name: chat_message fk_chat_message_session; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT fk_chat_message_session FOREIGN KEY (chat_session_uid) REFERENCES public.chat_session(chat_session_uid);


--
-- Name: chat_project fk_chat_project_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_project
    ADD CONSTRAINT fk_chat_project_user FOREIGN KEY (owner_user_uid) REFERENCES public."user"(user_uid);


--
-- Name: chat_session fk_chat_session_agent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_session
    ADD CONSTRAINT fk_chat_session_agent FOREIGN KEY (agent_uid) REFERENCES public.agent(agent_uid);


--
-- Name: chat_session fk_chat_session_owner; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_session
    ADD CONSTRAINT fk_chat_session_owner FOREIGN KEY (owner_user_uid) REFERENCES public."user"(user_uid);


--
-- Name: chat_session fk_chat_session_project; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_session
    ADD CONSTRAINT fk_chat_session_project FOREIGN KEY (chat_project_uid) REFERENCES public.chat_project(chat_project_uid);


--
-- Name: skill fk_skill_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill
    ADD CONSTRAINT fk_skill_user FOREIGN KEY (owner_uid) REFERENCES public."user"(user_uid);


--
-- Name: user fk_user_user_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT fk_user_user_role FOREIGN KEY (role_uid) REFERENCES public.user_role(user_role_uid);


