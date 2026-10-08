import { useState } from 'react'
import { Video, VideoOff, Maximize2, RefreshCw } from 'lucide-react'

interface VideoPlayerProps {
  boatKey: string
  className?: string
}

const VIDEO_BASE_URL = import.meta.env.VITE_VIDEO_URL || 'http://localhost:8889'

export default function VideoPlayer({ boatKey, className = '' }: VideoPlayerProps) {
  const [visible, setVisible] = useState(false)
  const [loading, setLoading] = useState(true)

  // MediaMTX WebRTC播放页面
  // 船端推流路径: usv/camera1 (boatKey如 boat_1 -> camera1)
  const cameraPath = boatKey.replace('boat_', 'camera')
  const videoUrl = `${VIDEO_BASE_URL}/${cameraPath}`

  if (!visible) {
    return (
      <div
        className={`bg-gray-900 rounded-lg flex items-center justify-center cursor-pointer hover:bg-gray-800 transition-colors ${className}`}
        onClick={() => setVisible(true)}
      >
        <div className="text-center text-gray-400">
          <Video className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p className="text-sm">点击查看实时视频</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`relative bg-black rounded-lg overflow-hidden ${className}`}>
      {/* 视频iframe */}
      <iframe
        src={videoUrl}
        className="w-full h-full border-0"
        allow="autoplay; fullscreen"
        onLoad={() => setLoading(false)}
      />

      {/* 加载遮罩 */}
      {loading && (
        <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
          <div className="text-white text-center">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2" />
            <p className="text-sm">连接视频流中...</p>
          </div>
        </div>
      )}

      {/* 控制栏 */}
      <div className="absolute top-2 right-2 flex gap-1">
        <button
          onClick={() => {
            setLoading(true)
            const iframe = document.querySelector('iframe')
            if (iframe) iframe.src = iframe.src
          }}
          className="p-1.5 bg-black/50 rounded text-white hover:bg-black/70"
          title="刷新"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
        <button
          onClick={() => setVisible(false)}
          className="p-1.5 bg-black/50 rounded text-white hover:bg-black/70"
          title="关闭"
        >
          <VideoOff className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
