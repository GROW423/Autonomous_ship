# 无人船远程控制系统 - 使用说明

## 目录

1. [系统概述](#1-系统概述)
2. [硬件准备](#2-硬件准备)
3. [部署指南](#3-部署指南)
4. [用户操作指南](#4-用户操作指南)
5. [常见问题](#5-常见问题)

---

## 1. 系统概述

本系统是一套基于 **ArduPilot + 云平台 + Web前端** 的无人船远程投喂控制系统，实现以下功能：

- **自动航行**：无人船从停泊点自动出发，沿预设GPS航路点航行，完成后自动返航
- **自动投喂**：航行途中根据船速自动调节投料量，保证单位面积投料均匀
- **自动避障**：通过激光雷达检测障碍物，自动停车或绕行
- **远程监控**：通过4G网络实时上传船的位置、电量、工作状态、饲料余量、部件状态
- **远程遥控**：用户通过Web界面遥控船（开始航行/返航/紧急停车/投料开关）
- **路径规划**：在地图上可视化编辑航路点，一键上传到船
- **实时视频**：通过船载摄像头查看实时画面
- **历史回放**：查看历史航行轨迹和状态数据

### 系统架构

```
┌─────────────┐     4G      ┌──────────────────┐   HTTPS/WSS   ┌──────────┐
│  船载端      │◄───────────►│   云平台          │◄────────────►│  Web前端  │
│  (香橙派)    │  MAVLink/RTSP│  (Docker Compose)│   REST/WS    │ (浏览器)  │
└─────────────┘              └──────────────────┘              └──────────┘
```

---

## 2. 硬件准备

### 2.1 硬件清单

| 部件 | 型号 | 数量 | 说明 |
|------|------|------|------|
| 飞控 | Holybro Pixhawk4 | 1 | 运行ArduPilot Rover固件 |
| GPS | Ublox M10N | 1 | 接飞控GPS1 |
| 伴飞计算机 | OrangePi Zero2W 2GB | 1 | 全志H618，跑Linux |
| 4G模块 | 移远EC200S-CN USB Dongle | 1 | 全网通，插SIM卡 |
| USB Hub | 4口USB 2.0 Hub（带供电） | 1 | 扩展USB口 |
| 摄像头 | USB 1080p摄像头（配防水壳） | 1 | 接USB Hub |
| 避障雷达 | 北醒TF02-i 激光雷达 | 1 | I2C接口，接飞控I2C |
| 投料电机驱动 | BTS7960 大电流电机驱动 | 1 | 接香橙派GPIO |
| 投料电机 | 12V直流减速电机+螺旋输送杆 | 1 | 料斗底部 |
| 料位传感器 | JSN-SR04T 防水超声波 | 1 | 料斗顶部 |
| 电池 | 12V 100Ah 磷酸铁锂（带BMS） | 1 | 主电源 |
| 推进电调 | 双通道有刷/无刷电调 | 1 | 接飞控MAIN OUT |
| 推进电机 | 根据船型选择 | 2 | 左右推进 |

### 2.2 接线图

#### Pixhawk4 ↔ OrangePi Zero2W（MAVLink遥测）

```
Pixhawk TELEM2          OrangePi Zero2W (26pin GPIO)
─────────────            ─────────────────────────────
TX  (飞控发)  ─────────►  GPIO10 / RX  (pin 10)
RX  (飞控收)  ◄─────────  GPIO8  / TX  (pin 8)
GND           ──────────  GND          (pin 6)
```
> 注意：不要接VCC，两边都是3.3V TTL可直连。

#### 投料电机控制（BTS7960）

```
OrangePi GPIO          BTS7960
─────────────          ───────
GPIO12 (PWM)  ───────►  PWM
GPIO16 (EN)   ───────►  R_EN + L_EN (短接)
GPIO18 (DIR)  ───────►  R_PWM (方向，固定正转)
GND           ───────►  GND
                       M1 ────── 投料电机+
                       M2 ────── 投料电机-
                       VCC ───── 12V电池+
                       GND ───── 12V电池-
```

#### 料位传感器（JSN-SR04T）

```
OrangePi GPIO          JSN-SR04T
─────────────          ─────────
5V (pin 2/4)   ─────►  VCC
GPIO20 (pin 38) ─────►  Trig
GPIO21 (pin 40) ─────►  Echo
GND (pin 39)   ─────►  GND
```

#### Pixhawk4 其他接口

```
GPS1         ──► Ublox M10N GPS
I2C          ──► TF02-i 激光雷达 (避障)
MAIN OUT1    ──► 左推进电调
MAIN OUT2    ──► 右推进电调
POWER        ──► 电源模块 (12V电池电压电流监测)
TELEM2       ──► 香橙派UART (MAVLink)
```

---

## 3. 部署指南

### 3.1 船载端部署

#### 准备工作

1. 为OrangePi Zero2W刷入Debian 12或Ubuntu 22.04系统
2. 通过SSH登录香橙派
3. 确认硬件接线正确

#### 部署步骤

```bash
# 1. 将 onboard/ 目录传到香橙派
# (在你的电脑上执行)
scp -r onboard/ orangepi@<香橙派IP>:/tmp/

# 2. SSH登录香橙派
ssh orangepi@<香橙派IP>

# 3. 运行一键初始化脚本
cd /tmp/onboard/scripts
sudo bash system_setup.sh

# 4. 修改配置文件
# 修改云服务器地址
sudo nano /opt/usv/config/mavlink-router.conf
# 找到 [TcpEndpoint cloud] 下的 Address= 改为你的云服务器IP

# 修改视频推流地址
sudo nano /opt/usv/scripts/ffmpeg_push.sh
# 修改 CLOUD_RTSP= 为 rtsp://你的云服务器IP:8554/usv/camera1

# 修改投料参数 (GPIO引脚、基础投料量等)
sudo nano /opt/usv/config/feeder_config.yaml

# 修改传感器参数 (料斗尺寸、GPIO引脚)
sudo nano /opt/usv/config/sensor_config.yaml

# 5. 确认硬件设备
ls /dev/ttyS*      # 确认串口 (通常是 /dev/ttyS1)
ls /dev/video*     # 确认摄像头 (通常是 /dev/video0)
ls /dev/ttyUSB*    # 确认4G模块 (通常是 /dev/ttyUSB0-2)

# 6. 重启
sudo reboot

# 7. 重启后检查服务状态
systemctl status mavlink-router go2rtc ffmpeg-push feeder-control sensor-monitor
```

#### 飞控配置（Mission Planner/QGC）

1. 连接飞控，刷入ArduPilot Rover最新固件
2. 配置框架类型（差速转向/阿克曼等）
3. 配置遥控器校准、电调校准
4. 配置避障参数：
   ```
   RNGFND1_TYPE = 21        # TF02 I2C
   RNGFND1_ADDR = 16        # I2C地址
   RNGFND1_TRIGGR_CM = 300  # 触发距离3m
   PRX1_TYPE = 4            # 用作接近传感器
   AVOID_ENABLE = 7          # 启用所有避障源
   OA_TYPE = 1               # BendyRuler绕障
   ```
5. 配置遥测端口：
   ```
   SERIAL2_PROTOCOL = 2      # TELEM2 = MAVLink 2
   SERIAL2_BAUD = 921        # 921600波特率
   ```
6. 配置投料舵机（如果用飞控控制投料）：
   ```
   SERVO9_FUNCTION = 0       # 通道9通用GPIO
   ```

### 3.2 云平台部署

#### 方式一：一键部署脚本（推荐）

```bash
# 1. 购买云服务器 (Ubuntu 22.04, 2核4G以上)
# 2. 在云控制台安全组开放端口:
#    TCP: 22, 8000, 5760, 8554, 8889, 8888
#    UDP: 40000-65535 (WebRTC)

# 3. 上传cloud目录到服务器
scp -r cloud/ root@你的服务器IP:/tmp/usv-cloud/

# 4. SSH登录服务器
ssh root@你的服务器IP

# 5. 运行一键部署脚本
sudo bash /tmp/usv-cloud/deploy.sh
# 脚本会自动安装Docker、配置环境、启动所有服务
# 按提示输入服务器IP等参数
```

#### 方式二：手动部署

```bash
# 1. 安装Docker和Docker Compose
curl -fsSL https://get.docker.com | sh

# 2. 上传cloud目录到服务器，进入目录
cd /opt/usv-cloud

# 3. 配置环境变量
cp .env.example .env
nano .env
# 修改:
#   POSTGRES_PASSWORD=你的密码
#   SECRET_KEY=随机字符串
#   MEDIAMTX_PUBLIC_IP=你的服务器IP
#   MEDIAMTX_WEBRTC_URL=http://你的服务器IP:8889

# 4. 构建并启动
docker compose up -d --build

# 5. 验证
docker compose ps
curl http://localhost:8000/health
# 浏览器打开 http://你的服务器IP:8000/docs 查看API文档
```

#### 本地测试（Windows）

1. 安装Docker Desktop for Windows
2. 打开PowerShell：
   ```powershell
   cd G:\项目\无人船远程控制系统\cloud
   docker compose up -d
   ```
3. 浏览器打开 http://localhost:8000/docs 验证

### 3.3 前端部署

#### 开发模式

```bash
cd web
npm install

# 配置环境变量
cp .env.example .env
# 编辑 .env:
#   VITE_API_BASE_URL=http://你的云服务器IP:8000
#   VITE_WS_URL=ws://你的云服务器IP:8000/ws
#   VITE_VIDEO_URL=http://你的云服务器IP:8889
#   VITE_AMAP_KEY=你的高德地图API_KEY
#   VITE_AMAP_SECURITY_CODE=你的高德地图安全密钥

npm run dev
# 浏览器打开 http://localhost:5173
```

#### 生产部署（Nginx）

```bash
# 1. 构建
npm run build
# 产物在 dist/ 目录

# 2. 上传到服务器
scp -r dist/ user@服务器IP:/var/www/usv-web/

# 3. Nginx配置
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/usv-web/dist;
    index index.html;

    location / { try_files $uri $uri/ /index.html; }
    location /api/ { proxy_pass http://127.0.0.1:8000; }
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 4. 用户操作指南

### 4.1 注册与登录

1. 打开前端页面，点击"立即注册"
2. 填写用户名（至少3位）、密码（至少6位）、邮箱（可选）
3. 注册成功后自动登录
4. 后续登录输入用户名和密码即可

### 4.2 添加无人船

1. 登录后进入"我的船"页面
2. 点击"添加船"按钮
3. 填写：
   - **船名称**：如"投喂船01"
   - **MAVLink系统ID**：与船端 `mavlink-router.conf` 中的 `SystemId` 一致（默认1）
   - **4G ICCID**（可选）：SIM卡卡号
   - **描述**（可选）
4. 点击"添加"
5. 船端上电后，4G联网自动连接云平台，船卡片会显示"在线"

### 4.3 船控制台

点击船卡片进入控制台，页面分为三个区域：

#### 左侧 - 实时仪表盘

- **电池**：电量百分比、电压、电流
- **航行状态**：速度、航向、当前航点、是否解锁
- **位置**：经纬度、GPS定位类型、卫星数
- **饲料余量**：百分比进度条
- **通信**：4G信号强度、箱内温度
- **告警**：飞控上报的状态文本

#### 右侧 - 地图

- 显示船的实时位置（蓝色箭头，指向航向）
- 显示航行轨迹
- 路径编辑模式下可添加/拖动/删除航点

#### 底部 - 遥控操作栏

| 按钮 | 功能 |
|------|------|
| 开始航行 | 切换到AUTO模式，开始执行当前任务 |
| 返航 | 切换到RTL模式，自动返回停泊点 |
| 紧急停车 | 切换到HOLD模式，立即停车 |
| 开投料 | 手动开启投料电机 |
| 关投料 | 手动关闭投料电机 |
| 编辑路径 | 进入地图路径编辑模式 |

### 4.4 路径规划与上传

1. 在控制台点击"编辑路径"按钮
2. 地图进入编辑模式，左上角显示操作提示：
   - 点击地图添加航点
   - 拖动航点调整位置
   - 右键航点删除
3. 航点编号显示：
   - 绿色 = 起点（第一个航点）
   - 红色 = 终点（最后一个航点）
   - 蓝色 = 中间航点
4. 编辑完成后点击"保存并上传"
5. 系统自动创建任务并上传到船，提示"路径已上传（N个航点）"
6. 点击"开始航行"，船自动按新路径航行

> 也可以在控制台底部的"已保存任务"区域，点击之前保存的任务快速执行。

### 4.5 实时视频

1. 在控制台顶部点击"视频"按钮
2. 地图下方出现视频窗口
3. 点击视频区域开始播放（WebRTC低延迟）
4. 视频窗口支持刷新和关闭

> 视频延迟通常300ms-1s，取决于4G信号质量。

### 4.6 历史轨迹回放

1. 在控制台顶部点击"历史"按钮
2. 进入历史回放页面
3. 选择时间范围（1小时/6小时/24小时/3天/7天）
4. 地图显示该时间段的航行轨迹（绿色线）
5. 右侧面板显示当前时间点的状态数据
6. 底部时间轴：
   - 拖动滑块查看任意时间点
   - 播放/暂停按钮自动回放
   - 跳转到起点/终点按钮

---

## 5. 常见问题

### 5.1 船端显示离线

**可能原因：**
1. 4G模块未联网或SIM卡欠费
2. 云服务器地址配置错误
3. 云服务器安全组未开放5760端口
4. 香橙派mavlink-router服务未启动
5. 飞控TELEM2接线错误

**排查步骤：**
```bash
# SSH登录香橙派
# 1. 检查4G是否联网
ping -c 3 baidu.com

# 2. 检查mavlink-router服务
systemctl status mavlink-router
journalctl -u mavlink-router -f

# 3. 检查配置文件中的云服务器地址
cat /opt/usv/config/mavlink-router.conf | grep Address

# 4. 检查飞控串口接线和波特率
ls /dev/ttyS*
```

### 5.2 视频黑屏或无法播放

**可能原因：**
1. 船端ffmpeg-push服务未运行
2. USB摄像头未识别
3. MediaMTX WebRTC ICE候选地址错误
4. 云服务器安全组未开放UDP端口

**排查步骤：**
```bash
# 船端:
ls /dev/video*                    # 确认摄像头
systemctl status ffmpeg-push      # 确认推流服务
journalctl -u ffmpeg-push -f      # 查看推流日志

# 云服务器:
docker compose logs mediamtx       # 查看MediaMTX日志
# 检查 .env 中 MEDIAMTX_PUBLIC_IP 是否为服务器公网IP
# 检查安全组是否开放UDP 40000-65535
```

### 5.3 投料电机不转

**可能原因：**
1. 投料控制服务未启动
2. BTS7960接线错误或电源未接
3. 飞控未在AUTO模式（投料控制只在AUTO/GUIDED模式自动开启）
4. 船速低于0.2m/s（低于阈值不投料）
5. GPIO引脚配置与实际接线不符

**排查步骤：**
```bash
# 船端:
systemctl status feeder-control
journalctl -u feeder-control -f
# 查看日志中是否有 "启动投料电机" 或 "停止投料: xxx"

# 手动测试GPIO输出
gpioset gpiochip0 16=1   # 使能
gpioset gpiochip0 12=1   # PWM高 (测试用)

# 检查配置文件中的GPIO引脚
cat /opt/usv/config/feeder_config.yaml | grep -A5 gpio
```

### 5.4 前端地图不显示

**可能原因：**
1. 高德地图API Key未配置或错误
2. 高德控制台未绑定当前域名
3. 安全密钥配置错误

**解决：**
1. 编辑 `web/.env`，确认 `VITE_AMAP_KEY` 和 `VITE_AMAP_SECURITY_CODE` 正确
2. 登录[高德开放平台](https://lbs.amap.com/)，在应用管理中确认：
   - Key类型为"Web端(JS API)"
   - 已绑定当前访问域名（localhost和生产域名都要加）
3. 重启前端开发服务器

### 5.5 登录后看不到船

**可能原因：**
1. 未添加船（新用户需要先添加）
2. 船的MAVLink系统ID与船端不一致
3. 船端未上线

**解决：**
1. 在"我的船"页面点击"添加船"
2. 确认MAVLink系统ID与船端 `/opt/usv/config/mavlink-router.conf` 中的 `SystemId` 一致
3. 船端上电，等待4G联网，船卡片会自动变为"在线"

### 5.6 上传路径失败

**可能原因：**
1. 船不在线
2. 航点数量为0
3. MAVLink网关与船端通信异常

**解决：**
1. 确认船卡片显示"在线"
2. 确认地图上至少添加了1个航点
3. 检查云平台MAVLink网关日志：
   ```bash
   docker compose logs mavlink-gateway
   ```

### 5.7 Docker服务启动失败

**排查步骤：**
```bash
# 查看所有服务状态
docker compose ps

# 查看失败服务的日志
docker compose logs <服务名>

# 常见问题:
# 1. 端口被占用: 检查 .env 中的端口配置
# 2. 数据库连接失败: 检查 POSTGRES_PASSWORD 是否一致
# 3. 构建失败: 重新构建 docker compose build --no-cache

# 完全重置(会丢失数据):
docker compose down -v
docker compose up -d --build
```

---

## 附录：服务端口一览

| 服务 | 端口 | 协议 | 用途 |
|------|------|------|------|
| SSH | 22 | TCP | 服务器远程登录 |
| API | 8000 | TCP | REST API + WebSocket |
| MAVLink网关 | 5760 | TCP | 船端MAVLink连接 |
| MediaMTX RTSP | 8554 | TCP | 船端视频推流 |
| MediaMTX WebRTC | 8889 | TCP/UDP | 前端视频拉流 |
| MediaMTX HLS | 8888 | TCP | 前端HLS视频(备选) |
| MediaMTX API | 9997 | TCP | MediaMTX管理API |
| PostgreSQL | 5432 | TCP | 数据库(仅内网) |
| Redis | 6379 | TCP | 缓存(仅内网) |
