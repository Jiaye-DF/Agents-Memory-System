"""Redis queue / DLQ key 常數集中地（v1.3.1）。

避免 worker / health endpoint 各自硬寫字串導致改名漏改。
"""

# 記憶 pipeline：worker BRPOP 與 health LLEN 共用
MEMORY_QUEUE_KEY = "chat:memory:queue"
MEMORY_DLQ_KEY = "chat:memory:dlq"

# v1.3.5：跨層聚合 worker（project / user）
PROJECT_MEMORY_QUEUE_KEY = "project:memory:queue"
PROJECT_MEMORY_DLQ_KEY = "project:memory:dlq"
USER_MEMORY_QUEUE_KEY = "user:memory:queue"
USER_MEMORY_DLQ_KEY = "user:memory:dlq"
