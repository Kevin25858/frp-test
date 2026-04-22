# FRP Monitor

基于 Python 的 FRP 隧道监控系统，支持 RTT 测量、端口探测、Web 面板和桌面 GUI。

## 功能特性

- **RTT 监控**: 通过 ping/pong 测量客户端到服务器的往返时间
- **丢包率统计**: 实时统计网络丢包率
- **端口探测**: 支持 TCP/UDP 端口探测
- **Web 面板**: 浏览器访问，实时图表展示
- **桌面 GUI**: PySimpleGUI 跨平台桌面应用
- **自动重连**: 客户端断线自动重连

## 快速开始

### 服务器模式

```bash
python -m cli.main server --port 8080 --http-port 8081
```

### 客户端模式

```bash
python -m cli.main client --server localhost:8080 --name my-client
```

### 端口探测

```bash
python -m cli.main client --probe --probe-server 8.8.8.8 --probe-port 53 --probe-proto udp
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用预构建的 EXE

从 GitHub Actions 下载:
- `frp-monitor.exe` - 主程序
- `frp-monitor-web.exe` - Web 面板

## Docker 部署

```bash
docker-compose up -d
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| FRP_MONITOR_PORT | 8080 | TCP 端口 |
| FRP_MONITOR_HTTP_PORT | 8081 | HTTP 端口 |
| FRP_MONITOR_SERVER | localhost:8080 | 服务器地址 |
| FRP_MONITOR_DB_PATH | frp-monitor.db | 数据库路径 |

## API 接口

- `GET /` - Web 界面
- `GET /api/health` - 健康检查
- `GET /api/clients` - 客户端列表
- `GET /api/clients/{name}` - 客户端详情
- `GET /api/metrics/{name}?hours=1` - 历史指标

## 技术栈

- Python 3.11+
- asyncio + aiohttp
- SQLite
- PySimpleGUI

## License

MIT
