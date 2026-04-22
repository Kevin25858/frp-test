"""CLI entry point for FRP Monitor - server and client subcommands"""

import argparse
import asyncio
import os
import signal
import sys
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frp_monitor.server import Server
from frp_monitor.client import Client


def get_env(key: str, default: str) -> str:
    return os.environ.get(key, default)


async def run_server(args):
    """Run the FRP Monitor server"""
    port = int(os.environ.get("FRP_MONITOR_PORT", args.port))
    http_port = int(os.environ.get("FRP_MONITOR_HTTP_PORT", args.http_port))
    db_path = os.environ.get("FRP_MONITOR_DB_PATH", args.db)

    print(f"Starting FRP Monitor server...")
    print(f"  TCP port: {port}")
    print(f"  HTTP port: {http_port}")
    print(f"  Database: {db_path}")

    server = Server(port=port, http_port=http_port, db_path=db_path)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await server.start()
        print("Server started successfully")
        await stop_event.wait()
    finally:
        await server.stop()
        print("Server stopped")


async def run_client(args):
    """Run the FRP Monitor client"""
    server_addr = os.environ.get("FRP_MONITOR_SERVER", args.server)
    name = args.name or f"client-{os.getpid()}"

    print(f"Starting FRP Monitor client...")
    print(f"  Server: {server_addr}")
    print(f"  Name: {name}")

    client = Client(server_addr=server_addr, name=name)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    if args.probe:
        # One-shot probe mode
        await client.connect()
        if client.connected:
            print(f"Probing {args.probe_server}:{args.probe_port} ({args.probe_proto})...")
            result = await client.probe(args.probe_server, args.probe_port, args.probe_proto)
            if result.success:
                print(f"Success! RTT: {result.rtt_ms:.2f} ms")
            else:
                print(f"Failed: {result.error}")
        else:
            print("Failed to connect to server")
        await client.stop()
        return

    try:
        await client.run()
    except asyncio.CancelledError:
        pass
    finally:
        await client.stop()
        print("Client stopped")


def main():
    parser = argparse.ArgumentParser(description="FRP Monitor")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Server subcommand
    server_parser = subparsers.add_parser("server", help="Run as server")
    server_parser.add_argument("--port", default="8080", help="TCP port (default: 8080)")
    server_parser.add_argument("--http-port", default="8081", help="HTTP port (default: 8081)")
    server_parser.add_argument("--db", default="frp-monitor.db", help="Database path")

    # Client subcommand
    client_parser = subparsers.add_parser("client", help="Run as client")
    client_parser.add_argument("--server", default="localhost:8080", help="Server address")
    client_parser.add_argument("--name", help="Client name (default: client-{pid})")
    client_parser.add_argument("--probe", action="store_true", help="One-shot probe mode")
    client_parser.add_argument("--probe-server", help="Server to probe (for probe mode)")
    client_parser.add_argument("--probe-port", help="Port to probe (for probe mode)")
    client_parser.add_argument("--probe-proto", default="tcp", help="Protocol (tcp/udp)")

    args = parser.parse_args()

    if args.command == "server":
        asyncio.run(run_server(args))
    elif args.command == "client":
        asyncio.run(run_client(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
