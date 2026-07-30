#!/usr/bin/env bash
# DN42 BGP Tool 一键安装脚本（Debian/Ubuntu）
# 用法: sudo bash deploy/setup.sh
set -euo pipefail

INSTALL_DIR="/opt/bgp-tool"
SERVICE_USER="bgptool"

echo "[1/7] 安装系统依赖 (bird2, python3, traceroute, whois, nginx)..."
apt-get update -qq
apt-get install -y -qq bird2 python3 python3-venv python3-pip traceroute whois nginx

echo "[2/7] 创建服务用户 ${SERVICE_USER}..."
if ! id -u "${SERVICE_USER}" &>/dev/null; then
    useradd -r -s /usr/sbin/nologin -d "${INSTALL_DIR}" "${SERVICE_USER}"
fi
# 加入 bird 组，使其能访问控制套接字（视发行版而定）
if getent group bird >/dev/null; then
    usermod -aG bird "${SERVICE_USER}" || true
fi

echo "[3/7] 部署代码到 ${INSTALL_DIR}..."
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${INSTALL_DIR}"
rsync -a --delete --exclude='venv' --exclude='__pycache__' \
    "${SRC_DIR}/" "${INSTALL_DIR}/"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

echo "[4/7] 创建 Python 虚拟环境并安装依赖..."
sudo -u "${SERVICE_USER}" bash -c "
    python3 -m venv ${INSTALL_DIR}/venv
    ${INSTALL_DIR}/venv/bin/pip install --quiet --upgrade pip
    ${INSTALL_DIR}/venv/bin/pip install --quiet -r ${INSTALL_DIR}/requirements.txt
"

echo "[5/7] 安装 systemd 服务..."
cp "${INSTALL_DIR}/deploy/bgp-tool.service" /etc/systemd/system/
systemctl daemon-reload

echo "[6/7] 配置日志目录..."
mkdir -p /var/log/bird
chown bird:bird /var/log/bird 2>/dev/null || true

echo "[7/7] 完成！"
cat <<EOF

────────────────────────────────────────────
 安装完成。下一步：
 1. 编辑 bird 配置：
      sudo cp ${INSTALL_DIR}/deploy/bird.conf.example /etc/bird/bird.conf
      sudo nano /etc/bird/bird.conf        # 修改 ASN / IP / peer
 2. 修改服务环境变量（站点名、ASN、API Key）：
      sudo systemctl edit bgp-tool
 3. 启动服务：
      sudo systemctl enable --now bird
      sudo systemctl enable --now bgp-tool
 4. （可选）配置 nginx 反代 + HTTPS：
      sudo cp ${INSTALL_DIR}/deploy/nginx.conf /etc/nginx/sites-available/bgp-tool.conf
      sudo ln -s /etc/nginx/sites-available/bgp-tool.conf /etc/nginx/sites-enabled/
      sudo nginx -t && sudo systemctl reload nginx
 5. 访问 http://127.0.0.1:8421  或  https://lg.your-node.dn42

 提示：首次若无 bird，可先开启演示模式体验前端：
      在 systemd 覆盖文件中设 BGP_TOOL_DEMO_MODE=true 后 restart
────────────────────────────────────────────
EOF
