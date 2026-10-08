# 无人船 Web 控制台

基于 **React 18 + TypeScript + Vite + Tailwind CSS + 高德地图** 的无人船远程控制前端。

## 功能

- 用户登录/注册 (JWT认证)
- 我的船列表 (实时在线状态、电量、模式)
- 船控制台:
  - 实时仪表盘 (位置/速度/航向/电量/饲料/4G信号/温度)
  - 高德地图实时位置 + 航向箭头
  - 路径编辑 (点击添加航点、拖动调整、右键删除)
  - 一键上传路径到船
  - 遥控操作 (开始航行/返航/紧急停车/投料开关)
  - 实时视频监控 (WebRTC)
- 历史轨迹回放 (时间轴拖动、状态同步显示)

## 快速开始

### 1. 安装依赖

```bash
cd web
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`:

```env
# 后端API地址
VITE_API_BASE_URL=http://你的云服务器IP:8000

# WebSocket地址
VITE_WS_URL=ws://你的云服务器IP:8000/ws

# 视频流地址 (MediaMTX WebRTC)
VITE_VIDEO_URL=http://你的云服务器IP:8889

# 高德地图Key (必须配置, 否则地图无法显示)
VITE_AMAP_KEY=你的高德地图API_KEY
VITE_AMAP_SECURITY_CODE=你的高德地图安全密钥
```

> 高德地图Key申请: https://lbs.amap.com/
> 申请"Web端(JS API)"类型的Key, 同时获取安全密钥(securityJsCode)

### 3. 启动开发服务器

```bash
npm run dev
```

浏览器打开 http://localhost:5173

### 4. 构建生产版本

```bash
npm run build
# 产物在 dist/ 目录
```

### 5. 部署 (Nginx)

```bash
# 将dist目录上传到服务器
# Nginx配置示例:
server {
    listen 80;
    server_name your-domain.com;

    root /var/www/usv-web/dist;
    index index.html;

    # SPA路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 反向代理API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    # 反向代理WebSocket
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 项目结构

```
web/
├── index.html                 # 入口HTML (含高德地图SDK)
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── .env.example
└── src/
    ├── main.tsx               # 入口
    ├── App.tsx                # 路由配置
    ├── index.css              # 全局样式 (Tailwind)
    ├── types/
    │   └── index.ts           # TypeScript类型定义
    ├── api/                   # API层 (axios封装)
    │   ├── client.ts
    │   ├── auth.ts
    │   ├── boats.ts
    │   ├── missions.ts
    │   ├── telemetry.ts
    │   └── control.ts
    ├── context/
    │   └── AuthContext.tsx    # 认证上下文
    ├── hooks/
    │   └── useBoatWebSocket.ts # WebSocket实时状态
    ├── components/
    │   ├── Layout.tsx         # 布局 (侧边栏)
    │   ├── ProtectedRoute.tsx # 路由保护
    │   ├── BoatCard.tsx       # 船卡片
    │   ├── BatteryIndicator.tsx # 电池指示器
    │   ├── VideoPlayer.tsx    # 视频播放器 (iframe嵌入MediaMTX)
    │   └── WaypointMap.tsx    # 高德地图航点编辑器
    ├── pages/
    │   ├── Login.tsx          # 登录
    │   ├── Register.tsx       # 注册
    │   ├── BoatList.tsx       # 船列表
    │   ├── BoatConsole.tsx    # 船控制台 (核心)
    │   └── History.tsx        # 历史轨迹回放
    └── utils/
        └── format.ts          # 格式化工具
```

## 与后端对接

前端通过以下方式与云平台通信:

| 通信方式 | 用途 | 地址 |
|---------|------|------|
| REST API | 数据CRUD、控制指令 | `VITE_API_BASE_URL/api/*` |
| WebSocket | 船实时状态推送 (1Hz) | `VITE_WS_URL?token=JWT` |
| WebRTC | 实时视频 | `VITE_VIDEO_URL/camera{N}` |

## 注意事项

1. **高德地图Key必须配置**, 否则地图页面空白
2. **生产环境必须修改JWT密钥** (后端 `.env` 的 `SECRET_KEY`)
3. **CORS配置**: 开发环境Vite会代理, 生产环境用Nginx反向代理避免跨域
4. **视频流**: 船端推流路径 `usv/camera1`, 前端根据船的 `boat_key` (如 `boat_1`) 映射为 `camera1`
5. **4G网络下视频延迟**: 通常300ms-1s, 取决于4G信号质量

## 常见问题

### 地图不显示
- 检查 `VITE_AMAP_KEY` 是否正确配置
- 检查高德控制台是否绑定了正确的域名 (localhost和生产域名都要加)
- 浏览器控制台看是否有高德API报错

### WebSocket连不上
- 检查 `VITE_WS_URL` 是否正确
- 检查后端api-server是否在运行
- 检查防火墙是否开放8000端口

### 视频黑屏
- 检查船端ffmpeg-push服务是否在运行
- 检查MediaMTX是否收到推流: `docker compose logs mediamtx`
- 检查WebRTC ICE候选地址 (`.env` 的 `MEDIAMTX_PUBLIC_IP`)
