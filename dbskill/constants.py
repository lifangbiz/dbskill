"""
支持的数据库类型与默认端口，供 dbskill/utils、schema 及 api/admin 统一使用。
"""

# 需要 host/port/user/password（及多数需要 database）的类型
DB_TYPES_REQUIRING_HOST = (
    "postgres",
    "mysql",
    "mariadb",
    "oracle",
    "mssql",
    "db2",
    "dm",
    "kingbase",
)
# 仅需 database（文件路径）的类型
DB_TYPES_FILE_ONLY = ("sqlite",)
# 所有支持的 direct 类型
SUPPORTED_DB_TYPES = (*DB_TYPES_REQUIRING_HOST, *DB_TYPES_FILE_ONLY)

# 默认端口
DEFAULT_PORTS = {
    "postgres": 5432,
    "mysql": 3306,
    "mariadb": 3306,
    "oracle": 1521,
    "mssql": 1433,
    "db2": 50000,
    "dm": 5236,
    "kingbase": 54321,
}
