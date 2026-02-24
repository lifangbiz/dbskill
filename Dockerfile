FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码与默认配置（运行时可用 -v 挂载 host config.yaml 覆盖）
COPY api/ api/
COPY dbskill/ dbskill/
COPY dbskill/config.example.yaml ./config.yaml

# 数据持久化目录（admin.db、logs）
RUN mkdir -p /app/data /app/logs
ENV ADMIN_DB_PATH=/app/data/admin.db
# 生产环境请通过 -e 或运行脚本覆盖
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
