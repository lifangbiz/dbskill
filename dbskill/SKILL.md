---
name: dbskill
description: 为 Agent 提供统一的数据库访问能力，支持 Direct 直连与 API 模式、多库与审计。在需要查库表结构、执行只读查询或写操作时使用。
---

# DBSkill Skill

为 Agent 提供统一的数据库访问能力，支持：

- Direct 模式：脚本直连数据库；
- API 模式：通过 Web 服务 API 访问数据库；
- 多数据库、多权限级别与审计日志。

## 目录结构

```text
dbskill/
  ├── SKILL.md
  ├── scripts/
  │   ├── schema.py
  │   ├── query.py
  │   └── execute.py
  └── config.example.yaml
```

## 配置示例

在项目根或 `dbskill/` 目录下创建 `config.yaml`。每个 `databases.<别名>` 必须配置 **mode**：`direct` 或 `api`。示例：

```yaml
databases:
  main:
    mode: direct
    type: postgres
    host: localhost
    port: 5432
    user: postgres
    password: example
    database: mydb
    permission: readonly

default_db: main

audit:
  enabled: true
  log_dir: ./logs/audit
  retention_days: 30
```

Direct / API 双模式示例见 `dbskill/config.example.yaml`。

## Direct 模式调用示例

```python
from dbskill.scripts.schema import get_schema
from dbskill.scripts.query import run_query
from dbskill.scripts.execute import run_execute

# 读取主库的表结构
schema = get_schema(table="users", db_alias="main")

# 只读查询（内部强制只允许 SELECT/CTE）
rows = run_query(
    sql="SELECT id, name FROM users WHERE status = :status",
    params={"status": "active"},
    db_alias="main",
)

# 写操作（仅 permission 为 write/full 时允许）
affected = run_execute(
    sql="UPDATE users SET name = :name WHERE id = :id",
    params={"name": "new-name", "id": 1},
    db_alias="main",
)
```

## API 模式（概览）

当 `config.yaml` 中某个数据库配置为 **mode: api** 并填写 `api_url`、`api_token` 时，Skill 将通过 HTTP 调用 Web 服务执行 `schema`/`query`/`execute`。示例见 `dbskill/config.example.yaml` 中的 `analytics` 库。

