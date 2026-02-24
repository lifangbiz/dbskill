# DBSkill

[中文](#中文) | [English](#english)

---

<a name="中文"></a>

## 中文

为 AI Agent 提供数据库访问能力的 Skill 工具包。Agent 可通过它查询表结构、执行只读 SQL、执行写操作（需相应权限），支持 **Direct**（直连数据库）与 **API**（通过 HTTP API 调用数据库）两种使用方式。

### Direct 模式 vs API 模式

| 项目 | Direct 模式 | API 模式 |
|------|-------------|----------|
| 含义 | Skill 脚本直接连数据库 | Skill 通过 API中转 连接数据库 |
| 适用场景 | Agent 与数据库在同一环境、可直连 | 数据库在远端，或需集中鉴权、审计 |
| 是否需要启动 Web 服务 | **否** | **是**（需先部署并运行 DBSkill API 服务） |
| 权限与审计 | 本地 `config.yaml` 中按库配置 `permission`；本地文件记录审计日志 | 服务端按 API Key 关联账号权限；服务端记录审计日志；支持多用户 |

- **能用 Direct 就用 Direct**：配置简单，无需额外服务。
- **用 API 时**：数据库在远程、多端共用同一套库，或需要统一管理账号/API Key 与审计时。

### 安装

1. 复制本项目下的 **dbskill** 目录到应用的 skills 目录。
2. 安装 Python 依赖：进入复制后的 **dbskill** 目录，执行：
   ```bash
   pip install -r requirements.txt
   ```
3. 在 dbskill 目录内，将 config.example.yaml 重命名为 config.yaml，并修改其中配置信息：
   - **permission**：`readonly` 仅查；`write` 可 INSERT/UPDATE；`full` 还可 DELETE。
   - **default_db**（可选）：调用时不指定使用哪个库时，默认使用的库（填 `databases` 里某个名称）。若 **只有一个库** 且未配置 `default_db`，会自动使用该库；多库时建议配置，否则调用时需显式传库名。
4. 在 AI 应用中测试使用。

### API 安装

如果上一步 config.yaml 中全部使用直连数据库，则无需部署 API；若有数据库无法直连或希望集中管控，则需要部署 API，Skill 通过 API 中转访问数据库。

1. 将本项目代码复制到服务器中，并安装依赖
```bash
pip install -e .
# 或
uv sync
```
2. 复制 server.example.yaml 为 server.yaml 并修改其配置
- **admin_db.path**：管理后台与 API 元数据存储（SQLite），默认 `./admin.db`。
- **logging**：应用日志文件路径与切分。`file` 为路径（不写则仅控制台）；`rotation.type` 为 `size`（按大小，需 `max_bytes`、`backup_count`）或 `time`（按天，需 `when`、`interval`、`backup_count`）。
- **api_audit**：API 请求审计（存 admin.db）的开关与 `retention_days`。

**3. 启动 Web 服务**

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

生产环境建议在 `server.yaml` 中设置 `session_secret`（用于管理后台会话）。

**4. 使用 Docker 部署（可选）**

构建镜像后，可用脚本一键启动（默认挂载当前目录 `data/` 持久化 admin.db，若存在则挂载 `config.yaml`，端口 8000；可通过环境变量 `PORT`、`SESSION_SECRET`、`CONFIG_PATH`、`DATA_PATH` 覆盖）：

```bash
docker build -t dbskill .
chmod +x scripts/docker-run.sh
./scripts/docker-run.sh
```

需自定义时可通过环境变量覆盖再执行脚本，例如：

```bash
PORT=9000 ./scripts/docker-run.sh
```

或直接运行容器（挂载的 `server.yaml` 中可设置 `session_secret`；未设置时使用默认值，生产环境勿用默认值）：

```bash
docker run -d -p 8000:8000 -v $(pwd)/server.yaml:/app/server.yaml -v $(pwd)/data:/app/data dbskill
```

需保证容器内能访问数据库；`data/` 用于持久化 admin.db；`server.yaml` 中可设置 `admin_db.path: /app/data/admin.db` 使数据落盘到挂载卷。

**5. 登录后台配置**

登录后台，默认账号：admin admin123。在后台，可配置数据库连接、api key、查看审计日志。

## 支持数据库列表

| 类型（config 中 type） | 默认端口 | 说明 |
|------------------------|----------|------|
| sqlite | — | 文件库，`database` 填文件路径；无需额外驱动 |
| postgres | 5432 | 需安装 `psycopg2-binary`（已含于 dbskill/requirements.txt） |
| mysql | 3306 | 需安装 `pymysql`（已含于 dbskill/requirements.txt） |
| mariadb | 3306 | 同 mysql，使用 pymysql |
| oracle | 1521 | 需自行安装驱动，如 `oracledb` 或 `cx_Oracle` |
| mssql | 1433 | 需自行安装驱动，如 `pyodbc` 或 `pymssql` |
| db2 | 50000 | 需自行安装 IBM DB2 驱动 |
| dm | 5236 | 达梦，需自行安装达梦驱动 |
| kingbase | 54321 | 人大金仓，需自行安装金仓驱动 |

SQLite、PostgreSQL、MySQL/MariaDB 的依赖已包含在 `dbskill/requirements.txt` 中，执行 `pip install -r requirements.txt` 即可。使用上表其他数据库时，需在 **dbskill 目录下** 按需安装对应驱动：

| 数据库 | 安装命令 |
|--------|----------|
| Oracle | `pip install oracledb` |
| SQL Server (MSSQL) | `pip install pyodbc` 或 `pip install pymssql`（pyodbc 需系统已安装 ODBC 驱动） |
| IBM DB2 | `pip install ibm-db`（SQLAlchemy 需另装 `ibm_db_sa`） |
| 达梦 (DM) | `pip install dmPython`（部分环境需配置 `DM_HOME`、`LD_LIBRARY_PATH` 等） |
| 人大金仓 (Kingbase) | `pip install ksycopg2` |

---

<a name="english"></a>

## English

DBSkill is a Skill toolkit that gives AI Agents database access. Agents can query table schemas, run read-only SQL, and run write operations (with appropriate permissions). It supports **Direct** (connect to the database directly) and **API** (call the database via HTTP API) modes.

### Direct vs API mode

| Item | Direct mode | API mode |
|------|-------------|----------|
| Meaning | Skill scripts connect to the DB directly | Skill connects via API proxy |
| Use case | Agent and DB in same environment, direct access | DB remote, or need central auth/audit |
| Web server required | **No** | **Yes** (deploy and run DBSkill API service first) |
| Permissions & audit | Configure `permission` per DB in local `config.yaml`; audit logs to local files | Server maps API Key to account permissions; server-side audit logs; multi-user |

- **Prefer Direct** when possible: simple config, no extra service.
- **Use API** when the DB is remote, multiple clients share the same DB set, or you need centralized API Key and audit management.

### Installation

1. Copy the **dbskill** directory from this project into your application’s skills directory.
2. Install Python dependencies: enter the copied **dbskill** directory and run:
   ```bash
   pip install -r requirements.txt
   ```
3. Inside the dbskill directory, rename `config.example.yaml` to `config.yaml` and edit:
   - **permission**: `readonly` (query only); `write` (INSERT/UPDATE); `full` (also DELETE).
   - **default_db** (optional): default database when none is specified (must be one of the names under `databases`). If there is **only one** database and `default_db` is not set, that database is used automatically; with multiple databases, set `default_db` or pass the database name explicitly when calling.
4. Test from your AI application.

### API installation

If all databases in `config.yaml` use direct connection, you do not need to deploy the API. Deploy the API when some databases cannot be reached directly or you want central control; the Skill will access the database through the API.

1. Copy this project to the server and install dependencies:
```bash
pip install -e .
# or
uv sync
```
2. Copy `server.example.yaml` to `server.yaml` and adjust:
- **admin_db.path**: Path for admin UI and API metadata (SQLite), default `./admin.db`.
- **logging**: App log file path and rotation. `file` is the path (omit for console only); `rotation.type` is `size` (by size, needs `max_bytes`, `backup_count`) or `time` (by day, needs `when`, `interval`, `backup_count`).
- **api_audit**: Toggle and `retention_days` for API request audit (stored in admin.db).

**3. Start the web service**

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

For production, set `session_secret` in `server.yaml` (used for admin session).

**4. Docker deployment (optional)**

After building the image, you can start with the script (default: mount current `data/` for admin.db persistence; mount `config.yaml` if present; port 8000; override with env vars `PORT`, `SESSION_SECRET`, `CONFIG_PATH`, `DATA_PATH`):

```bash
docker build -t dbskill .
chmod +x scripts/docker-run.sh
./scripts/docker-run.sh
```

Override with environment variables as needed, e.g.:

```bash
PORT=9000 ./scripts/docker-run.sh
```

Or run the container directly (you can set `session_secret` in the mounted `server.yaml`; if unset, a default is used—do not use the default in production):

```bash
docker run -d -p 8000:8000 -v $(pwd)/server.yaml:/app/server.yaml -v $(pwd)/data:/app/data dbskill
```

Ensure the container can reach the database; use `data/` for admin.db persistence; in `server.yaml` you can set `admin_db.path: /app/data/admin.db` so data is stored on the mounted volume.

**5. Admin UI**

Log in to the admin UI; default credentials: admin / admin123. There you can configure database connections, API keys, and view audit logs.

### Supported databases

| type (in config) | Default port | Notes |
|------------------|--------------|-------|
| sqlite | — | File-based; `database` is file path; no extra driver |
| postgres | 5432 | Use `psycopg2-binary` (in dbskill/requirements.txt) |
| mysql | 3306 | Use `pymysql` (in dbskill/requirements.txt) |
| mariadb | 3306 | Same as mysql, use pymysql |
| oracle | 1521 | Install driver separately (see below) |
| mssql | 1433 | Install driver separately (see below) |
| db2 | 50000 | Install IBM DB2 driver separately |
| dm | 5236 | DM (DaMeng); install driver separately |
| kingbase | 54321 | Kingbase; install driver separately |

SQLite, PostgreSQL, and MySQL/MariaDB are covered by `dbskill/requirements.txt`. For other databases, install the driver **inside the dbskill directory** as needed:

| Database | Install command |
|----------|-----------------|
| Oracle | `pip install oracledb` |
| SQL Server (MSSQL) | `pip install pyodbc` or `pip install pymssql` (pyodbc may require system ODBC driver) |
| IBM DB2 | `pip install ibm-db` (for SQLAlchemy also install `ibm_db_sa`) |
| DM (DaMeng) | `pip install dmPython` (some environments need `DM_HOME`, `LD_LIBRARY_PATH`, etc.) |
| Kingbase | `pip install ksycopg2` |
