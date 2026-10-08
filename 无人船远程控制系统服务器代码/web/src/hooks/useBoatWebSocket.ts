import { useEffect, useRef, useState, useCallback } from 'react'
import type { BoatStatus, WSMessage } from '../types'
import { useAuth } from '../context/AuthContext'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

/**
 * WebSocket连接Hook - 接收船实时状态 (1Hz)
 */
export function useBoatWebSocket() {
  const { token } = useAuth()
  const [statuses, setStatuses] = useState<Map<string, BoatStatus>>(new Map())
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<number | null>(null)

  const connect = useCallback(() => {
    if (!token) return

    const url = `${WS_URL}?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      console.log('[WS] 已连接')
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        if (msg.type === 'boat_statuses' && msg.data) {
          setStatuses((prev) => {
            const next = new Map(prev)
            for (const s of msg.data!) {
              next.set(s.boat_id, s)
            }
            return next
          })
        }
      } catch (e) {
        console.error('[WS] 解析消息失败', e)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      console.log('[WS] 断开, 3秒后重连')
      reconnectTimer.current = window.setTimeout(connect, 3000)
    }

    ws.onerror = (err) => {
      console.error('[WS] 错误', err)
    }
  }, [token])

  useEffect(() => {
    if (token) {
      connect()
    }
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [token, connect])

  // 获取指定船的状态
  const getBoatStatus = useCallback((boatKey: string): BoatStatus | undefined => {
    return statuses.get(boatKey)
  }, [statuses])

  return { statuses, connected, getBoatStatus }
}
