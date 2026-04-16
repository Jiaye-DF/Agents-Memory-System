CREATE TABLE IF NOT EXISTS agent_skill (
    agent_uid UUID NOT NULL,
    skill_uid UUID NOT NULL,
    PRIMARY KEY (agent_uid, skill_uid)
);

COMMENT ON TABLE agent_skill IS 'Agent 與 Skill 多對多關聯表';
