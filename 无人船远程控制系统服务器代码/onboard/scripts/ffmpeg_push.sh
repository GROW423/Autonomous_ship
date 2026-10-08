#!/bin/bash
# ============================================================
# 视频推流脚本
# 从本地go2rtc拉RTSP流, 推送到云端MediaMTX
# 支持断线自动重连
# ============================================================

set -e

# 配置 (根据实际情况修改)
LOCAL_RTSP="rtsp://127.0.0.1:8554/camera1"
# !!! 修改为你的云服务器地址 !!!
CLOUD_RTSP="rtsp://YOUR_SERVER_IP:8554/usv/camera1"

# 推流参数
# -rtsp_transport tcp: 使用TCP传输, 4G网络下更稳定
# -c copy: 不重新编码, 直接复制流 (低CPU占用)
# -f rtsp: 输出RTSP格式
FFMPEG_OPTS="-rtsp_transport tcp -i ${LOCAL_RTSP} -c copy -f rtsp -rtsp_transport tcp ${CLOUD_RTSP}"

LOG_FILE="/opt/usv/logs/ffmpeg-push.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 视频推流启动" >> "$LOG_FILE"
echo "  本地源: ${LOCAL_RTSP}" >> "$LOG_FILE"
echo "  云端目标: ${CLOUD_RTSP}" >> "$LOG_FILE"

# 等待go2rtc启动 (最多等30秒)
for i in $(seq 1 30); do
    if ffprobe -rtsp_transport tcp -timeout 2000000 -i "$LOCAL_RTSP" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 本地流就绪" >> "$LOG_FILE"
        break
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 等待本地流就绪... ($i/30)" >> "$LOG_FILE"
    sleep 1
done

# 主循环: ffmpeg退出后自动重启
while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始推流" >> "$LOG_FILE"
    ffmpeg -loglevel warning $FFMPEG_OPTS 2>> "$LOG_FILE" || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 推流中断, 3秒后重连" >> "$LOG_FILE"
    sleep 3
done
