"""FRP Monitor - 自动启动服务器并打开浏览器"""

import sys
import os
import webbrowser
import threading
import time
import argparse

sys.path.insert(0, os.getcwd())

from frp_monitor.server import Server


def open_browser(port=8081, delay=2):
    """延迟后打开浏览器"""
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")


async def run_server(port=8080, http_port=8081, db_path="frp-monitor.db"):
    """运行服务器"""
    server = Server(port=port, http_port=http_port, db_path=db_path)
    await server.start()
    print(f"服务器已启动，访问 http://localhost:{http_port}")
    return server


def main():
    import asyncio

    # 检查参数
    if len(sys.argv) > 1:
        # 有参数，导入 cli.main 处理
        from cli.main import main as cli_main
        cli_main()
        return

    # 无参数，自动启动服务器并打开浏览器
    print("启动 FRP Monitor 服务器...")

    # 在后台线程打开浏览器
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # 运行服务器
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    main()
