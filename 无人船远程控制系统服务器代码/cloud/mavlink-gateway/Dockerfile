FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# 安装系统依赖（本地调试构建：apt 使用清华镜像）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
        /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null || true; \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖（本地调试构建：pip 使用清华镜像）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制代码
COPY . .

# 创建日志目录
RUN mkdir -p /app/logs

# 启动
CMD ["python", "main.py"]
