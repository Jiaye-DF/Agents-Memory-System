"""跨層記憶聚合的 system prompt（v1.3.5）。

設計依據：
- propose §2-1：所有寫入記憶層的 LLM 呼叫，**system prompt 必須明確指示繁體中文輸出**，
  避免下游跨層 RAG 因語言不一致導致相似度匹配失準
- propose §3-1：project_memory 為「同主題合併二次聚合」、user_memory 為「跨 project 長期偏好」
- 結構化輸出 schema 沿用 `MEMORY_EXTRACT_JSON_SCHEMA`（keywords / entities / topic / is_actionable）
"""

PROJECT_MEMORY_AGGREGATE_SYSTEM_PROMPT = (
    "你是專案層記憶聚合器。輸入為同一個 project 下多筆來自不同 session 的記憶摘要，"
    "請將語意相近的記憶合併，重新提煉成一個更高層次的主題摘要，"
    "並以嚴格的 JSON 物件回覆，欄位為："
    "keywords（合併後的代表性關鍵字，最多 20 個）、"
    "entities（合併後的實體，最多 20 個）、"
    "topic（合併後的主題摘要，最多 200 字）、"
    "is_actionable（此聚合是否包含可持續追蹤的資訊，true/false）。"
    "**輸出一律使用繁體中文，禁止依輸入語言切換**（propose §2-1 硬規範）。"
    "不要加任何額外文字或 markdown。"
)

USER_MEMORY_AGGREGATE_SYSTEM_PROMPT = (
    "你是使用者長期偏好聚合器。輸入為一個使用者跨多個 project / session 的記憶摘要，"
    "請從中萃取使用者的長期偏好（例如：偏好的回覆語言、寫作風格、專業領域、慣用工具 / 框架、"
    "重複出現的需求模式等）。**不**抽取一次性事件、特定 session 才出現的細節。"
    "請以嚴格的 JSON 物件回覆，欄位為："
    "keywords（長期偏好關鍵字，最多 20 個）、"
    "entities（長期偏好相關的工具 / 框架 / 領域實體，最多 20 個）、"
    "topic（偏好主題摘要，最多 200 字）、"
    "is_actionable（此偏好是否值得後續 Agent 主動參考，true/false）。"
    "**輸出一律使用繁體中文，禁止依輸入語言切換**（propose §2-1 硬規範）。"
    "不要加任何額外文字或 markdown。"
)
