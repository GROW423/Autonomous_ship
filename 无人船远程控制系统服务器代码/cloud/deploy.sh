#!/bin/bash
# ============================================================
# 无人船云平台一键部署脚本
# 适用: Ubuntu 20.04/22.04, Debian 11/12 (x86_64/ARM64)
#
# 使用方法:
#   1. 先把 cloud/ 目录上传到服务器:
#      scp -r cloud/ user@your-server-ip:/tmp/usv-cloud/
#   2. SSH登录服务器, 运行:
#      sudo bash /tmp/usv-cloud/deploy.sh
#
# 脚本会自动:
#   - 安装 Docker 和 Docker Compose
#   - 交互式配置 .env
#   - 构建并启动所有服务
#   - 验证服务状态
#   - 打印访问地址和下一步操作
# ============================================================

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
prompt(){ echo -e "${BLUE}[INPUT]${NC} $1"; }

# 检查root
if [ "$EUID" -ne 0 ]; then
    error "请使用 sudo 运行此脚本"
    exit 1
fi

# 确定脚本所在目录 (cloud目录)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/usv-cloud"

echo ""
echo "============================================================"
echo "  无人船云平台一键部署"
echo "============================================================"
echo ""
info "项目目录: $SCRIPT_DIR"
info "安装目录: $INSTALL_DIR"
echo ""

# ============================================================
# 1. 安装 Docker
# ============================================================
info "检查 Docker..."
if command -v docker &> /dev/null; then
    info "Docker 已安装: $(docker --version)"
else
    info "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    info "Docker 安装完成"
fi

# 安装 Docker Compose 插件
if ! docker compose version &> /dev/null; then
    info "安装 Docker Compose 插件..."
    apt-get update -y
    apt-get install -y docker-compose-plugin
fi
info "Docker Compose: $(docker compose version)"

# ============================================================
# 2. 复制项目文件
# ============================================================
info "部署项目文件到 $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR"/
cp -r "$SCRIPT_DIR"/.env.example "$INSTALL_DIR"/.env.example 2>/dev/null || true

# ============================================================
# 3. 交互式配置 .env
# ============================================================
echo ""
prompt "=== 配置云平台参数 ==="
echo ""

# 获取服务器公网IP (尝试自动获取)
SERVER_IP=$(curl -s --max-time 5 ifconfig.me || curl -s --max-time 5 ipinfo.io/ip || echo "")
if [ -n "$SERVER_IP" ]; then
    prompt "检测到服务器公网IP: $SERVER_IP"
    read -p "确认使用此IP? [Y/n]: " use_auto_ip
    if [ "$use_auto_ip" = "n" ] || [ "$use_auto_ip" = "N" ]; then
        SERVER_IP=""
    fi
fi

if [ -z "$SERVER_IP" ]; then
    read -p "请输入服务器公网IP或域名: " SERVER_IP
    if [ -z "$SERVER_IP" ]; then
        error "IP不能为空"
        exit 1
    fi
fi

# 数据库密码
read -p "设置数据库密码 [默认: usv_$(date +%s)]: " DB_PASS
DB_PASS=${DB_PASS:-usv_$(date +%s)}

# JWT密钥 (自动生成)
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64)

# CORS (前端地址, 默认允许所有)
read -p "前端访问地址 (CORS), 多个用逗号分隔, * 表示允许所有 [默认: *]: " CORS_ORIGINS
CORS_ORIGINS=${CORS_ORIGINS:-*}

echo ""
info "配置汇总:"
echo "  服务器IP:   $SERVER_IP"
echo "  数据库密码: $DB_PASS"
echo "  JWT密钥:    ${JWT_SECRET:0:16}... (已自动生成)"
echo "  CORS:       $CORS_ORIGINS"
echo ""
read -p "确认配置并开始部署? [Y/n]: " confirm
if [ "$confirm" = "n" ] || [ "$confirm" = "N" ]; then
    info "已取消部署"
    exit 0
fi

# 写入 .env
cat > "$INSTALL_DIR/.env" << EOF
# PostgreSQL
POSTGRES_USER=usv
POSTGRES_PASSWORD=$DB_PASS
POSTGRES_DB=usv
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# MediaMTX (视频SFU)
MEDIAMTX_RTSP_PORT=8554
MEDIAMTX_WEBRTC_PORT=8889
MEDIAMTX_HLS_PORT=8888
MEDIAMTX_API_PORT=9997
MEDIAMTX_PUBLIC_IP=$SERVER_IP
MEDIAMTX_WEBRTC_URL=http://$SERVER_IP:8889

# MAVLink Gateway
MAVLINK_TCP_PORT=5760

# API Server
API_PORT=8000
SECRET_KEY=$JWT_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=$CORS_ORIGINS
LOG_LEVEL=INFO
EOF

info ".env 配置已写入 $INSTALL_DIR/.env"

# ============================================================
# 4. 开放防火墙端口
# ============================================================
info "配置防火墙..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp    # SSH
    ufw allow 8000/tcp  # API
    ufw allow 5760/tcp  # MAVLink
    ufw allow 8554/tcp  # RTSP
    ufw allow 8889/tcp  # WebRTC
    ufw allow 8888/tcp  # HLS
    # WebRTC使用UDP随机端口, 开放UDP范围
    ufw allow 40000:65535/udp
    echo "y" | ufw enable 2>/dev/null || true
    info "UFW防火墙已配置"
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=22/tcp
    firewall-cmd --permanent --add-port=8000/tcp
    firewall-cmd --permanent --add-port=5760/tcp
    firewall-cmd --permanent --add-port=8554/tcp
    firewall-cmd --permanent --add-port=8889/tcp
    firewall-cmd --permanent --add-port=8888/tcp
    firewall-cmd --permanent --add-port=40000-65535/udp
    firewall-cmd --reload
    info "firewalld已配置"
else
    warn "未检测到UFW/firewalld, 请手动开放防火墙端口"
fi

# 云服务商安全组提醒
warn "重要: 如果使用阿里云/腾讯云/华为云, 还需要在云控制台的'安全组'中开放以下端口:"
echo "  TCP: 22(SSH), 8000(API), 5760(MAVLink), 8554(RTSP), 8889(WebRTC), 8888(HLS)"
echo "  UDP: 40000-65535 (WebRTC媒体流)"
echo ""

# ============================================================
# 5. 构建并启动服务
# ============================================================
cd "$INSTALL_DIR"

info "构建Docker镜像 (首次可能需要3-5分钟)..."
docker compose build

info "启动所有服务..."
docker compose up -d

info "等待服务启动 (15秒)..."
sleep 15

# ============================================================
# 6. 验证
# ============================================================
echo ""
echo "============================================================"
info "服务状态:"
echo "============================================================"
docker compose ps

echo ""
info "验证API服务..."
if curl -s --max-time 5 http://localhost:8000/health | grep -q "ok"; then
    info "API服务正常 ✓"
else
    warn "API服务可能未就绪, 请稍后检查: docker compose logs api-server"
fi

info "验证MAVLink网关..."
if docker compose ps mavlink-gateway | grep -q "Up"; then
    info "MAVLink网关正常 ✓ (监听TCP 5760)"
else
    warn "MAVLink网关异常, 检查: docker compose logs mavlink-gateway"
fi

info "验证MediaMTX..."
if docker compose ps mediamtx | grep -q "Up"; then
    info "MediaMTX视频SFU正常 ✓"
else
    warn "MediaMTX异常, 检查: docker compose logs mediamtx"
fi

# ============================================================
# 7. 完成
# ============================================================
echo ""
echo "============================================================"
echo -e "${GREEN}  部署完成!${NC}"
echo "============================================================"
echo ""
echo "  安装目录: $INSTALL_DIR"
echo ""
echo "  访问地址:"
echo "    API文档:    http://$SERVER_IP:8000/docs"
echo "    健康检查:   http://$SERVER_IP:8000/health"
echo "    视频WebRTC: http://$SERVER_IP:8889"
echo ""
echo "  船载端配置 (修改这两个文件):"
echo "    onboard/config/mavlink-router.conf"
echo "      Address=$SERVER_IP  Port=5760"
echo "    onboard/scripts/ffmpeg_push.sh"
echo "      CLOUD_RTSP=rtsp://$SERVER_IP:8554/usv/camera1"
echo ""
echo "  前端配置 (修改 web/.env):"
echo "    VITE_API_BASE_URL=http://$SERVER_IP:8000"
echo "    VITE_WS_URL=ws://$SERVER_IP:8000/ws"
echo "    VITE_VIDEO_URL=http://$SERVER_IP:8889"
echo ""
echo "  常用命令:"
echo "    查看日志:   cd $INSTALL_DIR && docker compose logs -f"
echo "    重启服务:   docker compose restart"
echo "    停止服务:   docker compose down"
echo "    查看状态:   docker compose ps"
echo ""
echo "  下一步:"
echo "    1. 配置船载端的云服务器地址 (见上)"
echo "    2. 船端上电, 4G联网后会自动连接云平台"
echo "    3. 前端 npm run dev 启动, 注册账号, 添加船 (MAVLink系统ID与船端一致)"
echo "    4. 在船控制台查看实时状态、遥控、编辑路径"
echo ""
echo "  注意: 云服务商安全组必须开放上述端口, 否则外部无法访问!"
echo "============================================================"
