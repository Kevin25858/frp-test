"""Desktop GUI for FRP Monitor using PySimpleGUI"""

import asyncio
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import PySimpleGUI as sg
except ImportError:
    print("PySimpleGUI not installed. Run: pip install PySimpleGUI")
    sys.exit(1)

from frp_monitor.client import Client
from frp_monitor.protocol import ProbeResult


SERVERS_FILE = "servers.json"
REFRESH_INTERVAL = 5  # seconds


class DesktopApp:
    def __init__(self):
        self.servers = self._load_servers()
        self.probe_results = {}
        self.loop = None
        self.running = True

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

    async def _probe_async(self, name: str, addr: str, port: str, proto: str) -> ProbeResult:
        server_addr = os.environ.get("FRP_MONITOR_SERVER", "localhost:8080")
        client = Client(server_addr, f"desktop-{name}")
        await client.connect()
        if client.connected:
            result = await client.probe(addr, port, proto)
            await client.stop()
            return result
        await client.stop()
        return ProbeResult(success=False, rtt_ms=0, error="connection failed")

    def _probe_worker(self, name: str, addr: str, port: str, proto: str):
        """Run probe in async context"""
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        try:
            result = self.loop.run_until_complete(self._probe_async(name, addr, port, proto))
            self.probe_results[name] = result
        except Exception as e:
            self.probe_results[name] = ProbeResult(success=False, rtt_ms=0, error=str(e))

    def _probe_all(self):
        """Run all probes in parallel threads"""
        self.probe_results = {}
        threads = []
        for server in self.servers:
            t = threading.Thread(target=self._probe_worker, args=(
                server["name"],
                server["addr"],
                server["port"],
                server["proto"],
            ))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    def _build_window(self):
        sg.theme("DarkBlue13")

        server_rows = []
        for i, s in enumerate(self.servers):
            result = self.probe_results.get(s["name"])
            status = "Unknown"
            rtt = "-"
            if result:
                if result.success:
                    status = "OK"
                    rtt = f"{result.rtt_ms:.1f} ms"
                else:
                    status = f"Error: {result.error}"
            server_rows.append([str(i), s["name"], f"{s['addr']}:{s['port']}", s["proto"], status, rtt])

        col_layout = [
            [sg.Text("FRP Monitor Desktop", font=("Helvetica", 16))],
            [sg.Text(f"Monitor Server: {os.environ.get('FRP_MONITOR_SERVER', 'localhost:8080')}")],
            [sg.Button("Refresh All", key="refresh"), sg.Button("Add Server", key="add")],
            [sg.HorizontalSeparator()],
            [sg.Text("Servers:", font=("Helvetica", 12))],
            [
                sg.Table(
                    headings=["#", "Name", "Address", "Proto", "Status", "RTT"],
                    values=server_rows,
                    key="server_table",
                    auto_size_columns=True,
                    num_rows=min(10, max(5, len(server_rows))),
                )
            ],
            [sg.Button("Probe Selected", key="probe"), sg.Button("Remove Selected", key="remove")],
        ]

        layout = [
            [sg.Column(col_layout, size=(600, 400), scrollable=True)],
        ]

        return sg.Window("FRP Monitor", layout, finalize=True)

    def run(self):
        window = self._build_window()

        # Initial probe
        self._probe_all()

        while self.running:
            event, values = window.read(timeout=100)

            if event in (sg.WIN_CLOSED, "Exit"):
                self.running = False
                break

            elif event == "refresh":
                self._probe_all()
                window.close()
                window = self._build_window()

            elif event == "probe":
                if values.get("server_table") and len(values["server_table"]) > 0:
                    idx = values["server_table"][0]
                    if idx < len(self.servers):
                        server = self.servers[idx]
                        t = threading.Thread(target=self._probe_worker, args=(
                            server["name"], server["addr"], server["port"], server["proto"]
                        ))
                        t.start()
                        t.join()
                        window.close()
                        window = self._build_window()

            elif event == "remove":
                if values.get("server_table") and len(values["server_table"]) > 0:
                    idx = values["server_table"][0]
                    if idx < len(self.servers):
                        self.servers.pop(idx)
                        self._save_servers()
                        window.close()
                        window = self._build_window()

            elif event == "add":
                add_window = sg.Window("Add Server", [
                    [sg.Text("Name:"), sg.Input(key="name")],
                    [sg.Text("Address:"), sg.Input(key="addr")],
                    [sg.Text("Port:"), sg.Input(key="port")],
                    [sg.Text("Protocol:"), sg.Combo(["tcp", "udp"], key="proto", default_value="tcp")],
                    [sg.Button("Add"), sg.Button("Cancel")],
                ], modal=True)

                ev, vals = add_window.read()
                add_window.close()

                if ev == "Add" and vals["name"] and vals["addr"] and vals["port"]:
                    self.servers.append({
                        "name": vals["name"],
                        "addr": vals["addr"],
                        "port": vals["port"],
                        "proto": vals["proto"],
                    })
                    self._save_servers()
                    window.close()
                    window = self._build_window()

        window.close()


if __name__ == "__main__":
    DesktopApp().run()
