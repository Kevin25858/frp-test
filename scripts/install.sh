#!/bin/bash
#
# FRP Monitor 安装脚本
# 用法: curl -sSL https://example.com/install.sh | bash
#       curl -sSL https://example.com/install.sh | bash -s -- -v v1.0.0 -d /opt/frp-monitor
#

set -e

# 默认配置
VERSION="latest"
INSTALL_DIR="/usr/local/bin"
DATA_DIR="/var/lib/frp-monitor"
CONFIG_DIR="/etc/frp-monitor"
GITHUB_REPO="yourusername/frp-monitor"
SERVICE_USER="frp-monitor"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
FRP Monitor 安装脚本

用法:
  curl -sSL https://example.com/install.sh | bash
  bash install.sh [选项]

选项:
  -v, --version <版本>    指定安装版本 (默认: latest)
  -d, --dir <目录>        指定安装目录 (默认: /usr/local/bin)
  -h, --help              显示此帮助信息

示例:
  # 安装最新版本
  curl -sSL https://example.com/install.sh | bash

  # 安装指定版本
  curl -sSL https://example.com/install.sh | bash -s -- -v v1.0.0

  # 指定安装目录
  curl -sSL https://example.com/install.sh | bash -s -- -d /opt/frp-monitor

EOF
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -d|--dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检测操作系统
detect_os() {
    local os=""
    case "$(uname -s)" in
        Linux*)     os="linux";;
        Darwin*)    os="darwin";;
        CYGWIN*|MINGW*|MSYS*) os="windows";;
        *)
            log_error "不支持的操作系统: $(uname -s)"
            exit 1
            ;;
    esac
    echo "$os"
}

# 检测架构
detect_arch() {
    local arch=""
    case "$(uname -m)" in
        x86_64|amd64)   arch="amd64";;
        aarch64|arm64)  arch="arm64";;
        armv7l)         arch="arm";;
        i386|i686)      arch="386";;
        *)
            log_error "不支持的架构: $(uname -m)"
            exit 1
            ;;
    esac
    echo "$arch"
}

# 检查命令是否存在
check_command() {
    command -v "$1" >/dev/null 2>&1
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    if ! check_command curl && ! check_command wget; then
        log_error "需要 curl 或 wget 来下载文件"
        exit 1
    fi

    if [[ "$OS" == "linux" ]]; then
        if ! check_command systemctl; then
            log_warn "未检测到 systemd，将不会创建系统服务"
        fi
    fi
}

# 下载文件
download_file() {
    local url="$1"
    local output="$2"

    if check_command curl; then
        curl -fsSL -o "$output" "$url"
    else
        wget -q -O "$output" "$url"
    fi
}

# 获取最新版本号
get_latest_version() {
    local api_url="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"
    local version=""

    if check_command curl; then
        version=$(curl -fsSL "$api_url" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    else
        version=$(wget -qO- "$api_url" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    fi

    if [[ -z "$version" ]]; then
        log_error "无法获取最新版本号"
        exit 1
    fi

    echo "$version"
}

# 下载二进制文件
download_binary() {
    local version="$1"
    local os="$2"
    local arch="$3"

    if [[ "$version" == "latest" ]]; then
        version=$(get_latest_version)
        log_info "最新版本: $version"
    fi

    local binary_name="frp-monitor-${os}-${arch}"
    if [[ "$os" == "windows" ]]; then
        binary_name="${binary_name}.exe"
    fi

    local download_url="https://github.com/${GITHUB_REPO}/releases/download/${version}/${binary_name}"
    local temp_file="/tmp/${binary_name}"

    log_info "下载 ${binary_name}..."
    log_info "下载地址: ${download_url}"

    if ! download_file "$download_url" "$temp_file"; then
        log_error "下载失败，请检查版本号和网络连接"
        exit 1
    fi

    echo "$temp_file"
}

# 安装二进制文件
install_binary() {
    local source="$1"
    local dest="${INSTALL_DIR}/frp-monitor"

    log_info "安装 frp-monitor 到 ${INSTALL_DIR}..."

    # 创建安装目录
    if [[ ! -d "$INSTALL_DIR" ]]; then
        mkdir -p "$INSTALL_DIR"
    fi

    # 移动并设置权限
    mv "$source" "$dest"
    chmod +x "$dest"

    log_info "安装完成: $dest"
}

# 创建用户和目录
create_user_and_dirs() {
    log_info "创建用户和目录..."

    # 创建系统用户
    if ! id "$SERVICE_USER" &>/dev/null; then
        if [[ "$OS" == "linux" ]]; then
            useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER" 2>/dev/null || \
            useradd --system --no-create-home --shell /sbin/nologin "$SERVICE_USER" 2>/dev/null || true
        elif [[ "$OS" == "darwin" ]]; then
            sysadminctl -addUser "$SERVICE_USER" 2>/dev/null || true
        fi
    fi

    # 创建数据目录
    mkdir -p "$DATA_DIR"
    mkdir -p "$CONFIG_DIR"

    # 设置权限
    if id "$SERVICE_USER" &>/dev/null; then
        chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
    fi
}

# 创建 systemd 服务文件 (Linux)
create_systemd_service() {
    if [[ "$OS" != "linux" ]]; then
        return 0
    fi

    if ! check_command systemctl; then
        log_warn "跳过创建 systemd 服务"
        return 0
    fi

    log_info "创建 systemd 服务..."

    local service_file="/etc/systemd/system/frp-monitor.service"

    cat > "$service_file" << EOF
[Unit]
Description=FRP Monitor Service
Documentation=https://github.com/${GITHUB_REPO}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
ExecStart=${INSTALL_DIR}/frp-monitor server
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=frp-monitor
WorkingDirectory=${DATA_DIR}

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${DATA_DIR}

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载 systemd
    systemctl daemon-reload

    log_info "systemd 服务已创建: $service_file"
}

# 创建 Launchd 服务文件 (macOS)
create_launchd_service() {
    if [[ "$OS" != "darwin" ]]; then
        return 0
    fi

    log_info "创建 Launchd 服务..."

    local plist_file="/Library/LaunchDaemons/com.frp-monitor.server.plist"

    cat > "$plist_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.frp-monitor.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_DIR}/frp-monitor</string>
        <string>server</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${DATA_DIR}/frp-monitor.log</string>
    <key>StandardErrorPath</key>
    <string>${DATA_DIR}/frp-monitor.error.log</string>
    <key>WorkingDirectory</key>
    <string>${DATA_DIR}</string>
    <key>UserName</key>
    <string>root</string>
</dict>
</plist>
EOF

    # 加载服务
    launchctl load "$plist_file" 2>/dev/null || true

    log_info "Launchd 服务已创建: $plist_file"
}

# 启动服务
start_service() {
    log_info "启动服务..."

    if [[ "$OS" == "linux" ]] && check_command systemctl; then
        systemctl enable frp-monitor.service
        systemctl start frp-monitor.service

        # 检查服务状态
        sleep 2
        if systemctl is-active --quiet frp-monitor.service; then
            log_info "服务已成功启动"
        else
            log_warn "服务启动可能失败，请检查日志: journalctl -u frp-monitor -f"
        fi
    elif [[ "$OS" == "darwin" ]]; then
        launchctl start com.frp-monitor.server 2>/dev/null || true
        log_info "服务已启动"
    else
        log_warn "请手动启动服务"
    fi
}

# 显示安装信息
show_install_info() {
    echo ""
    echo "========================================"
    echo "  FRP Monitor 安装完成!"
    echo "========================================"
    echo ""
    echo "安装路径: ${INSTALL_DIR}/frp-monitor"
    echo "数据目录: ${DATA_DIR}"
    echo "配置目录: ${CONFIG_DIR}"
    echo ""

    if [[ "$OS" == "linux" ]] && check_command systemctl; then
        echo "服务管理命令:"
        echo "  查看状态: sudo systemctl status frp-monitor"
        echo "  启动服务: sudo systemctl start frp-monitor"
        echo "  停止服务: sudo systemctl stop frp-monitor"
        echo "  重启服务: sudo systemctl restart frp-monitor"
        echo "  查看日志: sudo journalctl -u frp-monitor -f"
    elif [[ "$OS" == "darwin" ]]; then
        echo "服务管理命令:"
        echo "  启动服务: sudo launchctl start com.frp-monitor.server"
        echo "  停止服务: sudo launchctl stop com.frp-monitor.server"
        echo "  查看日志: tail -f ${DATA_DIR}/frp-monitor.log"
    fi

    echo ""
    echo "使用说明:"
    echo "  frp-monitor --help"
    echo "  frp-monitor server     # 启动服务端"
    echo "  frp-monitor client     # 启动客户端"
    echo ""
    echo "访问地址:"
    echo "  TCP 端口: 8400"
    echo "  HTTP 端口: 8401"
    echo ""
    echo "========================================"
}

# 主函数
main() {
    echo "========================================"
    echo "  FRP Monitor 安装脚本"
    echo "========================================"
    echo ""

    # 检测系统信息
    OS=$(detect_os)
    ARCH=$(detect_arch)

    log_info "检测到操作系统: $OS"
    log_info "检测到架构: $ARCH"
    log_info "安装版本: $VERSION"
    log_info "安装目录: $INSTALL_DIR"

    # 检查是否为 root 用户 (Linux/macOS 安装服务需要)
    if [[ "$OS" != "windows" && $EUID -ne 0 ]]; then
        log_warn "建议使用 root 权限运行此脚本以创建系统服务"
        log_warn "或使用: curl -sSL https://example.com/install.sh | sudo bash"
    fi

    # 检查依赖
    check_dependencies

    # 下载并安装
    TEMP_FILE=$(download_binary "$VERSION" "$OS" "$ARCH")
    install_binary "$TEMP_FILE"

    # 创建用户和目录
    create_user_and_dirs

    # 创建服务文件
    create_systemd_service
    create_launchd_service

    # 启动服务
    if [[ $EUID -eq 0 ]]; then
        start_service
    fi

    # 显示安装信息
    show_install_info

    # 清理临时文件
    rm -f "$TEMP_FILE"
}

# 运行主函数
main
