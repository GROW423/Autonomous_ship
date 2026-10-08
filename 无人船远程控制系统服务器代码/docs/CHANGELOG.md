# 修改记录 (CHANGELOG)

本项目所有重要变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.0.0] - 2026-08-21

### 新增

#### 船载端 (onboard/)
- **MAVLink遥测转发**：基于mavlink-router，将Pixhawk4飞控的MAVLink数据通过4G网络转发到云平台，支持断线自动重连
- **视频流服务**：基于go2rtc采集USB摄像头，通过ffmpeg推RTSP到云端MediaMTX，支持WebRTC低延迟播放
- **投料控制系统**：Python程序，通过MAVLink监听飞控状态（飞行模式/船速/航点），自动控制投料电机启停，支持根据船速实时调节投料量（速度补偿算法，保证单位面积投料均匀）
- **传感器监控系统**：读取JSN-SR04T超声波料位传感器、4G模块信号强度（AT+CSQ）、箱内温度，通过MAVLink NAMED_VALUE_FLOAT自定义消息上报
- **5个systemd开机自启服务**：mavlink-router、go2rtc、ffmpeg-push、feeder-control、sensor-monitor
- **一键系统初始化脚本**：自动安装依赖、编译mavlink-router、安装go2rtc、配置UART串口、部署所有服务
- **完整接线说明**：Pixhawk4 TELEM2 ↔ OrangePi Zero2W UART、BTS7960电机驱动、超声波传感器接线

#### 云平台 (cloud/)
- **MAVLink网关服务**：TCP服务端监听5760端口，接受多艘船同时连接，解析MAVLink消息（位置/电量/模式/航点/自定义数据），实时状态写入Redis，历史数据批量写入PostgreSQL
- **指令转发系统**：通过Redis Pub/Sub接收API下发的控制指令，转发MAVLink消息给对应船（模式切换/解锁/航点任务上传/返航/舵机控制/手动控制）
- **FastAPI后端**：REST API + WebSocket，JWT认证，多租户隔离（用户只能看到自己的船）
- **用户管理**：注册/登录/JWT验证
- **船管理**：增删改查，实时状态查询
- **任务管理**：航路点任务CRUD，上传到船，一键执行
- **遥测历史**：轨迹查询，最近记录，统计摘要（里程/时长/平均速度/最大速度）
- **控制指令**：通用指令接口，一键返航，开始AUTO，紧急停车，投料开关
- **WebSocket实时推送**：1Hz推送所有船的实时状态给前端
- **MediaMTX视频SFU**：接收船端RTSP推流，转WebRTC/HLS给前端播放
- **Docker Compose一键编排**：PostgreSQL 16 + Redis 7 + MediaMTX + MAVLink网关 + API服务
- **一键部署脚本**：自动安装Docker、交互式配置.env、构建镜像、启动服务、配置防火墙、验证服务状态

#### 前端 (web/)
- **React 18 + TypeScript + Vite + Tailwind CSS** 技术栈
- **高德地图集成**：实时位置显示、航向箭头、历史轨迹、航点编辑器
- **登录/注册页面**：JWT认证，表单验证
- **船列表页面**：卡片展示所有船，实时在线状态、电量、模式、速度、位置、饲料余量
- **船控制台（核心页面）**：
  - 左侧实时仪表盘：电池（电压/电流/电量）、航行状态（速度/航向/航点/解锁）、位置（经纬度/GPS定位/卫星数）、饲料余量、4G信号、箱温、状态告警
  - 右侧高德地图：船实时位置+航向，路径编辑模式
  - 底部遥控栏：开始航行/返航/紧急停车/投料开关/编辑路径
  - 视频监控弹窗：WebRTC实时视频
  - 已保存任务快速执行
- **路径编辑器**：点击地图添加航点、拖动调整位置、右键删除、航点编号显示（起点绿色/终点红色/中间蓝色）、一键保存并上传到船
- **历史轨迹回放**：时间范围选择、地图轨迹显示、时间轴拖动播放、同步显示当时状态数据
- **响应式布局**：侧边栏导航，用户信息，退出登录

### 技术栈

| 层级 | 技术 |
|------|------|
| 飞控 | Holybro Pixhawk4 + ArduPilot Rover 4.5+ |
| 伴飞计算机 | OrangePi Zero2W (全志H618, 2GB) |
| 船载端语言 | Bash + Python 3.11 |
| 云平台网关 | Python + pymavlink + redis + psycopg2 |
| 云平台API | Python + FastAPI + SQLAlchemy + Pydantic |
| 数据库 | PostgreSQL 16 + Redis 7 |
| 视频SFU | MediaMTX |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 地图 | 高德地图 JS API 2.0 |
| 部署 | Docker Compose |

### 已知限制

- 船载端投料控制使用软件PWM（100Hz），精度有限，对投料均匀性要求极高的场景建议使用硬件PWM或独立调速器
- WebRTC视频在4G弱网下可能卡顿，可降低分辨率或码率
- 前端地图使用高德地图，需要申请API Key，仅支持国内地图
- 避障功能依赖ArduPilot Rover固件配置，需在飞控端单独配置激光雷达参数
- 当前版本未实现多用户同时遥控同一艘船的互斥机制

---

## [未发布]

### 计划中

- 船载端硬件PWM支持（使用OrangePi硬件PWM引脚）
- 多用户遥控互斥与权限管理
- 任务模板与定时任务（按时间表自动执行投喂）
- 低电量自动返航与饲料不足告警推送
- 移动端适配（小程序/PWA）
- 视频录像与云端存储
- 多船编队控制
- 数据统计报表与导出
