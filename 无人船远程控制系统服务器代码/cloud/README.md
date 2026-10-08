# 无人船云平台

基于 **FastAPI + PostgreSQL + Redis + MediaMTX** 的无人船远程控制云平台。

## 架构概述

```
船端 (4G)                    云平台 (Docker Compose)
─────────                    ──────────────────────────
mavlink-router ──TCP 5760──► MAVLink Gateway ──► Redis (实时状态)
                                       │              │
                                       │              ├──► PostgreSQL (历史数据)
                                       │              └──► WebSocket ──► 前端
ffmpeg ──RTSP 8554──────────► MediaMTX ──WebRTC──► 前端
                                       │
                                       └──HLS──► 前端 (备选)

前端 ──HTTPS/WSS 8000──────► FastAPI ──REST API──► PostgreSQL
                                       │
                                       └──Redis Pub/Sub──► MAVLink Gateway ──► 船端
```

## 服务列表

| 服务 | 端口 | 功能 |
|------|------|------|
| mqtt-broker (可选 profile) | 8883/TLS | 船端 MQTT 通信；只接受 TLS/密码认证 |
| postgres | 5432 | 主数据库 (用户/船/任务/遥测历史) |
| redis | 6379 | 实时状态缓存 + Pub/Sub 指令通道 |
| mediamtx | 8554/8889/8888 | 视频SFU (RTSP推流/WebRTC/HLS拉流) |
| mavlink-gateway | 5760 | 船端MAVLink通信网关 |
| api-server | 8000 | REST API + WebSocket |

## 快速部署

### 1. 环境要求

- 云服务器 (Linux, 2核4G以上, 公网IP)
- Docker 24+ 和 Docker Compose v2+
- 开放端口: 5760 (MAVLink), 8000 (API), 8554 (RTSP), 8889 (WebRTC), 8888 (HLS)

### 2. 配置

```bash
cd cloud
cp .env.example .env
nano .env
```

必须修改的配置项：
```env
# 数据库密码 (务必修改)
POSTGRES_PASSWORD=your_strong_password

# JWT密钥 (生产环境必须修改为随机字符串)
SECRET_KEY=please_change_this_to_a_long_random_string_at_least_32_chars

# 云服务器公网IP或域名 (用于WebRTC ICE候选)
MEDIAMTX_PUBLIC_IP=your-server-ip-or-domain
MEDIAMTX_WEBRTC_URL=http://your-server-ip-or-domain:8889

# CORS (生产环境指定前端域名)
CORS_ORIGINS=http://your-frontend-domain.com
```

### 3. 启动

```bash
docker compose up -d
```

MQTT Broker 单独启用：先按 [`../docs/MQTT_MAVLINK_SIMULATION.md`](../docs/MQTT_MAVLINK_SIMULATION.md) 准备 TLS 证书和密码文件，再运行 `docker compose --profile mqtt up -d mqtt-broker`。Broker 不监听明文 1883；腾讯云安全组和 4G 物联卡白名单需放行 TCP 8883。

### 4. 验证

```bash
# 查看所有服务状态
docker compose ps

# 查看日志
docker compose logs -f mavlink-gateway
docker compose logs -f api-server

# 测试API
curl http://localhost:8000/health
# 应返回 {"status":"ok"}

# API文档
# 浏览器打开 http://<服务器IP>:8000/docs
```

## 与船载端对接

### MAVLink遥测

船载端 `mavlink-router.conf` 配置：
```ini
[TcpEndpoint cloud]
Address=<云服务器公网IP>
Port=5760
```

船端启动后会主动连接云服务器5760端口，MAVLink网关接受连接并解析消息。

### 视频流

船载端 `ffmpeg_push.sh` 配置：
```bash
CLOUD_RTSP="rtsp://<云服务器公网IP>:8554/usv/camera1"
```

前端WebRTC播放地址：
```
http://<云服务器IP>:8889/usv/camera1
```

## API 概览

所有API需要JWT认证 (除注册/登录/健康检查外)。

### 认证
- `POST /api/auth/register` - 注册
- `POST /api/auth/login` - 登录 (返回JWT token)
- `GET /api/auth/me` - 当前用户信息

### 无人船管理
- `GET /api/boats` - 我的船列表
- `POST /api/boats` - 添加船
- `GET /api/boats/{id}` - 船详情
- `PUT /api/boats/{id}` - 更新船信息
- `DELETE /api/boats/{id}` - 删除船
- `GET /api/boats/{id}/status` - 船实时状态 (从Redis)

### 任务管理
- `GET /api/boats/{id}/missions` - 任务列表
- `POST /api/boats/{id}/missions` - 创建任务 (航路点)
- `GET /api/boats/{id}/missions/{mid}` - 任务详情
- `PUT /api/boats/{id}/missions/{mid}` - 更新任务
- `DELETE /api/boats/{id}/missions/{mid}` - 删除任务
- `POST /api/boats/{id}/missions/{mid}/upload` - 上传任务到船
- `POST /api/boats/{id}/missions/{mid}/execute` - 开始执行任务

### 遥测历史
- `GET /api/boats/{id}/telemetry/history` - 历史轨迹 (时间范围)
- `GET /api/boats/{id}/telemetry/latest` - 最近一条记录
- `GET /api/boats/{id}/telemetry/summary` - 统计摘要 (里程/时长/速度)

### 控制指令
- `POST /api/boats/{id}/control` - 通用指令 (set_mode/rtl/arm_disarm等)
- `POST /api/boats/{id}/control/rtl` - 一键返航
- `POST /api/boats/{id}/control/start_auto` - 开始AUTO模式
- `POST /api/boats/{id}/control/stop` - 紧急停车
- `POST /api/boats/{id}/control/feed/on` - 开启投料
- `POST /api/boats/{id}/control/feed/off` - 关闭投料

### WebSocket
- `WS /ws?token=<JWT>` - 实时推送船状态 (1Hz)

## 多租户隔离

- 每艘船属于一个用户 (`boats.user_id`)
- 所有查询自动加 `WHERE user_id = 当前用户`
- 用户只能看到和操作自己的船
- JWT token中包含用户ID，服务端验证

## 数据模型

```
users (用户)
  └── boats (无人船, 1对多)
        ├── missions (任务/航路点, 1对多)
        └── telemetry_history (遥测历史, 按boat_key关联)
```

## 故障排查

### 船端连不上MAVLink网关

```bash
# 检查网关是否在监听
docker compose logs mavlink-gateway
# 应看到 "等待船端连接"

# 检查端口是否开放
telnet <服务器IP> 5760

# 检查船端mavlink-router配置
# Address和Port是否正确
```

### 视频推流失败

```bash
# 检查MediaMTX日志
docker compose logs mediamtx

# 检查船端ffmpeg-push日志
journalctl -u ffmpeg-push -f

# 测试RTSP推流 (在船端)
ffprobe rtsp://<服务器IP>:8554/usv/camera1

# 测试WebRTC播放 (浏览器)
http://<服务器IP>:8889/usv/camera1
```

### WebRTC无法播放 (黑画面)

最常见原因是WebRTC ICE候选地址不对：
1. 确认 `.env` 中 `MEDIAMTX_PUBLIC_IP` 是服务器公网IP
2. 确认防火墙开放了UDP端口 (WebRTC使用随机UDP端口，建议开放全UDP或使用TURN)
3. 浏览器控制台查看ICE连接状态

### API返回401

- 确认登录获取了token
- 请求头包含 `Authorization: Bearer <token>`
- token未过期 (默认24小时)

### 数据库连接失败

```bash
# 检查PostgreSQL状态
docker compose ps postgres
docker compose logs postgres

# 检查DATABASE_URL配置
# 默认: postgresql://usv:usv_secret@postgres:5432/usv
# 密码必须与POSTGRES_PASSWORD一致
```

## 目录结构

```
cloud/
├── docker-compose.yml          # Docker编排
├── .env.example                # 环境变量示例
├── README.md                   # 本文档
├── mavlink-gateway/            # MAVLink通信网关
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py                 # TCP服务入口
│   ├── boat_connection.py      # 单船连接处理
│   ├── mavlink_parser.py       # MAVLink消息解析
│   ├── redis_store.py          # Redis状态存储
│   └── db_writer.py            # 历史数据批量写入
├── api-server/                 # FastAPI后端
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # FastAPI入口
│   ├── config.py
│   ├── database.py
│   ├── models.py               # SQLAlchemy模型
│   ├── schemas.py              # Pydantic schemas
│   ├── auth.py                 # JWT认证
│   ├── websocket.py            # WebSocket实时推送
│   └── routers/
│       ├── auth.py
│       ├── boats.py
│       ├── missions.py
│       ├── telemetry.py
│       └── control.py
└── mediamtx/
    └── mediamtx.yml            # 视频SFU配置
```
