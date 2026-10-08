"""
历史遥测数据批量写入PostgreSQL
每艘船维护一个缓冲区, 定时批量写入, 减少数据库压力
"""
import time
import threading
import psycopg2
from psycopg2.extras import execute_values
from config import config


class DbWriter:
    def __init__(self):
        self.conn = None
        self._connect()
        self._ensure_table()
        # 每艘船的缓冲区: {boat_id: [(timestamp, lat, lon, ...), ...]}
        self._buffers = {}
        self._last_write = {}
        self._lock = threading.Lock()
        self._running = True
        # 后台批量写入线程
        self._writer_thread = threading.Thread(target=self._batch_write_loop, daemon=True)
        self._writer_thread.start()

    def _connect(self):
        """连接数据库"""
        self.conn = psycopg2.connect(config.DATABASE_URL)
        self.conn.autocommit = False

    def _ensure_table(self):
        """确保遥测历史表存在"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_history (
                    id BIGSERIAL PRIMARY KEY,
                    boat_id VARCHAR(64) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    lat DOUBLE PRECISION,
                    lon DOUBLE PRECISION,
                    heading DOUBLE PRECISION,
                    groundspeed DOUBLE PRECISION,
                    battery_voltage DOUBLE PRECISION,
                    battery_current DOUBLE PRECISION,
                    battery_remaining INTEGER,
                    flight_mode VARCHAR(32),
                    armed BOOLEAN,
                    current_waypoint INTEGER,
                    feed_level DOUBLE PRECISION,
                    cellular_csq INTEGER,
                    box_temperature DOUBLE PRECISION,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            # 索引
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_boat_time
                ON telemetry_history (boat_id, timestamp DESC);
            """)
            self.conn.commit()

    def lookup_boat_by_iccid(self, iccid: str) -> str | None:
        """通过ICCID查询船的boat_key (全局唯一标识)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT boat_key FROM boats WHERE iccid = %s AND is_active = true",
                    (iccid,)
                )
                row = cur.fetchone()
                if row:
                    return row[0]
        except Exception as e:
            # 连接可能断开, 重连后重试
            try:
                self._connect()
                with self.conn.cursor() as cur:
                    cur.execute(
                        "SELECT boat_key FROM boats WHERE iccid = %s AND is_active = true",
                        (iccid,)
                    )
                    row = cur.fetchone()
                    if row:
                        return row[0]
            except Exception as e2:
                print(f"查询ICCID失败: {e2}")
        return None

    def add_record(self, boat_id: str, status: dict):
        """添加一条遥测记录到缓冲区 (去重, 最小间隔)"""
        now = time.time()
        # 最小间隔检查
        last = self._last_write.get(boat_id, 0)
        if now - last < config.HISTORY_MIN_INTERVAL:
            return

        with self._lock:
            if boat_id not in self._buffers:
                self._buffers[boat_id] = []
            self._buffers[boat_id].append((
                now,
                status.get("lat"),
                status.get("lon"),
                status.get("heading"),
                status.get("groundspeed"),
                status.get("battery_voltage"),
                status.get("battery_current"),
                status.get("battery_remaining"),
                status.get("flight_mode"),
                status.get("armed"),
                status.get("current_waypoint"),
                status.get("feed_level"),
                status.get("cellular_csq"),
                status.get("box_temperature"),
            ))
            self._last_write[boat_id] = now

    def _batch_write_loop(self):
        """后台线程: 定时批量写入"""
        while self._running:
            time.sleep(config.HISTORY_BATCH_INTERVAL)
            self._flush_all()

    def _flush_all(self):
        """将所有缓冲区写入数据库"""
        with self._lock:
            if not self._buffers:
                return
            buffers = dict(self._buffers)
            self._buffers.clear()

        total = 0
        try:
            with self.conn.cursor() as cur:
                for boat_id, records in buffers.items():
                    if not records:
                        continue
                    execute_values(
                        cur,
                        """
                        INSERT INTO telemetry_history
                            (boat_id, timestamp, lat, lon, heading, groundspeed,
                             battery_voltage, battery_current, battery_remaining,
                             flight_mode, armed, current_waypoint,
                             feed_level, cellular_csq, box_temperature)
                        VALUES %s
                        """,
                        [
                            (
                                boat_id,
                                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r[0])),
                                r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                                r[8], r[9], r[10], r[11], r[12], r[13],
                            )
                            for r in records
                        ],
                    )
                    total += len(records)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"[DbWriter] 写入失败: {e}", flush=True)
            # 重连
            try:
                self.conn.close()
            except Exception:
                pass
            self._connect()

    def flush(self):
        """强制刷新所有缓冲区"""
        self._flush_all()

    def close(self):
        self._running = False
        self._flush_all()
        if self.conn:
            self.conn.close()
