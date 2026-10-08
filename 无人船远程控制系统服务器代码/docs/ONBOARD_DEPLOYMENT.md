# 无人船船载端部署与联调指南

> 适用硬件：Pixhawk 2.4.8 + Ublox M10 GPS + OrangePi Zero2W (全志H618, 2GB) + 移远EC200S 4G + USB摄像头
> 适用固件：ArduPilot Rover 4.5+ 稳定版
> 文档版本：v1.0 | 2026-08-21

---

## 目录

1. [硬件清单](#1-硬件清单)
2. [硬件接线指南](#2-硬件接线指南)
3. [Pixhawk飞控固件刷写与参数配置](#3-pixhawk飞控固件刷写与参数配置)
4. [香橙派系统准备](#4-香橙派系统准备)
5. [船载端软件部署](#5-船载端软件部署)
6. [配置文件修改](#6-配置文件修改)
7. [端到端联调测试清单](#7-端到端联调测试清单)
8. [故障排查指南](#8-故障排查指南)

---

## 1. 硬件清单

### 核心部件
| 序号 | 设备 | 型号 | 数量 | 说明 |
|------|------|------|------|------|
| 1 | 飞控 | Pixhawk 2.4.8 (ICM-20608版) | 1 | 运行ArduPilot Rover固件 |
| 2 | GPS | Ublox M10 (带外置磁力计) | 1 | 北斗/GPS/GLONASS多模定位 |
| 3 | 伴飞计算机 | OrangePi Zero2W 2GB | 1 | 全志H618, ARM64, 运行5个服务 |
| 4 | 4G模块 | 移远EC200S (Mini PCIe) + 转接板 | 1 | 4G Cat.1, 物联网卡 |
| 5 | 物联网卡 | 中国移动/电信 Cat.1物联网卡 | 1 | ICCID作为船唯一标识 |
| 6 | USB摄像头 | 普通USB摄像头 (支持MJPEG) | 1 | 720P/25fps即可 |
| 7 | USB Hub | 带供电的USB 2.0 Hub | 1 | 扩展USB口(4G+摄像头) |

### 投料与传感器
| 序号 | 设备 | 型号 | 数量 | 说明 |
|------|------|------|------|------|
| 8 | 电机驱动 | BTS7960 双路H桥 | 1 | 投料电机PWM驱动 |
| 9 | 投料电机 | 12V直流减速电机 | 1 | 根据料斗选型, 建议30-60rpm |
| 10 | 料位传感器 | JSN-SR04T 防水超声波 | 1 | 料斗顶部向下测距 |
| 11 | 激光雷达 | 北醒TF02-i (可选) | 1 | 避障, 量程40m |

### 电源与配件
| 序号 | 设备 | 规格 | 数量 | 说明 |
|------|------|------|------|------|
| 12 | 主电池 | 12V锂电池 (建议20Ah以上) | 1 | 推进+投料+飞控+香橙派供电 |
| 13 | BEC降压模块 | 12V→5V 5A | 1 | 飞控和香橙派5V供电 |
| 14 | 电压电流传感器 | 3DR电源模块 (可选) | 1 | 电池电压电流监控 |
| 15 | 杜邦线 | 母对母/公对母 20cm | 若干 | 接线用 |
| 16 | 防水接线盒 | IP67以上 | 1-2 | 电子设备防水 |

---

## 2. 硬件接线指南

### 2.1 整体接线框图

```
┌─────────────────────────────────────────────────────────────────┐
│                        12V锂电池                                  │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │              │              │              │              │ │
│  ▼              ▼              ▼              ▼              ▼ │
│ 推进电机     BTS7960       投料电机      12V→5V BEC     电压电流传感器│
│ (电调)       (投料驱动)     (12V直流)     (5V 5A)        (飞控POWER)│
│                              │              │              │
│                              │              ▼              ▼
│                              │         ┌─────────┐   ┌───────────┐
│                              │         │ OrangePi│   │ Pixhawk   │
│                              │         │ Zero2W  │   │ 2.4.8     │
│                              │         │         │   │           │
│                              │         │ USB Hub │   │ TELEM2────┼─── 串口交叉连接
│                              │         │  ┌──┐   │   │           │
│                              │         │  │4G│   │   │ GPS1──────┼─── M10 GPS
│                              │         │  │EC│   │   │           │
│                              │         │  │20│   │   │ AUX1──────┼─── BTS7960 PWM
│                              │         │  │0S│   │   │ AUX2──────┼─── BTS7960 EN
│                              │         │  └──┘   │   │           │
│                              │         │ 摄像头  │   │ I2C────────┼─── JSN-SR04T料位
│                              │         └─────────┘   │ (可选)SER4──┼─── TF02-i雷达
│                              │                         └───────────┘
│                              ▼
│                         BTS7960 OUT
│                         (投料电机正反转)
```

### 2.2 Pixhawk 2.4.8 接口定义

Pixhawk 2.4.8 主要接口（从左到右，从上到下）：

| 接口 | 引脚定义 | 用途 |
|------|---------|------|
| **POWER** | 5V/GND/VCC | 电源模块输入（电压电流传感器） |
| **USB** | Micro USB | 固件刷写/参数配置/调试 |
| **TELEM1** | TX/RX/GND/5V | 数传电台（本项目不用） |
| **TELEM2** | TX/RX/GND/5V | **接香橙派UART（MAVLink通信）** |
| **GPS1** | TX/RX/GND/5V/SDA/SCL | **接M10 GPS** |
| **GPS2** | TX/RX/GND/5V | 双GPS冗余（可选） |
| **I2C** | SDA/SCL/GND/5V | **接JSN-SR04T料位传感器** |
| **CAN** | CAN_H/CAN_L/GND/5V | CAN设备（本项目不用） |
| **ADC** | 3.3V/ADC/GND | 模拟电压采集（可选） |
| **MAIN OUT** | 1-8路PWM | 主输出（推进电机电调） |
| **AUX OUT** | 1-6路PWM | 辅助输出（**投料电机控制**） |

### 2.3 关键接线详细说明

#### 接线1：Pixhawk TELEM2 ↔ 香橙派 UART（最重要！）

> ⚠️ **TX/RX必须交叉连接！** 飞控的TX接香橙派的RX，飞控的RX接香橙派的TX。

| Pixhawk TELEM2 | 线色（建议） | OrangePi Zero2W GPIO | 引脚功能 |
|----------------|-------------|----------------------|---------|
| TX (飞控发) | 绿 | GPIO10 (RX) / Physical pin 19 | 香橙派接收 |
| RX (飞控收) | 白 | GPIO8 (TX) / Physical pin 24 | 香橙派发送 |
| GND | 黑 | GND / Physical pin 6/9/14/20/25 | 共地（必须接！） |
| 5V | 红 | **不接** | 飞控5V输出，香橙派用独立供电 |

> 📌 **注意事项：**
> - 两边都是3.3V TTL电平，可以直连，不需要电平转换
> - **绝对不要接VCC/5V**，否则可能烧毁香橙派
> - GND必须共地，否则串口数据会乱码或完全无法通信
> - 香橙派启用uart1 overlay后，串口设备名为 `/dev/ttyS1`

#### 接线2：M10 GPS ↔ Pixhawk GPS1

| M10 GPS模块 | Pixhawk GPS1 | 说明 |
|-------------|-------------|------|
| VCC (5V) | 5V | 飞控供电 |
| GND | GND | 共地 |
| TX (模块发) | RX | 交叉连接 |
| RX (模块收) | TX | 交叉连接 |
| SDA | SDA | I2C磁力计（如果模块带） |
| SCL | SCL | I2C磁力计 |

> 📌 M10 GPS安装位置：尽量安装在船的高处，远离电机和电调，天线朝上，周围无金属遮挡。

#### 接线3：投料电机控制（Pixhawk AUX OUT ↔ BTS7960）

| Pixhawk AUX OUT | BTS7960 | 说明 |
|-----------------|---------|------|
| AUX1 (信号) | PWM / EN1 | 投料电机PWM调速 |
| AUX2 (信号) | EN2 / R_PWM | 使能/方向控制 |
| **GND** | GND | 共地（必须接！） |

| BTS7960 | 投料电机 | 电源 |
|---------|---------|------|
| M+ | 电机正极 | - |
| M- | 电机负极 | - |
| V+ | - | 12V电池正极 |
| GND | - | 12V电池负极 |

> 📌 **BTS7960接线说明：**
> - BTS7960是双路H桥，可以控制电机正反转
> - 投料电机通常只需要正转，所以EN2可以接高电平或悬空
> - PWM信号来自飞控AUX1，飞控输出3.3V PWM，BTS7960可以直接识别
> - BTS7960的GND必须和飞控GND共地，否则PWM信号无效

#### 接线4：JSN-SR04T料位传感器 ↔ 香橙派 GPIO

> ⚠️ JSN-SR04T是5V供电，Trig是3.3V/5V兼容，但Echo输出是5V！香橙派GPIO是3.3V，**Echo必须接分压电阻或电平转换**，否则可能烧毁GPIO。

| JSN-SR04T | 线色 | OrangePi Zero2W | 说明 |
|-----------|------|-----------------|------|
| VCC | 红 | 5V / Physical pin 2/4 | 5V供电 |
| GND | 黑 | GND / Physical pin 6 | 共地 |
| Trig | 黄 | GPIO20 / Physical pin 38 | 触发信号（香橙派发3.3V） |
| Echo | 蓝 | GPIO21 / Physical pin 40 | **需分压！5V→3.3V** |

> 📌 **Echo分压电路（必须）：**
> ```
> Echo (5V) ──[1kΩ]──┬── GPIO21 (3.3V)
>                      │
>                     [2kΩ]
>                      │
>                     GND
> ```
> 分压比：3.3/(1+2) = 1.1，5V × (2/(1+2)) = 3.33V ✓

> 📌 **安装位置：** 传感器安装在料斗顶部，探头向下，垂直对准料面。满料时距离约5cm，空料时距离约50cm（根据实际料斗尺寸调整配置）。

#### 接线5：移远EC200S 4G模块 ↔ 香橙派 USB

| EC200S转接板 | 香橙派 | 说明 |
|-------------|--------|------|
| USB (数据) | USB Hub → 香橙派USB | 数据通信 |
| VCC (5V) | USB Hub 5V或独立5V供电 | 4G模块峰值电流可达2A，建议独立供电 |
| GND | GND | 共地 |
| SIM卡 | 物联网卡插入模块SIM卡槽 | 注意卡的方向 |

> 📌 **4G模块注意事项：**
> - EC200S通过USB连接后，通常会枚举为3个串口：/dev/ttyUSB0 (AT), /dev/ttyUSB1 (PPP), /dev/ttyUSB2 (AT诊断)
> - AT命令端口通常是 /dev/ttyUSB2（不同固件可能不同，用 `ls /dev/ttyUSB*` 确认）
> - 4G天线必须接，否则信号极差或无法注册网络
> - 物联网卡需要激活，并确认APN配置正确（移动=cmnet，联通=3gnet，电信=ctnet）

#### 接线6：USB摄像头 ↔ 香橙派 USB

| USB摄像头 | 香橙派 | 说明 |
|----------|--------|------|
| USB | USB Hub → 香橙派USB | 视频数据 |
| - | - | 摄像头通常由USB供电 |

> 📌 摄像头设备名通常是 `/dev/video0`，用 `ls /dev/video*` 确认。

#### 接线7：TF02-i激光雷达（可选，避障用）

| TF02-i | Pixhawk | 说明 |
|--------|---------|------|
| VCC (5V) | 5V | 供电 |
| GND | GND | 共地 |
| TX (模块发) | SERIAL4 RX | 交叉连接 |
| RX (模块收) | SERIAL4 TX | 交叉连接 |

> 📌 TF02-i安装在船头，朝前安装，用于前方避障。在ArduPilot中配置为Proximity传感器。

### 2.4 供电系统设计

```
12V锂电池 (主电源)
├── 推进电机电调 (直接12V)
├── BTS7960投料驱动 (直接12V)
├── 12V→5V BEC 5A
│   ├── Pixhawk飞控 (5V)
│   ├── OrangePi香橙派 (5V, 建议3A以上)
│   ├── USB Hub (5V)
│   │   ├── 4G模块 (5V, 峰值2A)
│   │   └── USB摄像头 (5V)
│   ├── M10 GPS (5V, 由飞控供电)
│   └── JSN-SR04T (5V, 由香橙派或BEC供电)
└── 电压电流传感器 (飞控POWER口)
```

> ⚠️ **重要：**
> - 香橙派和4G模块峰值电流较大，BEC建议5A以上
> - 4G模块发射时峰值电流可达2A，建议4G模块用独立5V供电，不要和香橙派共用一个BEC
> - 所有设备必须共地
> - 电池建议加保险丝（15-20A），防止短路

---

## 3. Pixhawk飞控固件刷写与参数配置

### 3.1 刷写ArduPilot Rover固件

**工具：** Mission Planner (Windows) 或 QGroundControl (跨平台)

**步骤：**

1. **下载Mission Planner**：https://firmware.ardupilot.org/Tools/MissionPlanner/
2. **用USB线连接Pixhawk到电脑**
3. **打开Mission Planner → 初始设置 → 安装固件**
4. **选择"Rover"（无人车/船固件）**
5. **选择最新稳定版（4.5.x）**，点击刷写
6. **等待刷写完成**，不要断开USB
7. **刷写完成后**，飞控会自动重启

> 📌 也可以直接下载固件文件手动刷写：https://firmware.ardupilot.org/Rover/stable/Pixhawk1/

### 3.2 飞控基础参数配置

连接飞控后，在Mission Planner的**配置/调试 → 全部参数表**中搜索并修改以下参数：

#### 串口配置（TELEM2接香橙派）
| 参数 | 值 | 说明 |
|------|-----|------|
| `SERIAL2_PROTOCOL` | 1 (MAVLink2) | TELEM2使用MAVLink2协议 |
| `SERIAL2_BAUD` | 921 | TELEM2波特率921600（921=921600） |

#### GPS配置
| 参数 | 值 | 说明 |
|------|-----|------|
| `GPS_TYPE` | 1 (Auto) | 自动检测GPS类型（M10自动识别） |
| `GPS_AUTO_CONFIG` | 1 | 自动配置GPS |
| `COMPASS_USE` | 1 | 启用磁力计 |
| `COMPASS_USE2` | 0 | 禁用第二磁力计（如果只有一个） |

#### 航行模式配置
| 参数 | 值 | 说明 |
|------|-----|------|
| `MODE1` | 0 (Manual) | 模式1=手动 |
| `MODE2` | 3 (Steering) | 模式2=转向 |
| `MODE3` | 4 (Hold) | 模式3=保持 |
| `MODE4` | 10 (Auto) | 模式4=自动航行 |
| `MODE5` | 11 (RTL) | 模式5=返航 |
| `MODE6` | 15 (Guided) | 模式6=引导 |

> 📌 模式切换通过遥控器通道5或MAVLink指令实现。本项目主要通过MAVLink指令切换模式，不需要遥控器。

#### 返航配置
| 参数 | 值 | 说明 |
|------|-----|------|
| `RTL_ALT` | 0 | 返航高度（船不需要高度，设0） |
| `RTL_SPEED` | 150 | 返航速度1.5m/s (单位cm/s) |

#### 自动航行配置
| 参数 | 值 | 说明 |
|------|-----|------|
| `WP_SPEED` | 150 | 航点航行速度1.5m/s (cm/s) |
| `WP_RADIUS` | 200 | 到达航点半径2m (cm) |
| `NAVL1_PERIOD` | 8 | L1导航周期（影响转向灵敏度，船建议6-10） |
| `NAVL1_DAMPING` | 0.75 | L1阻尼系数 |

#### 投料相关配置（通过AUX输出控制）
| 参数 | 值 | 说明 |
|------|-----|------|
| `AUX1_FUNCTION` | 0 | AUX1=通用PWM输出（由脚本或MAVLink控制） |
| `AUX2_FUNCTION` | 0 | AUX2=通用PWM输出 |

> 📌 投料控制由香橙派的feeder_control服务通过MAVLink的DO_SET_SERVO指令直接控制AUX输出PWM，不需要飞控内置功能。

#### 避障配置（如果使用TF02-i激光雷达）
| 参数 | 值 | 说明 |
|------|-----|------|
| `SERIAL4_PROTOCOL` | 11 (Lidar360) | SERIAL4接激光雷达 |
| `SERIAL4_BAUD` | 115 | 波特率115200 |
| `PRX1_TYPE` | 7 (TF02) | 接近传感器类型=北醒TF02 |
| `PRX1_ORIENT` | 0 (前向) | 安装方向=朝前 |
| `PRX1_CM` | 300 | 检测距离3m (cm) |
| `AVOID_ENABLE` | 1 | 启用避障 |
| `AVOID_MARGIN` | 150 | 避障安全距离1.5m (cm) |

#### 电池监控配置（如果使用电压电流传感器）
| 参数 | 值 | 说明 |
|------|-----|------|
| `BATT_MONITOR` | 4 (电压电流) | 电池监控类型 |
| `BATT_VOLT_PIN` | 2 | 电压检测引脚（Pixhawk默认2） |
| `BATT_CURR_PIN` | 3 | 电流检测引脚（Pixhawk默认3） |
| `BATT_VOLT_MULT` | 10.1 | 电压分压比（根据电源模块调整） |
| `BATT_AMP_PERVLT` | 17 | 电流传感器系数（根据电源模块调整） |

### 3.3 飞控校准（必须完成！）

在Mission Planner的**初始设置 → 必要硬件**中依次完成：

1. **加速度计校准**：按提示将飞控放置在6个不同方向
2. **磁力计校准**：拿着飞控在空中画"8"字，旋转各个方向
   > ⚠️ 磁力计校准必须在船上实际安装位置进行，远离电机和金属
3. **遥控器校准**（如果使用遥控器）：本项目可跳过
4. **电机方向测试**：确认推进电机转向正确
5. **故障保护设置**：
   - 遥控信号丢失 → 保持当前模式或RTL
   - 电池低压 → RTL或Hold

### 3.4 设置停泊点（Home位置）

1. 将船放到停泊点
2. 等待GPS定位成功（至少8颗星，HDOP<2）
3. 在Mission Planner中点击**"设置Home位置"** → "当前位置"
4. 确认Home位置坐标正确

> 📌 Home位置是RTL返航的目标点，必须准确设置。也可以通过MAVLink指令动态设置。

---

## 4. 香橙派系统准备

### 4.1 系统镜像烧写

**推荐系统：** OrangePi Zero2W 官方 Debian Bookworm (Server版, ARM64)

**下载地址：** http://www.orangepi.cn/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-Zero-2W.html

**烧写工具：** balenaEtcher 或 Rufus

**烧写步骤：**
1. 下载镜像文件（.img或.xz）
2. 用balenaEtcher将镜像烧写到TF卡（建议32GB以上，Class10）
3. 烧写完成后，将TF卡插入香橙派
4. 插上网线和5V电源，启动

### 4.2 首次登录与基础配置

**默认登录：**
- 用户名：`root` 或 `orangepi`
- 密码：`orangepi`

**基础配置：**
```bash
# 登录后修改root密码
passwd

# 扩展文件系统到整张卡
orangepi-config  # 选择 System → Expand filesystem

# 设置时区
timedatectl set-timezone Asia/Shanghai

# 设置主机名（每艘船不同，建议用船名）
hostnamectl set-hostname usv-nansha-01

# 更新系统
apt update && apt upgrade -y
```

### 4.3 启用UART1串口（接Pixhawk TELEM2）

OrangePi Zero2W默认可能没有启用UART1，需要手动启用：

```bash
# 方法1：通过orangepi-config
orangepi-config
# 选择 System → Hardware → 勾选 uart1 → 保存 → 重启

# 方法2：手动修改配置文件
# 编辑 /boot/orangepiEnv.txt 或 /boot/armbianEnv.txt
# 在 overlays= 行添加 uart1
# 例如：overlays=uart1
nano /boot/orangepiEnv.txt

# 重启
reboot

# 重启后确认串口设备
ls /dev/ttyS*
# 应该能看到 /dev/ttyS1
```

> 📌 OrangePi Zero2W的UART1引脚：
> - GPIO8 (TX) = Physical pin 24
> - GPIO10 (RX) = Physical pin 19
> - GND = Physical pin 6/9/14/20/25

### 4.4 测试串口通信（验证飞控连接）

```bash
# 安装pymavlink测试
apt install -y python3-pip
pip install pymavlink

# 测试读取飞控MAVLink数据
python3 -c "
from pymavlink import mavutil
master = mavutil.mavlink_connection('/dev/ttyS1', baud=921600)
print('等待心跳包...')
master.wait_heartbeat()
print(f'飞控已连接! sys_id={master.target_system}, comp_id={master.target_component}')
print(f'飞行模式: {master.flightmode}')
"
```

如果看到"飞控已连接"，说明串口接线和飞控配置都正确。

### 4.5 4G模块配置

移远EC200S通过USB连接后，推荐用NetworkManager管理：

```bash
# 确认4G模块识别
ls /dev/ttyUSB*
# 应该看到 /dev/ttyUSB0, /dev/ttyUSB1, /dev/ttyUSB2

# 查看AT端口（通常是ttyUSB2）
apt install -y minicom
minicom -D /dev/ttyUSB2 -b 115200
# 输入 AT 应该返回 OK
# 输入 AT+QCCID 查看ICCID
# 输入 AT+CSQ 查看信号强度
# 按 Ctrl+A 然后 X 退出minicom

# 用NetworkManager配置4G拨号
nmcli device status
# 应该看到cdc-wdm0或类似的移动宽带设备

# 创建4G连接（APN根据运营商调整）
nmcli connection add type gsm ifname '*' con-name '4G' apn 'cmnet'
# 移动=cmnet, 联通=3gnet, 电信=ctnet

# 启用4G连接
nmcli connection up 4G

# 验证网络
ping -c 4 www.baidu.com
```

> 📌 如果NetworkManager无法识别4G模块，可以用wvdial拨号（部署脚本已配置），或参考移远官方Linux驱动文档。

### 4.6 读取ICCID（验证船身份识别）

```bash
# 通过AT命令读取ICCID
minicom -D /dev/ttyUSB2 -b 115200
# 输入 AT+QCCID
# 返回类似：+QCCID: 898604A1192070012345
# 这就是船的唯一标识，需要在云平台添加船时填写这个ICCID
```

---

## 5. 船载端软件部署

### 5.1 上传项目文件到香橙派

在你的电脑上，将 `onboard` 目录上传到香橙派：

```bash
# 方法1：scp上传（电脑上执行）
scp -r onboard/ root@<香橙派IP>:/tmp/

# 方法2：U盘拷贝
# 将onboard目录拷贝到U盘，插入香橙派，挂载后拷贝
```

### 5.2 运行一键部署脚本

```bash
# SSH登录香橙派
ssh root@<香橙派IP>

# 进入项目目录
cd /tmp/onboard

# 运行部署脚本（会自动安装所有依赖和服务）
bash scripts/system_setup.sh
```

脚本会自动完成：
1. 系统更新和基础依赖安装
2. UART1串口配置
3. 4G模块拨号配置
4. Python虚拟环境创建和依赖安装
5. mavlink-router编译安装
6. go2rtc下载安装
7. 项目文件部署到 /opt/usv
8. 6个systemd服务安装并启用开机自启

### 5.3 部署完成后验证

```bash
# 查看工作目录
ls -la /opt/usv/
# 应该看到 config/ logs/ scripts/ services/ venv/

# 查看Python服务
ls -la /opt/usv/services/
# 应该看到 boat_identity.py, feeder_control.py, sensor_monitor.py

# 查看配置文件
ls -la /opt/usv/config/
# 应该看到 mavlink-router.conf, go2rtc.yaml, feeder_config.yaml, sensor_config.yaml

# 查看systemd服务
systemctl list-unit-files | grep usv
# 应该看到6个服务都已启用
```

---

## 6. 配置文件修改

部署完成后，**必须**根据实际情况修改以下配置文件：

### 6.1 mavlink-router.conf（最重要！）

```bash
nano /opt/usv/config/mavlink-router.conf
```

**必须修改：**
```ini
[TcpEndpoint cloud]
Address=你的云服务器公网IP或域名  # ← 必须修改！
Port=5760
```

**确认：**
```ini
[UartEndpoint pixhawk]
Device=/dev/ttyS1   # 确认串口设备名
Baud=921600          # 确认与飞控SERIAL2_BAUD一致
```

### 6.2 ffmpeg_push.sh（视频推流地址）

```bash
nano /opt/usv/scripts/ffmpeg_push.sh
```

**必须修改：**
```bash
CLOUD_RTSP="rtsp://你的云服务器IP:8554/usv/camera1"  # ← 必须修改！
```

> 📌 路径中的 `camera1` 建议用船的boat_key或ICCID，方便云端区分不同船的视频流。

### 6.3 feeder_config.yaml（投料参数）

```bash
nano /opt/usv/config/feeder_config.yaml
```

**根据实际硬件调整：**
```yaml
gpio:
  pwm_pin: 12        # 确认PWM引脚
  enable_pin: 16     # 确认使能引脚
  direction_pin: 18  # 确认方向引脚

feeder:
  base_duty: 0.5     # 根据投料量需求调整(0.2-0.9)
  target_speed: 1.5  # 与飞控WP_SPEED一致(m/s)
  pwm_freq: 20000    # BTS7960建议20kHz

auto_feed:
  min_speed: 0.2     # 最低速度阈值(m/s)
  start_waypoint: 1  # 从第几个航点开始投料(0=第一个)
```

### 6.4 sensor_config.yaml（传感器参数）

```bash
nano /opt/usv/config/sensor_config.yaml
```

**根据实际料斗尺寸调整：**
```yaml
ultrasonic:
  trig_pin: 20       # 确认Trig引脚
  echo_pin: 21       # 确认Echo引脚(需分压!)
  hopper_full_cm: 5.0   # 满料时距离(cm)，实际测量
  hopper_empty_cm: 50.0 # 空料时距离(cm)，实际测量

cellular:
  at_port: "/dev/ttyUSB2"  # 确认4G AT端口
```

### 6.5 go2rtc.yaml（视频参数）

```bash
nano /opt/usv/config/go2rtc.yaml
```

**根据摄像头能力调整：**
```yaml
streams:
  camera1:
    - v4l2:///dev/video0?resolution=1280x720&fps=25&video_codec=mjpeg
    # 如果摄像头不支持720P25，改成 640x480&fps=20
```

---

## 7. 端到端联调测试清单

按照以下顺序逐项测试，每一项通过后再进行下一项：

### 7.1 硬件接线检查（上电前！）

- [ ] Pixhawk TELEM2 TX/RX交叉连接，GND共地，**未接5V**
- [ ] M10 GPS接GPS1，TX/RX交叉
- [ ] BTS7960 PWM接AUX1，EN接AUX2，GND共地
- [ ] BTS7960电源接12V，电机接M+/M-
- [ ] JSN-SR04T VCC接5V，GND共地，Trig接GPIO20，**Echo接分压电路后接GPIO21**
- [ ] 4G模块USB接USB Hub，SIM卡插入，天线接好
- [ ] USB摄像头接USB Hub
- [ ] 所有设备共地
- [ ] 电源接线正确，无短路

### 7.2 飞控独立测试

- [ ] USB连接电脑，Mission Planner能识别飞控
- [ ] 固件版本正确（ArduPilot Rover 4.5+）
- [ ] 加速度计校准完成
- [ ] 磁力计校准完成（在船上实际位置校准）
- [ ] GPS定位成功（绿色GPS图标，至少8颗星）
- [ ] 电池电压显示正确
- [ ] 推进电机转向正确（手动模式测试）

### 7.3 香橙派独立测试

- [ ] 系统启动正常，SSH可登录
- [ ] UART1启用，`/dev/ttyS1`存在
- [ ] 4G模块识别，`/dev/ttyUSB0-2`存在
- [ ] 4G拨号成功，能ping通外网
- [ ] `AT+QCCID`能读取到ICCID
- [ ] USB摄像头识别，`/dev/video0`存在
- [ ] `v4l2-ctl --list-formats-ext`能看到摄像头支持的格式

### 7.4 飞控↔香橙派串口通信测试

- [ ] 飞控和香橙派都上电
- [ ] 香橙派上执行串口测试脚本，能收到飞控心跳包
- [ ] 飞控sys_id和comp_id正确
- [ ] 飞控模式能正确读取

### 7.5 mavlink-router测试

- [ ] `systemctl start mavlink-router`启动服务
- [ ] `systemctl status mavlink-router`显示active running
- [ ] `journalctl -u mavlink-router -f`查看日志，无报错
- [ ] 本地UDP 14550端口能收到MAVLink数据（用QGC连接测试）
- [ ] 如果云平台已部署，TCP连接云服务器5760端口成功

### 7.6 boat_identity身份识别测试

- [ ] `systemctl start boat-identity`启动服务
- [ ] `journalctl -u boat-identity -f`查看日志
- [ ] 日志显示"读取到ICCID: xxxx"
- [ ] 日志显示"身份上报成功: BOAT_ID:xxxx"，每30秒一次
- [ ] 云平台MAVLink网关日志显示收到ICCID并映射到boat_key

### 7.7 云平台连接测试（需云平台已部署）

- [ ] 云平台5个Docker服务全部运行
- [ ] 船端mavlink-router连接云服务器5760成功
- [ ] 云平台MAVLink网关日志显示新船连接
- [ ] 网关通过ICCID查询数据库，映射到boat_key
- [ ] 前端登录后，船列表中该船显示"在线"
- [ ] 前端船控制台能看到实时位置、电量、模式等状态
- [ ] 位置在地图上正确显示

### 7.8 遥控指令测试

- [ ] 前端点"返航"，飞控切换到RTL模式
- [ ] 前端点"开始航行"，飞控切换到AUTO模式
- [ ] 前端点"紧急停车"，飞控切换到HOLD模式
- [ ] 前端点"开投料"，投料电机启动
- [ ] 前端点"关投料"，投料电机停止

### 7.9 自动航行+投料测试

- [ ] 前端编辑路径，设置3-5个航点
- [ ] 点"保存并上传"，提示上传成功
- [ ] 点"开始航行"，船开始按航点行驶
- [ ] 到达第一个航点后，投料电机自动启动
- [ ] 船按航线行驶，途中均匀撒料
- [ ] 到达最后一个航点，投料停止，自动返航
- [ ] 船回到停泊点，自动切换HOLD模式

### 7.10 视频流测试

- [ ] `systemctl start go2rtc`启动服务
- [ ] `systemctl start ffmpeg-push`启动推流
- [ ] 本地浏览器访问 `http://<香橙派IP>:1984` 能看到视频
- [ ] 云平台MediaMTX能收到视频流
- [ ] 前端船控制台点"视频"，能看到实时画面
- [ ] 视频延迟在可接受范围（<3秒）

### 7.11 传感器监控测试

- [ ] `systemctl start sensor-monitor`启动服务
- [ ] `journalctl -u sensor-monitor -f`查看日志，无报错
- [ ] 料位传感器读数正常（满料/空料时数值变化）
- [ ] 4G信号强度正常（CSQ 10-30）
- [ ] 箱温正常
- [ ] 前端能看到饲料余量百分比

### 7.12 避障测试（如有激光雷达）

- [ ] TF02-i安装在船头，朝前
- [ ] 飞控参数配置正确（PRX1_TYPE=7, AVOID_ENABLE=1）
- [ ] 船前方放置障碍物
- [ ] 船接近障碍物时自动减速/转向
- [ ] 障碍物移除后恢复正常航行

---

## 8. 故障排查指南

### 8.1 串口通信问题

**现象：** 香橙派收不到飞控心跳包

**排查步骤：**
1. 确认接线：TX/RX是否交叉？GND是否共地？
2. 确认飞控TELEM2参数：`SERIAL2_PROTOCOL=1`, `SERIAL2_BAUD=921`
3. 确认香橙派UART1启用：`ls /dev/ttyS1`
4. 确认波特率一致：飞控921600，mavlink-router配置921600
5. 用示波器或逻辑分析仪看TX/RX是否有数据
6. 换一根杜邦线试试（接触不良很常见）

**常用命令：**
```bash
# 查看串口设备
ls /dev/ttyS*

# 直接读取串口数据（看有没有乱码）
cat /dev/ttyS1

# 用pymavlink测试
python3 -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('/dev/ttyS1', baud=921600); m.wait_heartbeat(); print('OK')"
```

### 8.2 4G模块问题

**现象1：** /dev/ttyUSB* 不存在

**排查：**
1. `lsusb` 查看是否识别到移远模块（ID 2c7c:0125或类似）
2. 检查USB线是否是数据线（不是充电线）
3. 检查4G模块供电是否充足（峰值2A）
4. `dmesg | grep ttyUSB` 查看内核日志

**现象2：** 4G拨号成功但上不了网

**排查：**
1. 确认APN正确：移动=cmnet, 联通=3gnet, 电信=ctnet
2. 确认物联网卡已激活且有流量
3. `AT+CSQ` 查看信号强度（应>10）
4. `AT+CGREG?` 查看是否注册网络（应返回0,1或0,5）
5. 检查天线是否接好

**现象3：** 读取不到ICCID

**排查：**
1. 确认AT端口（通常是/dev/ttyUSB2，可能是ttyUSB0或ttyUSB3）
2. `minicom -D /dev/ttyUSB2 -b 115200` 手动测试AT命令
3. 输入 `AT` 应返回 `OK`
4. 输入 `AT+QCCID` 应返回ICCID
5. 如果AT命令无响应，换一个ttyUSB端口试试

### 8.3 mavlink-router问题

**现象：** 服务启动失败或频繁重启

**排查：**
1. `systemctl status mavlink-router` 查看错误
2. `journalctl -u mavlink-router -n 50` 查看日志
3. 确认配置文件路径正确：`/opt/usv/config/mavlink-router.conf`
4. 确认串口设备存在：`ls /dev/ttyS1`
5. 手动运行测试：`mavlink-routerd -c /opt/usv/config/mavlink-router.conf`
6. 检查云服务器地址和端口是否正确，网络是否通

**常用命令：**
```bash
# 查看服务状态
systemctl status mavlink-router

# 查看实时日志
journalctl -u mavlink-router -f

# 手动运行（前台，看报错）
mavlink-routerd -c /opt/usv/config/mavlink-router.conf

# 测试TCP连接云服务器
telnet 云服务器IP 5760
# 或
nc -zv 云服务器IP 5760
```

### 8.4 投料电机不转

**排查步骤：**
1. 确认BTS7960电源：12V是否接上？指示灯是否亮？
2. 确认电机接线：M+/M-是否接好？
3. 确认PWM信号：用示波器看AUX1是否有PWM输出
4. 确认GND共地：BTS7960的GND和飞控GND必须连在一起
5. 确认飞控AUX输出功能：`AUX1_FUNCTION=0`（通用输出）
6. 手动测试：用MAVLink指令设置AUX1 PWM为高，看电机是否转
   ```python
   from pymavlink import mavutil
   master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
   master.wait_heartbeat()
   # 设置AUX1 (servo 9) PWM为2000us（全速）
   master.mav.command_long_send(
       master.target_system, master.target_component,
       mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
       0, 9, 2000, 0, 0, 0, 0, 0
   )
   ```

### 8.5 料位传感器读数异常

**排查步骤：**
1. 确认5V供电：JSN-SR04T VCC是否接5V？
2. 确认Echo分压：是否接了1k+2k分压电阻？
3. 确认Trig/Echo引脚：配置文件和实际接线是否一致
4. 用示波器看Trig是否有触发信号，Echo是否有回波
5. 检查传感器安装：是否垂直向下？是否有遮挡？
6. 调整料斗参数：`hopper_full_cm`和`hopper_empty_cm`是否与实际一致

### 8.6 视频流问题

**现象1：** /dev/video0不存在

**排查：**
1. `ls /dev/video*` 查看
2. `lsusb` 查看是否识别到USB摄像头
3. 换一个USB口试试
4. 检查USB Hub供电是否充足

**现象2：** go2rtc启动失败

**排查：**
1. `journalctl -u go2rtc -n 50` 查看日志
2. 确认配置文件路径：`/opt/usv/config/go2rtc.yaml`
3. 手动运行：`go2rtc -config /opt/usv/config/go2rtc.yaml`
4. 确认摄像头支持的格式：`v4l2-ctl --device=/dev/video0 --list-formats-ext`
5. 如果摄像头不支持MJPEG，改成YUYV或降低分辨率

**现象3：** 前端看不到视频

**排查：**
1. 确认go2rtc本地能看到视频：`http://<香橙派IP>:1984`
2. 确认ffmpeg-push服务运行：`systemctl status ffmpeg-push`
3. 确认推流地址正确：云服务器IP和端口
4. 确认云平台MediaMTX运行正常
5. 确认前端视频地址配置正确（.env中的VITE_VIDEO_URL）

### 8.7 云平台看不到船在线

**排查步骤：**
1. 确认船端4G网络正常：`ping www.baidu.com`
2. 确认mavlink-router运行：`systemctl status mavlink-router`
3. 确认云服务器地址配置正确：`/opt/usv/config/mavlink-router.conf`
4. 测试TCP连接：`nc -zv 云服务器IP 5760`
5. 确认云平台MAVLink网关运行：`docker compose ps`
6. 查看网关日志：`docker compose logs mavlink-gateway -f`
7. 确认ICCID已在云平台注册：添加船时填写的ICCID必须与船端实际ICCID一致
8. 查看网关是否收到ICCID：网关日志中应有"收到BOAT_ID:xxx"和"映射到boat_key:xxx"

### 8.8 服务开机不自启

**排查：**
```bash
# 确认服务已启用
systemctl is-enabled mavlink-router
# 应返回 enabled

# 如果没启用，手动启用
systemctl enable mavlink-router

# 查看所有usv服务状态
systemctl list-units | grep usv
```

---

## 附录A：常用命令速查

### 香橙派系统命令
```bash
# 查看系统信息
uname -a
df -h
free -h

# 查看串口设备
ls /dev/ttyS*
ls /dev/ttyUSB*

# 查看USB设备
lsusb

# 查看摄像头
ls /dev/video*
v4l2-ctl --device=/dev/video0 --list-formats-ext

# 查看网络
ip addr
nmcli device status
ping -c 4 www.baidu.com

# 读取4G ICCID
minicom -D /dev/ttyUSB2 -b 115200
# 输入 AT+QCCID
```

### 服务管理命令
```bash
# 查看所有服务状态
systemctl status mavlink-router boat-identity go2rtc ffmpeg-push feeder-control sensor-monitor

# 启动/停止/重启服务
systemctl start <服务名>
systemctl stop <服务名>
systemctl restart <服务名>

# 查看实时日志
journalctl -u <服务名> -f

# 查看最近50条日志
journalctl -u <服务名> -n 50

# 启用/禁用开机自启
systemctl enable <服务名>
systemctl disable <服务名>
```

### 云平台Docker命令（在云服务器上执行）
```bash
cd /path/to/cloud

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f mavlink-gateway
docker compose logs -f api-server

# 重启服务
docker compose restart mavlink-gateway

# 重新构建并启动
docker compose up -d --build
```

---

## 附录B：接线检查清单（打印出来对照）

上电前逐项打勾：

- [ ] Pixhawk TELEM2 TX → 香橙派 GPIO10 (RX)
- [ ] Pixhawk TELEM2 RX → 香橙派 GPIO8 (TX)
- [ ] Pixhawk TELEM2 GND → 香橙派 GND
- [ ] Pixhawk TELEM2 5V → **未接**（重要！）
- [ ] M10 GPS VCC → Pixhawk GPS1 5V
- [ ] M10 GPS GND → Pixhawk GPS1 GND
- [ ] M10 GPS TX → Pixhawk GPS1 RX
- [ ] M10 GPS RX → Pixhawk GPS1 TX
- [ ] BTS7960 PWM → Pixhawk AUX1
- [ ] BTS7960 EN → Pixhawk AUX2
- [ ] BTS7960 GND → Pixhawk GND
- [ ] BTS7960 V+ → 12V电池正极
- [ ] BTS7960 GND → 12V电池负极
- [ ] BTS7960 M+ → 投料电机正极
- [ ] BTS7960 M- → 投料电机负极
- [ ] JSN-SR04T VCC → 5V
- [ ] JSN-SR04T GND → GND
- [ ] JSN-SR04T Trig → 香橙派 GPIO20
- [ ] JSN-SR04T Echo → 分压电路 → 香橙派 GPIO21
- [ ] 4G模块 USB → USB Hub
- [ ] 4G模块 天线 → 接好
- [ ] 4G模块 SIM卡 → 插入，方向正确
- [ ] USB摄像头 → USB Hub
- [ ] 所有设备 GND → 共地
- [ ] 电源正负极 → 无短路
- [ ] 保险丝 → 已安装

---

**文档结束。如有问题请参考故障排查指南，或在项目中提交Issue。**
