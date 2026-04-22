"""Standalone web dashboard for FRP Monitor - runs on port 38080"""

import asyncio
import json
import os
import sys
from aiohttp import web

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frp_monitor.client import Client


SERVERS_FILE = "servers.json"
HTTP_PORT = 38080


class WebDashboard:
    def __init__(self):
        self.servers = self._load_servers()
        self.probe_results = []

    def _load_servers(self):
        if os.path.exists(SERVERS_FILE):
            try:
                with open(SERVERS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_servers(self):
        with open(SERVERS_FILE, "w") as f:
            json.dump(self.servers, f, indent=2)

    async def handle_index(self, request: web.Request) -> web.Response:
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>FRP Monitor Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eaeaea; }
        h1 { color: #e94560; }
        .server { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .server.online { border-left: 4px solid #00d9ff; }
        .server.offline { border-left: 4px solid #ff4757; }
        .add-form { background: #0f3460; padding: 15px; margin: 20px 0; border-radius: 8px; }
        input { padding: 8px; margin: 5px; background: #16213e; border: 1px solid #2a2a4a; color: #eaeaea; }
        button { padding: 8px 16px; background: #e94560; border: none; color: white; cursor: pointer; border-radius: 4px; }
        button:hover { background: #ff6b8a; }
        .probe-result { margin-top: 10px; padding: 10px; background: #0f3460; border-radius: 4px; }
        .success { color: #00d9ff; }
        .error { color: #ff4757; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #2a2a4a; }
        th { background: #0f3460; }
    </style>
</head>
<body>
    <h1>FRP Monitor Dashboard</h1>

    <div class="add-form">
        <h3>添加服务器</h3>
        <form method="POST" action="/api/add">
            <input name="name" placeholder="名称" required>
            <input name="addr" placeholder="地址 (如 1.2.3.4)" required>
            <input name="port" placeholder="端口 (如 7000)" required>
            <input name="proto" placeholder="协议 (tcp/udp)" value="tcp" required>
            <button type="submit">添加</button>
        </form>
    </div>

    <h2>服务器列表</h2>
    <div id="servers">
        <table>
            <thead>
                <tr><th>名称</th><th>地址</th><th>状态</th><th>操作</th></tr>
            </thead>
            <tbody>
                {server_rows}
            </tbody>
        </table>
    </div>

    <h2>探测结果</h2>
    <div id="results">
        {probe_results}
    </div>

    <script>
        async function probe(name, addr, port, proto) {
            try {
                const response = await fetch(`/api/probe?name=${{name}}&addr=${{addr}}&port=${{port}}&proto=${{proto}}`);
                const data = await response.json();
                location.reload();
            } catch (e) {{
                alert('探测失败: ' + e);
            }}
        }
    </script>
</body>
</html>
        """
        server_rows = ""
        for s in self.servers:
            status = "offline"
            server_rows += f"""
                <tr>
                    <td>{s['name']}</td>
                    <td>{s['addr']}:{s['port']}</td>
                    <td class="{'success' if status == 'online' else 'error'}">{status}</td>
                    <td><button onclick="probe('{s['name']}', '{s['addr']}', '{s['port']}', '{s['proto']}')">探测</button></td>
                </tr>
            """
        if not self.servers:
            server_rows = "<tr><td colspan='4'>暂无服务器</td></tr>"

        probe_results = ""
        for r in self.probe_results[-10:]:
            cls = "success" if r["success"] else "error"
            probe_results += f"""
                <div class="probe-result {cls}">
                    <strong>{r['name']}</strong>: {r['addr']}:{r['port']} -
                    {r['result']}
                </div>
            """
        if not self.probe_results:
            probe_results = "<p>暂无探测结果</p>"

        return web.Response(
            text=html.format(server_rows=server_rows, probe_results=probe_results),
            content_type="text/html"
        )

    async def handle_add(self, request: web.Request) -> web.Response:
        data = await request.post()
        server = {
            "name": data.get("name"),
            "addr": data.get("addr"),
            "port": data.get("port"),
            "proto": data.get("proto", "tcp"),
        }
        self.servers.append(server)
        self._save_servers()
        raise web.HTTPFound("/")

    async def handle_probe(self, request: web.Request) -> web.Response:
        name = request.query.get("name")
        addr = request.query.get("addr")
        port = request.query.get("port")
        proto = request.query.get("proto", "tcp")
        server_addr = os.environ.get("FRP_MONITOR_SERVER", "localhost:8080")

        client = Client(server_addr, f"dashboard-{name}")
        await client.connect()

        result_text = "连接失败"
        success = False

        if client.connected:
            probe_result = await client.probe(addr, port, proto)
            if probe_result.success:
                result_text = f"RTT: {probe_result.rtt_ms:.2f} ms"
                success = True
            else:
                result_text = f"错误: {probe_result.error}"

        await client.stop()

        self.probe_results.append({
            "name": name,
            "addr": addr,
            "port": port,
            "result": result_text,
            "success": success,
        })

        return web.json_response({"success": success, "result": result_text})

    def run(self):
        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_post("/api/add", self.handle_add)
        app.router.add_get("/api/probe", self.handle_probe)

        print(f"Starting FRP Monitor web dashboard on port {HTTP_PORT}")
        web.run_app(app, host="0.0.0.0", port=HTTP_PORT)


if __name__ == "__main__":
    WebDashboard().run()
