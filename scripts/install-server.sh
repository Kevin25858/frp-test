#!/bin/bash
# FRP Monitor 一键安装脚本 - 服务端
# 使用方法: curl -sL https://raw.githubusercontent.com/Kevin25858/frp-test/main/install-server.sh | bash

set -e

# 配置
INSTALL_DIR="/opt/frp-monitor"
BINARY_NAME="frp-monitor"
REPO_OWNER="Kevin25858"
REPO_NAME="frp-test"
RELEASE_FILE="frp-monitor"

echo "=== FRP Monitor 安装脚本 ==="
echo "安装目录: $INSTALL_DIR"

# 检测架构
ARCH=$(uname -m)
case $ARCH in
    x86_64) ARTIFACT="${RELEASE_FILE}-linux-amd64" ;;
    aarch64) ARTIFACT="${RELEASE_FILE}-linux-arm64" ;;
    armv7l) ARTIFACT="${RELEASE_FILE}-linux-armv7" ;;
    *) echo "不支持的架构: $ARCH"; exit 1 ;;
esac

echo "架构: $ARCH"

# 创建目录
sudo mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 下载最新版本
LATEST_VERSION=$(curl -sL "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest" | grep -o '"tag_name": "[^"]*"' | cut -d'"' -f4)
echo "版本: $LATEST_VERSION"

URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${LATEST_VERSION}/${ARTIFACT}"
echo "下载: $URL"

curl -sL "$URL" -o "$BINARY_NAME"
chmod +x "$BINARY_NAME"

# 创建数据目录
mkdir -p data

# 创建 systemd 服务
cat > frp-monitor.service << 'EOF'
[Unit]
Description=FRP Monitor Service
After=network.target

[Service]
Type=simple
ExecStart=/opt/frp-monitor/frp-monitor server --port 8400 --http-port 8401 --db data/frp-monitor.db
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 安装 systemd 服务
sudo cp frp-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable frp-monitor
sudo systemctl restart frp-monitor

echo ""
echo "=== 安装完成 ==="
echo "服务状态: sudo systemctl status frp-monitor"
echo "日志: sudo journalctl -u frp-monitor -f"
echo "监控端连接地址: $(hostname -I | awk '{print $1}'):8400"
echo "接下来只需要在监控端里填写 FRP 实际映射到的内网地址和端口"
