#!/bin/bash
# ============================================================
# 无人船船载端系统初始化脚本
# 适用平台: OrangePi Zero2W (全志H618) / Debian/Ubuntu ARM64
# 功能: 安装依赖、配置串口、安装mavlink-router和go2rtc
# 使用: sudo bash system_setup.sh
# ============================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    log_error "请使用 sudo 运行此脚本"
    exit 1
fi

WORK_DIR="/opt/usv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

log_info "工作目录: $WORK_DIR"
log_info "项目目录: $PROJECT_DIR"

# ============================================================
# 1. 系统更新与基础依赖
# ============================================================
log_info "更新软件源..."
apt-get update -y
apt-get upgrade -y

log_info "安装基础依赖..."
apt-get install -y \
    python3 python3-pip python3-dev python3-venv \
    git build-essential cmake pkg-config \
    libssl-dev libgps-dev \
    i2c-tools spi-tools \
    dos2unix curl wget htop vim \
    libgpiod2 gpiod libgpiod-dev \
    network-manager modemmanager \
    usbutils udev \
    ffmpeg

# ============================================================
# 2. 配置硬件串口 (UART) - 接Pixhawk TELEM2
# ============================================================
log_info "配置UART串口..."

# OrangePi Zero2W 启用UART1 (GPIO8=TX, GPIO10=RX)
# 通过armbian-config或overlay启用
if [ -f /boot/orangepiEnv.txt ]; then
    # 检查是否已添加uart1
    if ! grep -q "uart1" /boot/orangepiEnv.txt 2>/dev/null; then
        echo "overlays=uart1" >> /boot/orangepiEnv.txt
        log_info "已在 /boot/orangepiEnv.txt 添加 uart1 overlay"
    else
        log_info "uart1 overlay 已配置"
    fi
elif [ -f /boot/armbianEnv.txt ]; then
    if ! grep -q "uart1" /boot/armbianEnv.txt 2>/dev/null; then
        echo "overlays=uart1" >> /boot/armbianEnv.txt
        log_info "已在 /boot/armbianEnv.txt 添加 uart1 overlay"
    else
        log_info "uart1 overlay 已配置"
    fi
else
    log_warn "未找到 /boot/orangepiEnv.txt 或 /boot/armbianEnv.txt"
    log_warn "请手动通过 armbian-config -> System -> Hardware 启用 uart1"
fi

# 禁用串口控制台（如果有的话）
systemctl disable serial-getty@ttyS1.service 2>/dev/null || true
systemctl stop serial-getty@ttyS1.service 2>/dev/null || true

# ============================================================
# 3. 配置4G模块 (移远EC200S / 通用PPP)
# ============================================================
log_info "配置4G模块..."

# 安装PPP和拨号工具
apt-get install -y ppp pptp-linux wvdial

# 配置wvdial (EC200S通常识别为 /dev/ttyUSB0-2)
cat > /etc/wvdial.conf << 'EOF'
[Dialer 4g]
Modem = /dev/ttyUSB2
Baud = 115200
Init = ATZ
Init2 = ATQ0 V1 E1 S0=0 &C1 &D2 +FCLASS=0
Init3 = AT+CGDCONT=1,"IP","3gnet"
Phone = *99#
Username = ""
Password = ""
Auto DNS = 1
Check Def Route = 1
EOF

log_info "4G拨号配置已写入 /etc/wvdial.conf"
log_warn "APN根据运营商调整: 移动=cmnet, 联通=3gnet, 电信=ctnet"

# 也可以用NetworkManager管理4G（推荐）
nmcli device status 2>/dev/null || true

# ============================================================
# 4. 创建工作目录与Python虚拟环境
# ============================================================
log_info "创建工作目录..."
mkdir -p $WORK_DIR/{config,logs,scripts,services}

# 创建Python虚拟环境
log_info "创建Python虚拟环境..."
python3 -m venv $WORK_DIR/venv
source $WORK_DIR/venv/bin/activate

# 升级pip
pip install --upgrade pip setuptools wheel

# 安装Python依赖
log_info "安装Python依赖..."
pip install \
    pymavlink \
    pyserial \
    python-periphery \
    gpiod \
    pyyaml \
    requests \
    websocket-client

deactivate

# ============================================================
# 5. 安装 mavlink-router
# ============================================================
log_info "安装 mavlink-router..."

cd /tmp
if [ -d mavlink-router ]; then
    rm -rf mavlink-router
fi
git clone https://github.com/mavlink-router/mavlink-router.git
cd mavlink-router
git submodule update --init --recursive

# 编译
meson setup build
ninja -C build

# 安装
install -m 0755 build/src/mavlink-routerd /usr/local/bin/mavlink-routerd

log_info "mavlink-router 安装完成: $(which mavlink-routerd)"

# ============================================================
# 6. 安装 go2rtc (视频流)
# ============================================================
log_info "安装 go2rtc..."

GO2RTC_VERSION="1.9.8"
GO2RTC_ARCH="linux_arm64"

cd /tmp
wget -q "https://github.com/AlexxIT/go2rtc/releases/download/v${GO2RTC_VERSION}/go2rtc_${GO2RTC_ARCH}.tar.gz" -O go2rtc.tar.gz
tar -xzf go2rtc.tar.gz
install -m 0755 go2rtc /usr/local/bin/go2rtc

log_info "go2rtc 安装完成: $(which go2rtc)"

# 安装v4l2工具（摄像头调试）
apt-get install -y v4l-utils

# ============================================================
# 7. 部署项目文件到工作目录
# ============================================================
log_info "部署项目文件..."

# 复制配置文件
cp -f $PROJECT_DIR/config/mavlink-router.conf $WORK_DIR/config/
cp -f $PROJECT_DIR/config/go2rtc.yaml $WORK_DIR/config/
cp -f $PROJECT_DIR/config/feeder_config.yaml $WORK_DIR/config/
cp -f $PROJECT_DIR/config/sensor_config.yaml $WORK_DIR/config/

# 复制Python服务
cp -f $PROJECT_DIR/services/feeder_control.py $WORK_DIR/services/
cp -f $PROJECT_DIR/services/sensor_monitor.py $WORK_DIR/services/
cp -f $PROJECT_DIR/services/boat_identity.py $WORK_DIR/services/

# 复制辅助脚本
cp -f $PROJECT_DIR/scripts/*.sh $WORK_DIR/scripts/ 2>/dev/null || true

# 设置权限
chmod +x $WORK_DIR/scripts/*.sh 2>/dev/null || true
chmod +x $WORK_DIR/services/*.py

# 转换换行符（防止Windows编辑导致CRLF）
find $WORK_DIR -name "*.sh" -exec dos2unix {} \; 2>/dev/null || true
find $WORK_DIR -name "*.py" -exec dos2unix {} \; 2>/dev/null || true
find $WORK_DIR -name "*.conf" -exec dos2unix {} \; 2>/dev/null || true
find $WORK_DIR -name "*.yaml" -exec dos2unix {} \; 2>/dev/null || true

# ============================================================
# 8. 安装 systemd 服务
# ============================================================
log_info "安装 systemd 服务..."

cp -f $PROJECT_DIR/systemd/mavlink-router.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/go2rtc.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/feeder-control.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/sensor-monitor.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/boat-identity.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/ffmpeg-push.service /etc/systemd/system/

systemctl daemon-reload

# 启用开机自启（默认启用，可根据需要禁用）
systemctl enable mavlink-router.service
systemctl enable go2rtc.service
systemctl enable feeder-control.service
systemctl enable sensor-monitor.service
systemctl enable boat-identity.service
systemctl enable ffmpeg-push.service

log_info "systemd 服务已安装并启用"

# ============================================================
# 9. 日志目录
# ============================================================
mkdir -p $WORK_DIR/logs
chmod 755 $WORK_DIR/logs

# ============================================================
# 完成
# ============================================================
echo ""
echo "============================================================"
echo -e "${GREEN}  系统初始化完成!${NC}"
echo "============================================================"
echo ""
echo "  工作目录: $WORK_DIR"
echo "  Python环境: $WORK_DIR/venv"
echo ""
echo "  已安装服务:"
echo "    - mavlink-router  (飞控MAVLink转发)"
echo "    - boat-identity   (ICCID身份识别上报)"
echo "    - go2rtc          (USB摄像头本地WebRTC/RTSP)"
echo "    - ffmpeg-push     (视频推流到云端MediaMTX)"
echo "    - feeder-control  (投料电机控制)"
echo "    - sensor-monitor  (传感器监控与MAVLink上报)"
echo ""
echo "  下一步:"
echo "    1. 编辑 $WORK_DIR/config/mavlink-router.conf 修改云服务器地址"
echo "    2. 编辑 $WORK_DIR/scripts/ffmpeg_push.sh 修改云端MediaMTX地址"
echo "    3. 编辑 $WORK_DIR/config/feeder_config.yaml 修改GPIO引脚和投料参数"
echo "    4. 编辑 $WORK_DIR/config/sensor_config.yaml 修改料斗尺寸和GPIO"
echo "    5. 确认串口设备名: ls /dev/ttyS* (通常是 /dev/ttyS1)"
echo "    6. 确认摄像头设备: ls /dev/video* (通常是 /dev/video0)"
echo "    7. 重启系统: sudo reboot"
echo "    8. 查看服务状态: systemctl status <服务名>"
echo ""
echo "  注意: 首次运行前请确保飞控已通过TELEM2连接到香橙派UART"
echo "        TX(飞控)->RX(香橙派), RX(飞控)->TX(香橙派), GND共地"
echo "============================================================"
