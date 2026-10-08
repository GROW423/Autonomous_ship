// 类型定义 - 与后端schemas对应

export interface User {
  id: number
  username: string
  email: string | null
  full_name: string | null
  phone: string | null
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Region {
  id: number
  name: string
  description: string | null
  is_active: boolean
  created_at: string
}

export interface Boat {
  id: number
  name: string
  mavlink_sys_id: number
  boat_key: string
  iccid: string | null
  region_id: number | null
  region_name: string | null
  description: string | null
  home_lat: number | null
  home_lon: number | null
  is_active: boolean
  created_at: string
}

export interface BoatStatus {
  boat_id: string
  online: boolean
  lat: number | null
  lon: number | null
  heading: number | null
  groundspeed: number | null
  battery_voltage: number | null
  battery_current: number | null
  battery_remaining: number | null
  flight_mode: string | null
  armed: boolean | null
  current_waypoint: number | null
  feed_level: number | null
  cellular_csq: number | null
  box_temperature: number | null
  gps_fix_type: string | null
  gps_satellites_visible: number | null
  last_status_text: string | null
  updated_at: number | null
}

export interface Waypoint {
  lat: number
  lon: number
  alt: number
  speed: number
  action: string | null
}

export interface Mission {
  id: number
  boat_id: number
  name: string
  description: string | null
  waypoints: Waypoint[]
  status: string
  created_at: string
  updated_at: string | null
  executed_at: string | null
  completed_at: string | null
}

export interface TelemetryRecord {
  timestamp: string
  lat: number | null
  lon: number | null
  heading: number | null
  groundspeed: number | null
  battery_remaining: number | null
  flight_mode: string | null
  current_waypoint: number | null
  feed_level: number | null
}

export interface ControlCommand {
  type: string
  custom_mode?: number
  arm?: boolean
  channel?: number
  pwm?: number
  x?: number
  y?: number
}

export interface CommandResponse {
  success: boolean
  message: string
}

// WebSocket消息
export interface WSMessage {
  type: string
  data?: BoatStatus[]
  timestamp?: number
}
