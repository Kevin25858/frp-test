"""SQLite storage layer for FRP Monitor"""

import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple


@dataclass
class ClientRecord:
    id: int
    name: str
    addr: str
    connected_at: datetime
    last_seen: datetime
    status: str


@dataclass
class MetricRecord:
    id: int
    client_id: int
    rtt_ms: float
    loss_rate: float
    timestamp: datetime


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    addr TEXT NOT NULL,
                    connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'offline'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    rtt_ms REAL NOT NULL,
                    loss_rate REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_client_time
                ON metrics(client_id, timestamp)
            """)
            self.conn.commit()

    def close(self):
        with self.lock:
            self.conn.close()

    def save_client(self, name: str, addr: str) -> int:
        """Insert or update client, returns client_id"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO clients (name, addr, status, last_seen, connected_at)
                VALUES (?, ?, 'online', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    addr = excluded.addr,
                    status = 'online',
                    last_seen = CURRENT_TIMESTAMP
            """, (name, addr))
            self.conn.commit()
            cursor.execute("SELECT id FROM clients WHERE name = ?", (name,))
            row = cursor.fetchone()
            return row["id"] if row else 0

    def update_client_last_seen(self, name: str):
        """Update client's last_seen timestamp"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE clients SET last_seen = CURRENT_TIMESTAMP, status = 'online'
                WHERE name = ?
            """, (name,))
            self.conn.commit()

    def set_client_offline(self, name: str):
        """Mark client as offline"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE clients SET status = 'offline' WHERE name = ?
            """, (name,))
            self.conn.commit()

    def get_clients(self) -> List[ClientRecord]:
        """Get all clients ordered by id"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, name, addr, connected_at, last_seen, status
                FROM clients ORDER BY id
            """)
            rows = cursor.fetchall()
            return [
                ClientRecord(
                    id=row["id"],
                    name=row["name"],
                    addr=row["addr"],
                    connected_at=datetime.fromisoformat(row["connected_at"]),
                    last_seen=datetime.fromisoformat(row["last_seen"]),
                    status=row["status"],
                )
                for row in rows
            ]

    def get_client_by_name(self, name: str) -> Optional[ClientRecord]:
        """Get a client by name"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, name, addr, connected_at, last_seen, status
                FROM clients WHERE name = ?
            """, (name,))
            row = cursor.fetchone()
            if not row:
                return None
            return ClientRecord(
                id=row["id"],
                name=row["name"],
                addr=row["addr"],
                connected_at=datetime.fromisoformat(row["connected_at"]),
                last_seen=datetime.fromisoformat(row["last_seen"]),
                status=row["status"],
            )

    def save_metric(self, client_id: int, rtt_ms: float, loss_rate: float):
        """Save a metric record"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO metrics (client_id, rtt_ms, loss_rate)
                VALUES (?, ?, ?)
            """, (client_id, rtt_ms, loss_rate))
            self.conn.commit()

    def get_metrics(
        self, client_id: int, start: datetime, end: datetime
    ) -> List[MetricRecord]:
        """Get metrics for a client within a time range"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, client_id, rtt_ms, loss_rate, timestamp
                FROM metrics
                WHERE client_id = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (client_id, start.isoformat(), end.isoformat()))
            rows = cursor.fetchall()
            return [
                MetricRecord(
                    id=row["id"],
                    client_id=row["client_id"],
                    rtt_ms=row["rtt_ms"],
                    loss_rate=row["loss_rate"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
                for row in rows
            ]

    def get_latest_metric(self, client_id: int) -> Optional[MetricRecord]:
        """Get the most recent metric for a client"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, client_id, rtt_ms, loss_rate, timestamp
                FROM metrics
                WHERE client_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (client_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return MetricRecord(
                id=row["id"],
                client_id=row["client_id"],
                rtt_ms=row["rtt_ms"],
                loss_rate=row["loss_rate"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
