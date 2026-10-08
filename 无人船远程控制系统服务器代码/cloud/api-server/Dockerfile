FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# 本地调试构建：apt 使用清华镜像（原版为 deb.debian.org，国内慢）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
        /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null || true; \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 本地调试构建：pip 使用清华镜像
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

# 本地调试用单 worker，避免多 worker 并发 create_all 建表竞态（生产可改回 2）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
