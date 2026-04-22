"""FRP Monitor - 启动服务器并打开浏览器"""

import sys
import os
import webbrowser
import threading
import time

sys.path.insert(0, os.getcwd())

from cli.main import main


def open_browser_after_delay(port=8081, delay=2):
    """延迟后打开浏览器"""
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")


def run_with_browser():
    """启动服务器并自动打开浏览器"""
    # 在后台线程打开浏览器
    browser_thread = threading.Thread(target=open_browser_after_delay, daemon=True)
    browser_thread.start()
    # 运行主程序
    main()


if __name__ == "__main__":
    run_with_browser()
