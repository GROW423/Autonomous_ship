#!/bin/bash
set -e
WORK_DIR=/opt/usv
PROJECT_DIR=/tmp/onboard

echo '[INFO] 创建工作目录...'
mkdir -p $WORK_DIR/{config,logs,scripts,services}

echo '[INFO] 创建Python虚拟环境...'
python3 -m venv $WORK_DIR/venv
source $WORK_DIR/venv/bin/activate
pip install --upgrade pip setuptools wheel 2>&1 | tail -2

echo '[INFO] 安装Python依赖...'
pip install pymavlink pyserial python-periphery gpiod pyyaml requests websocket-client 2>&1 | tail -3
deactivate

echo '[INFO] 编译安装mavlink-router...'
cd /tmp
rm -rf mavlink-router
git clone https://github.com/mavlink-router/mavlink-router.git 2>&1 | tail -2
cd mavlink-router
git submodule update --init --recursive 2>&1 | tail -2
meson setup build 2>&1 | tail -2
ninja -C build 2>&1 | tail -3
install -m 0755 build/src/mavlink-routerd /usr/local/bin/mavlink-routerd
echo '[INFO] mavlink-router安装完成'

echo '[INFO] 安装go2rtc...'
cd /tmp
wget -q https://github.com/AlexxIT/go2rtc/releases/download/v1.9.8/go2rtc_linux_arm64.tar.gz -O go2rtc.tar.gz
tar -xzf go2rtc.tar.gz
install -m 0755 go2rtc /usr/local/bin/go2rtc
echo '[INFO] go2rtc安装完成'

echo '[INFO] 部署项目文件...'
cp -f $PROJECT_DIR/config/mavlink-router.conf $WORK_DIR/config/
cp -f $PROJECT_DIR/config/go2rtc.yaml $WORK_DIR/config/
cp -f $PROJECT_DIR/config/feeder_config.yaml $WORK_DIR/config/
cp -f $PROJECT_DIR/config/sensor_config.yaml $WORK_DIR/config/
cp -f $PROJECT_DIR/services/feeder_control.py $WORK_DIR/services/
cp -f $PROJECT_DIR/services/sensor_monitor.py $WORK_DIR/services/
cp -f $PROJECT_DIR/services/boat_identity.py $WORK_DIR/services/
cp -f $PROJECT_DIR/scripts/*.sh $WORK_DIR/scripts/ 2>/dev/null || true
chmod +x $WORK_DIR/scripts/*.sh 2>/dev/null || true
chmod +x $WORK_DIR/services/*.py
find $WORK_DIR -name '*.sh' -exec sed -i 's/\r$//' {} \; 2>/dev/null || true
find $WORK_DIR -name '*.py' -exec sed -i 's/\r$//' {} \; 2>/dev/null || true

echo '[INFO] 安装systemd服务...'
cp -f $PROJECT_DIR/systemd/mavlink-router.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/go2rtc.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/feeder-control.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/sensor-monitor.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/boat-identity.service /etc/systemd/system/
cp -f $PROJECT_DIR/systemd/ffmpeg-push.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable mavlink-router.service go2rtc.service feeder-control.service sensor-monitor.service boat-identity.service ffmpeg-push.service 2>&1 | tail -2

echo ''
echo '========================================'
echo '  部署完成!'
echo '  工作目录: /opt/usv'
echo '  mavlink-router: /usr/local/bin/mavlink-routerd'
echo '  go2rtc: /usr/local/bin/go2rtc'
echo '========================================'
