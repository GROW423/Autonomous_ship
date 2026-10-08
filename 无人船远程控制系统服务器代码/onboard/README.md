# 无人船船载端软件系统

基于 **ArduPilot Rover + OrangePi Zero2W** 的无人船远程投喂控制系统船载端。

## 硬件清单

| 部件 | 型号 | 数量 |
|------|------|------|
| 飞控 | Holybro Pixhawk4 (FMUv5) | 1 |
| GPS | Ublox M10N | 1 |
| 伴飞计算机 | OrangePi Zero2W 2GB (全志H618) | 1 |
| 4G模块 | 移远 EC200S-CN USB Dongle | 1 |
| USB Hub | 4口 USB 2.0 Hub (带供电) | 1 |
| 摄像头 | USB 1080p摄像头 (配防水壳) | 1 |
| 前向避障 | 北醒 TF02-i 激光雷达 (I2C) | 1 |
| 投料电机驱动 | BTS7960 大电流电机驱动 | 1 |
| 投料电机 | 12V直流减速电机 + 螺旋输送杆 | 1 |
| 料位传感器 | JSN-SR04T 防水超声波 | 1 |
| 电池 | 12V 100Ah 磷酸铁锂 (带BMS) | 1 |

## 硬件接线

### 1. Pixhawk4 <-> OrangePi Zero2W (MAVLink遥测)

```
Pixhawk TELEM2          OrangePi Zero2W (26pin GPIO)
─────────────            ─────────────────────────────
TX  (飞控发)  ─────────►  GPIO10 / RX  (pin 10)
RX  (飞控收)  ◄─────────  GPIO8  / TX  (pin 8)
GND           ──────────  GND          (pin 6)
(不要接VCC, 两边都是3.3V TTL可直连)
```

### 2. 投料电机控制 (BTS7960)

```
OrangePi GPIO          BTS7960
─────────────          ───────
GPIO12 (PWM)  ───────►  PWM
GPIO16 (EN)   ───────►  R_EN + L_EN (短接)
GPIO18 (DIR)  ───────►  R_PWM (方向, 固定正转)
GND           ───────►  GND
                       M1 ────── 投料电机+
                       M2 ────── 投料电机-
                       VCC ───── 12V电池+
                       GND ───── 12V电池-
```

### 3. 料位传感器 (JSN-SR04T)

```
OrangePi GPIO          JSN-SR04T
─────────────          ─────────
5V (pin 2/4)   ─────►  VCC
GPIO20 (pin 38) ─────►  Trig
GPIO21 (pin 40) ─────►  Echo
GND (pin 39)   ─────►  GND
```

### 4. USB设备 (通过USB Hub)

```
OrangePi USB2.0 ──► USB Hub ──┬── 4G模块 (EC200S)
                                ├── USB摄像头
                                └── (预留) RPLidar / 其他
```

### 5. Pixhawk4 其他接口

```
GPS1     ──► Ublox M10N GPS
I2C      ──► TF02-i 激光雷达 (避障)
MAIN OUT1 ──► 左推进电调
MAIN OUT2 ──► 右推进电调
POWER    ──► 电源模块 (12V电池电压电流监测)
```

## 系统要求

- OrangePi Zero2W 运行 **Debian 12 (bookworm)** 或 **Ubuntu 22.04** ARM64
- 已启用UART1 overlay
- root或sudo权限
- 4G模块已识别 (lsusb可见)

## 快速部署

### 1. 将项目文件传输到香橙派

```bash
# 在你的电脑上, 将 onboard 目录传到香橙派
scp -r onboard/ orangepi@<香橙派IP>:/tmp/
```

### 2. SSH登录香橙派, 运行初始化脚本

```bash
ssh orangepi@<香橙派IP>
cd /tmp/onboard/scripts
sudo bash system_setup.sh
```

脚本会自动完成:
- 系统更新和依赖安装
- UART串口配置
- 4G拨号配置
- Python虚拟环境和依赖
- mavlink-router 编译安装
- go2rtc 安装
- 项目文件部署到 `/opt/usv/`
- systemd服务安装和启用

### 3. 修改配置文件

```bash
# 修改云服务器地址 (MAVLink网关)
sudo nano /opt/usv/config/mavlink-router.conf
# 找到 [TcpEndpoint cloud] 下的 Address= 改为你的云服务器IP/域名

# 修改视频推流地址 (云端MediaMTX)
sudo nano /opt/usv/scripts/ffmpeg_push.sh
# 修改 CLOUD_RTSP= 为你的云服务器RTSP地址

# 修改投料参数 (GPIO引脚、基础投料量、目标速度等)
sudo nano /opt/usv/config/feeder_config.yaml

# 修改传感器参数 (料斗尺寸、GPIO引脚)
sudo nano /opt/usv/config/sensor_config.yaml
```

### 4. 确认硬件设备

```bash
# 确认串口 (接飞控的UART)
ls /dev/ttyS*
# 通常是 /dev/ttyS1, 如果不是, 修改 mavlink-router.conf 中的 Device=

# 确认摄像头
ls /dev/video*
# 通常是 /dev/video0, 如果不是, 修改 go2rtc.yaml 中的 v4l2:///dev/video0

# 确认4G模块
ls /dev/ttyUSB*
# EC200S通常出现 /dev/ttyUSB0, /dev/ttyUSB1, /dev/ttyUSB2
# AT指令端口通常是 /dev/ttyUSB2, 如果不是, 修改 sensor_config.yaml 中的 at_port=
```

### 5. 重启并验证

```bash
sudo reboot

# 重启后查看所有服务状态
systemctl status mavlink-router go2rtc ffmpeg-push feeder-control sensor-monitor

# 查看某个服务的日志
journalctl -u mavlink-router -f
journalctl -u feeder-control -f
journalctl -u sensor-monitor -f
```

## 服务说明

| 服务 | 功能 | 端口 |
|------|------|------|
| mavlink-router | 飞控MAVLink数据转发到云端, 本地UDP调试 | UDP 14550 (本地) |
| go2rtc | USB摄像头采集, 本地WebRTC/RTSP输出 | 1984 (Web), 8554 (RTSP), 8555 (WebRTC) |
| ffmpeg-push | 从本地go2rtc拉流, 推送到云端MediaMTX | — |
| feeder-control | 监听飞控状态, 自动控制投料电机启停和速度 | — |
| sensor-monitor | 读取料位/4G信号/温度, 通过MAVLink上报 | — |

## 投料控制逻辑

### 自动投料条件 (全部满足才投料)

1. 飞控已解锁 (ARMED)
2. 飞行模式为 AUTO(10) 或 GUIDED(15)
3. 地速 > 0.2 m/s (避免原地堆积)
4. 当前航点序号 >= 1 (跳过出发段)

### 速度补偿算法

```
投料占空比 = 基础占空比 × (当前船速 / 目标船速)
```

- 船速越快 → 占空比越高 → 投料量越大
- 保证单位面积投料均匀
- 占空比限制在 min_duty ~ max_duty 之间

### 手动覆盖

通过MAVLink发送模式切换命令即可:
- 切到 MANUAL/RTL/HOLD → 自动停止投料
- 切回 AUTO → 自动恢复投料

## MAVLink自定义数据上报

sensor-monitor 通过 `NAMED_VALUE_FLOAT` 消息上报以下数据:

| 名称 | 含义 | 单位 |
|------|------|------|
| feed_lvl | 饲料余量 | 0-100% |
| feed_dist | 料位传感器原始距离 | cm |
| 4g_csq | 4G信号强度 | 0-31 (99=无信号) |
| box_temp | 箱内温度(CPU参考) | ℃ |

云平台MAVLink网关解析这些消息后存入数据库, 前端展示。

## 故障排查

### 飞控连不上

```bash
# 检查串口是否存在
ls /dev/ttyS*

# 检查uart1 overlay是否启用
cat /boot/orangepiEnv.txt | grep overlays

# 检查接线 (TX/RX是否接反)
# 用逻辑分析仪或USB转TTL看飞控TELEM2是否有数据输出

# 查看mavlink-router日志
journalctl -u mavlink-router -f
```

### 摄像头不工作

```bash
# 检查摄像头是否识别
ls /dev/video*
v4l2-ctl --device=/dev/video0 --list-formats-ext

# 测试本地预览
ffplay rtsp://127.0.0.1:8554/camera1

# 查看go2rtc日志
journalctl -u go2rtc -f
```

### 投料电机不转

```bash
# 检查GPIO权限 (服务以root运行, 应该没问题)
# 手动测试GPIO输出
gpioset gpiochip0 16=1   # 使能
gpioset gpiochip0 12=1   # PWM高 (测试用)

# 检查BTS7960接线和电源
# 检查feeder-control是否检测到AUTO模式
journalctl -u feeder-control -f
```

### 4G连不上

```bash
# 检查4G模块是否识别
lsusb
ls /dev/ttyUSB*

# 手动测试AT指令
sudo minicom -D /dev/ttyUSB2 -b 115200
# 输入 AT, 应返回 OK
# 输入 AT+CSQ, 应返回信号强度
# 输入 AT+CGDCONT? 查看APN

# 检查wvdial配置
sudo nano /etc/wvdial.conf
# APN根据运营商: 移动=cmnet, 联通=3gnet, 电信=ctnet
```

## 与云平台对接

船载端通过以下方式与云平台通信:

1. **MAVLink遥测**: mavlink-router 通过 TCP 主动连接云服务器 `5760` 端口
2. **视频流**: ffmpeg-push 通过 RTSP 推流到云服务器 `8554` 端口
3. **自定义数据**: sensor-monitor 的 NAMED_VALUE_FLOAT 随MAVLink链路一起上传

云平台需要部署:
- MAVLink网关 (监听TCP 5760, 解析MAVLink消息)
- MediaMTX (接收RTSP推流, 转WebRTC/HLS给前端)
- Web API + WebSocket + 数据库 + 前端

详见 `../cloud/` 和 `../web/` 目录 (后续开发)。

## 目录结构

```
onboard/
├── config/
│   ├── mavlink-router.conf    # MAVLink转发配置
│   ├── go2rtc.yaml            # 视频流配置
│   ├── feeder_config.yaml     # 投料控制配置
│   └── sensor_config.yaml     # 传感器监控配置
├── scripts/
│   ├── system_setup.sh        # 系统初始化一键脚本
│   └── ffmpeg_push.sh         # 视频推流脚本
├── services/
│   ├── feeder_control.py      # 投料控制程序
│   └── sensor_monitor.py      # 传感器监控程序
├── systemd/
│   ├── mavlink-router.service
│   ├── go2rtc.service
│   ├── ffmpeg-push.service
│   ├── feeder-control.service
│   └── sensor-monitor.service
└── README.md                   # 本文档
```
