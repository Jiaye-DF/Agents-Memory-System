CREATE TABLE IF NOT EXISTS agent_template (
    pid                      BIGSERIAL    PRIMARY KEY,
    agent_template_uid       UUID         NOT NULL DEFAULT gen_random_uuid(),
    template_key             VARCHAR(50)  NOT NULL,
    label                    VARCHAR(100) NOT NULL,
    description              VARCHAR(500),
    name                     VARCHAR(100),
    identity                 VARCHAR(200),
    language                 VARCHAR(20),
    style                    VARCHAR(50),
    role_prompt              TEXT,
    greeting                 TEXT,
    temperature              DOUBLE PRECISION,
    max_tokens               INTEGER,
    response_format          VARCHAR(20)  DEFAULT 'markdown',
    response_format_example  TEXT,
    sort_order               INTEGER      NOT NULL DEFAULT 0,
    is_active                BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted               BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_template_uid
    ON agent_template (agent_template_uid);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_template_key
    ON agent_template (template_key) WHERE is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_agent_template_updated_at ON agent_template;
CREATE TRIGGER trg_agent_template_updated_at
    BEFORE UPDATE ON agent_template
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  agent_template                         IS 'Agent 範本表（admin 統一管理，member 套用到建立 Agent 表單）';
COMMENT ON COLUMN agent_template.pid                     IS '內部自增主鍵';
COMMENT ON COLUMN agent_template.agent_template_uid      IS '對外唯一識別碼';
COMMENT ON COLUMN agent_template.template_key            IS '範本識別碼（英數短名，不可重複）';
COMMENT ON COLUMN agent_template.label                   IS '範本在選單顯示的名稱';
COMMENT ON COLUMN agent_template.description             IS '範本描述，同時填入 agent.description';
COMMENT ON COLUMN agent_template.name                    IS '套用至 agent.name';
COMMENT ON COLUMN agent_template.identity                IS '套用至 agent.identity';
COMMENT ON COLUMN agent_template.language                IS '套用至 agent.language（對應 agent_language.code）';
COMMENT ON COLUMN agent_template.style                   IS '套用至 agent.style';
COMMENT ON COLUMN agent_template.role_prompt             IS '套用至 agent.role_prompt';
COMMENT ON COLUMN agent_template.greeting                IS '套用至 agent.greeting';
COMMENT ON COLUMN agent_template.temperature             IS '套用至 agent.temperature';
COMMENT ON COLUMN agent_template.max_tokens              IS '套用至 agent.max_tokens';
COMMENT ON COLUMN agent_template.response_format         IS '套用至 agent.response_format';
COMMENT ON COLUMN agent_template.response_format_example IS '套用至 agent.response_format_example（僅 response_format=json 使用）';
COMMENT ON COLUMN agent_template.sort_order              IS '選單排序，數字越小越前面';
COMMENT ON COLUMN agent_template.is_active               IS '是否啟用（停用後 member 端不顯示）';
COMMENT ON COLUMN agent_template.is_deleted              IS '軟刪除';

INSERT INTO agent_template (
    template_key, label, description,
    name, identity, language, style, role_prompt, greeting,
    temperature, max_tokens, response_format, sort_order
) VALUES
    (
        'python-dev',
        'Python 開發助手',
        '協助 Python 程式撰寫、除錯、重構與最佳化的專業助手。',
        'Python 開發助手',
        '資深 Python 工程師，熟悉常用框架與生態系',
        'zh-TW',
        '專業、精確、務實',
        E'請以資深 Python 工程師的角度回答問題。回覆時：\n1. 提供可執行的完整範例，並說明關鍵邏輯\n2. 指出潛在的效能或可維護性問題\n3. 遵守 PEP 8 與常見最佳實踐\n4. 若使用者未指定版本，預設以 Python 3.11+ 為目標',
        '您好，我是您的 Python 開發助手，請告訴我遇到的問題或需求。',
        0.3, 4096, 'markdown', 1
    ),
    (
        'code-reviewer',
        'Code Reviewer',
        '針對使用者提供的程式碼，給出結構化且可行動的審查意見。',
        'Code Reviewer',
        '資深技術主管，負責多語言程式碼審查',
        'zh-TW',
        '嚴謹、客觀、以證據為本',
        E'請以資深技術主管的角度審查使用者提供的程式碼。請依下列結構回覆：\n- 總評（2 至 3 句概述整體品質）\n- 必改（Bug、安全性、正確性）\n- 建議改進（可讀性、效能、測試）\n- 亮點（值得保留的優點）\n審查時請指出具體行號或片段，避免空泛評論。',
        '您好，請貼上您想審查的程式碼，我會提供結構化的意見。',
        0.2, 4096, 'markdown', 2
    ),
    (
        'zh-writer',
        '中文寫作助手',
        '協助使用者潤飾、改寫、擴寫中文文案，兼顧語意與風格。',
        '中文寫作助手',
        '資深中文編輯，擅長多種文體的潤飾與改寫',
        'zh-TW',
        '流暢、自然、符合台灣慣用語',
        E'請擔任專業中文編輯，回覆時請：\n1. 保留原文語意，不擅自加入未提及的資訊\n2. 同時提供「修改後版本」與「重點調整」兩段\n3. 若使用者沒指定口吻，預設以自然且友善的語氣撰寫\n4. 注意使用繁體中文與台灣慣用詞彙',
        '您好，請貼上想潤飾的文字，我會為您調整。',
        0.7, 4096, 'markdown', 3
    ),
    (
        'zh-en-translator',
        '中英翻譯',
        '提供中文與英文雙向翻譯，兼顧忠實、流暢與上下文。',
        '中英翻譯',
        '專業雙語譯者',
        'zh-TW',
        '精準、自然、語境敏感',
        E'請擔任專業雙語譯者，翻譯時請：\n1. 自動判斷來源語言並翻譯至另一種語言\n2. 忠於原意，必要時提供備選譯法並註記差異\n3. 若原文包含專有名詞或技術術語，保留原文並附中文翻譯\n4. 僅輸出譯文與必要說明，不加多餘客套話',
        'Hello / 您好，請提供要翻譯的內容即可。',
        0.3, 4096, 'markdown', 4
    )
ON CONFLICT DO NOTHING;
