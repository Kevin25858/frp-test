"""Server for FRP Monitor - TCP client accept, HTTP API, port probing"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

import aiohttp
from aiohttp import web

from .protocol import (
    Message,
    MessageType,
    new_ping,
    new_probe_result,
    read_message,
    write_message,
)
from .storage import Storage


@dataclass
class PingRecord:
    seq: int
    sent_at: int  # timestamp ms
    received: bool = False


@dataclass
class ClientConn:
    conn: asyncio.StreamReader
    writer: asyncio.StreamWriter
    name: str = ""
    addr: str = ""
    last_ping: int = 0
    last_pong: int = 0
    ping_seq: int = 0
    ping_history: List[PingRecord] = field(default_factory=list)
    client_id: int = 0
    rtt_ms: float = 0.0
    loss_rate: float = 0.0


class Server:
    def __init__(self, port: int = 8080, http_port: int = 8081, db_path: str = "frp-monitor.db"):
        self.port = port
        self.http_port = http_port
        self.storage = Storage(db_path)
        self.clients: Dict[str, ClientConn] = {}
        self.tcp_server: Optional[asyncio.Server] = None
        self.http_server: Optional[web.Application] = None
        self.http_runner: Optional[web.AppRunner] = None
        self._running = False

    async def start(self):
        """Start TCP and HTTP servers"""
        self._running = True

        # Start TCP server
        self.tcp_server = await asyncio.start_server(
            self._handle_connection, "0.0.0.0", self.port
        )

        # Start HTTP server
        self.http_runner = web.AppRunner(self._create_http_app())
        await self.http_runner.setup()
        site = web.TCPSite(self.http_runner, "0.0.0.0", self.http_port)
        await site.start()

    async def stop(self):
        """Graceful shutdown"""
        self._running = False

        if self.tcp_server:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()

        if self.http_runner:
            await self.http_runner.cleanup()

        for name in list(self.clients.keys()):
            await self._remove_client(name)

        self.storage.close()

    def _create_http_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/api/health", self._handle_health)
        app.router.add_get("/api/clients", self._handle_clients)
        app.router.add_get("/api/clients/{name}", self._handle_client_detail)
        app.router.add_get("/api/metrics/{name}", self._handle_metrics)
        return app

async def _handle_index(self, request: web.Request) -> web.Response:
        """Serve web UI"""
        import os
        import sys

        # Try multiple possible paths for bundled exe
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "web", "static", "index.html"),
            os.path.join(os.path.dirname(sys.executable), "frp_monitor", "web", "static", "index.html"),
            os.path.join(os.path.dirname(sys.executable), "web", "static", "index.html"),
            os.path.join(os.path.dirname(__file__), "..", "web", "static", "index.html"),
        ]

        for index_path in possible_paths:
            if os.path.exists(index_path):
                return web.FileResponse(index_path)

        return web.Response(text="FRP Monitor", content_type="text/html")

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _handle_clients(self, request: web.Request) -> web.Response:
        clients = []
        for name, conn in self.clients.items():
            latest = self.storage.get_latest_metric(conn.client_id)
            rtt = latest.rtt_ms if latest else 0.0
            loss = latest.loss_rate if latest else 0.0
            clients.append({
                "name": name,
                "addr": conn.addr,
                "status": "online",
                "rtt_ms": rtt,
                "loss_rate": loss,
            })
        # Add offline clients from DB
        for rec in self.storage.get_clients():
            if rec.name not in self.clients:
                latest = self.storage.get_latest_metric(rec.id)
                clients.append({
                    "name": rec.name,
                    "addr": rec.addr,
                    "status": rec.status,
                    "rtt_ms": latest.rtt_ms if latest else 0.0,
                    "loss_rate": latest.loss_rate if latest else 0.0,
                })
        return web.json_response(clients)

    async def _handle_client_detail(self, request: web.Request) -> web.Response:
        name = request.match_info["name"]
        if name in self.clients:
            conn = self.clients[name]
            return web.json_response({
                "name": name,
                "addr": conn.addr,
                "status": "online",
                "rtt_ms": conn.rtt_ms,
                "loss_rate": conn.loss_rate,
            })
        client = self.storage.get_client_by_name(name)
        if client:
            latest = self.storage.get_latest_metric(client.id)
            return web.json_response({
                "name": name,
                "addr": client.addr,
                "status": client.status,
                "rtt_ms": latest.rtt_ms if latest else 0.0,
                "loss_rate": latest.loss_rate if latest else 0.0,
            })
        return web.json_response({"error": "not found"}, status=404)

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        name = request.match_info["name"]
        hours = int(request.query.get("hours", 1))
        client = self.storage.get_client_by_name(name)
        if not client:
            return web.json_response({"error": "not found"}, status=404)
        end = datetime.now()
        start = end - timedelta(hours=hours)
        metrics = self.storage.get_metrics(client.id, start, end)
        return web.json_response([
            {"rtt_ms": m.rtt_ms, "loss_rate": m.loss_rate, "timestamp": m.timestamp.isoformat()}
            for m in metrics
        ])

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        client = ClientConn(conn=reader, writer=writer, addr=f"{addr[0]}:{addr[1]}")

        try:
            # Wait for register
            registered = await self._wait_for_register(client)
            if not registered:
                writer.close()
                await writer.wait_closed()
                return

            # Add client
            self.clients[client.name] = client
            client.client_id = self.storage.save_client(client.name, client.addr)

            # Start client loops
            asyncio.create_task(self._read_loop(client))
            asyncio.create_task(self._ping_loop(client))
            asyncio.create_task(self._heartbeat_loop(client))

        except Exception:
            pass
        finally:
            if client.name in self.clients:
                await self._remove_client(client.name)
            writer.close()
            await writer.wait_closed()

    async def _wait_for_register(self, client: ClientConn) -> bool:
        """Wait up to 10s for register message"""
        try:
            msg = await asyncio.wait_for(read_message(client.conn), timeout=10.0)
            if msg and msg.type == MessageType.REGISTER.value:
                client.name = msg.data if isinstance(msg.data, str) else str(msg.data)
                return True
        except asyncio.TimeoutError:
            pass
        return False

    async def _read_loop(self, client: ClientConn):
        """Read messages from client"""
        while self._running and client.name in self.clients:
            try:
                msg = await asyncio.wait_for(read_message(client.conn), timeout=5.0)
                if msg is None:
                    break
                await self._handle_message(client, msg)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    async def _handle_message(self, client: ClientConn, msg: Message):
        """Route messages by type"""
        if msg.type == MessageType.PONG.value:
            await self._handle_pong(client, msg)
        elif msg.type == MessageType.HEARTBEAT.value:
            self.storage.update_client_last_seen(client.name)
        elif msg.type == MessageType.PROBE_START.value:
            await self._handle_probe_start(client, msg)

    async def _handle_pong(self, client: ClientConn, msg: Message):
        """Record pong and calculate RTT"""
        client.last_pong = int(time.time() * 1000)
        rtt = client.last_pong - msg.timestamp

        # Update ping history
        for record in client.ping_history:
            if record.seq == msg.seq and not record.received:
                record.received = True
                client.rtt_ms = rtt
                break

        await self._save_metrics(client)

    async def _handle_probe_start(self, client: ClientConn, msg: Message):
        """Handle probe request"""
        probe_req = msg.get_probe_request()
        if not probe_req:
            return

        success, rtt_ms, err = await self._do_probe(
            probe_req.server_addr,
            probe_req.server_port,
            probe_req.protocol,
        )
        result = new_probe_result(success, rtt_ms, err)
        await write_message(client.writer, result)

    async def _do_probe(self, addr: str, port: str, proto: str) -> tuple:
        """Perform TCP/UDP probe with 5s timeout"""
        start = time.time()
        try:
            if proto == "udp":
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(addr, int(port)),
                    timeout=5.0
                )
                writer.close()
                await writer.wait_closed()
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(addr, int(port)),
                    timeout=5.0
                )
                writer.close()
                await reader.read()
                await writer.wait_closed()
            rtt = (time.time() - start) * 1000
            return True, rtt, ""
        except asyncio.TimeoutError:
            return False, 0, "timeout"
        except Exception as e:
            return False, 0, str(e)

    async def _ping_loop(self, client: ClientConn):
        """Send ping every 5 seconds"""
        while self._running and client.name in self.clients:
            await asyncio.sleep(5)
            if client.name not in self.clients:
                break
            await self._send_ping(client)
            await self._save_metrics(client)

    async def _send_ping(self, client: ClientConn):
        """Create and send ping"""
        client.ping_seq += 1
        record = PingRecord(seq=client.ping_seq, sent_at=int(time.time() * 1000))
        client.ping_history.append(record)
        if len(client.ping_history) > 10:
            client.ping_history.pop(0)

        msg = new_ping(client.ping_seq)
        try:
            await write_message(client.writer, msg)
            client.last_ping = int(time.time() * 1000)
        except Exception:
            pass

    async def _heartbeat_loop(self, client: ClientConn):
        """Check if client is dead (>30s inactivity)"""
        while self._running and client.name in self.clients:
            await asyncio.sleep(10)
            if client.name not in self.clients:
                break
            if self._is_client_dead(client):
                await self._remove_client(client.name)
                break

    def _is_client_dead(self, client: ClientConn) -> bool:
        """Check if no activity for 30 seconds"""
        now = int(time.time() * 1000)
        last_activity = max(client.last_ping, client.last_pong)
        return (now - last_activity) > 30000

    async def _save_metrics(self, client: ClientConn):
        """Calculate loss rate and persist to DB"""
        if not client.ping_history:
            return

        total = len(client.ping_history)
        lost = sum(1 for r in client.ping_history if not r.received)
        loss_rate = lost / total if total > 0 else 0.0

        self.storage.save_metric(client.client_id, client.rtt_ms, loss_rate)

    async def _remove_client(self, name: str):
        """Remove client and update DB"""
        if name in self.clients:
            self.storage.set_client_offline(name)
            del self.clients[name]

    def get_clients(self) -> List[Dict[str, Any]]:
        """Get all clients"""
        return [
            {
                "name": name,
                "addr": conn.addr,
                "status": "online",
                "rtt_ms": conn.rtt_ms,
                "loss_rate": conn.loss_rate,
            }
            for name, conn in self.clients.items()
        ]

    def get_client(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific client"""
        if name in self.clients:
            conn = self.clients[name]
            return {
                "name": name,
                "addr": conn.addr,
                "status": "online",
                "rtt_ms": conn.rtt_ms,
                "loss_rate": conn.loss_rate,
            }
        return None

    def get_metrics(self, name: str, hours: int = 1) -> List[Dict[str, Any]]:
        """Get metrics for a client"""
        client = self.storage.get_client_by_name(name)
        if not client:
            return []
        end = datetime.now()
        start = end - timedelta(hours=hours)
        metrics = self.storage.get_metrics(client.id, start, end)
        return [
            {"rtt_ms": m.rtt_ms, "loss_rate": m.loss_rate, "timestamp": m.timestamp.isoformat()}
            for m in metrics
        ]
