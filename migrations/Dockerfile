# Coolify deploy 專用：把 V*.sql 烤進 flyway image，避免 runtime bind mount 失效
# 對應 docker-compose.yml 的 flyway service（build: ./migrations）
FROM flyway/flyway:10-alpine
COPY sql/ /flyway/sql/
