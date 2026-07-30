# -*- coding: utf-8 -*-
"""
bgp-tool 配置文件
所有配置均可通过环境变量覆盖，便于容器化与 systemd 部署。
"""
import os

# ---------- 基本服务配置 ----------
# 监听地址，0.0.0.0 表示对外开放；建议绑定 127.0.0.1 后用 nginx 反代
HOST = os.environ.get("BGP_TOOL_HOST", "127.0.0.1")
PORT = int(os.environ.get("BGP_TOOL_PORT", "8421"))
# 访问该工具需要的 API Key（留空则不启用鉴权；公网暴露务必设置）
API_KEY = os.environ.get("BGP_TOOL_API_KEY", "")
# 站点名称（展示在页面顶部）
SITE_NAME = os.environ.get("BGP_TOOL_SITE_NAME", "DN42 BGP Looking Glass")
# 当前节点 ASN / 节点名（仅展示用）
NODE_NAME = os.environ.get("BGP_TOOL_NODE_NAME", "node1")
NODE_ASN = os.environ.get("BGP_TOOL_NODE_ASN", "4242420000")

# ---------- BIRD 守护进程配置 ----------
# birdc 二进制路径
BIRDC_BIN = os.environ.get("BGP_TOOL_BIRDC_BIN", "birdc")
# BIRD 控制套接字路径
BIRD_SOCKET = os.environ.get("BGP_TOOL_BIRD_SOCKET", "/run/bird/bird.ctl")
# 是否以受限模式运行（强烈建议保持 True，仅允许 show 类命令）
BIRD_RESTRICT = os.environ.get("BGP_TOOL_BIRD_RESTRICT", "true").lower() in (
    "1", "true", "yes", "on",
)
# birdc 执行超时（秒）
BIRD_TIMEOUT = float(os.environ.get("BGP_TOOL_BIRD_TIMEOUT", "15"))
# 演示模式：当 birdc 不可用时返回模拟数据，便于本地开发/体验
DEMO_MODE = os.environ.get("BGP_TOOL_DEMO_MODE", "false").lower() in (
    "1", "true", "yes", "on",
)

# ---------- 缓存配置（降低 birdc 与系统负载）----------
CACHE_ENABLED = os.environ.get("BGP_TOOL_CACHE", "true").lower() in (
    "1", "true", "yes", "on",
)
# 各命令默认缓存时间（秒）
CACHE_TTL_STATUS = int(os.environ.get("BGP_TOOL_CACHE_TTL_STATUS", "5"))
CACHE_TTL_PROTOCOLS = int(os.environ.get("BGP_TOOL_CACHE_TTL_PROTOCOLS", "10"))
CACHE_TTL_ROUTES = int(os.environ.get("BGP_TOOL_CACHE_TTL_ROUTES", "15"))
CACHE_TTL_LOOKUP = int(os.environ.get("BGP_TOOL_CACHE_TTL_LOOKUP", "5"))
CACHE_TTL_MEMORY = int(os.environ.get("BGP_TOOL_CACHE_TTL_MEMORY", "15"))

# ---------- 外部工具配置 ----------
# traceroute 二进制路径（留空则禁用 traceroute 功能）
TRACEROUTE_BIN = os.environ.get("BGP_TOOL_TRACEROUTE_BIN", "traceroute")
TRACEROUTE_MAX_HOPS = int(os.environ.get("BGP_TOOL_TRACEROUTE_MAX_HOPS", "15"))
TRACEROUTE_TIMEOUT = float(os.environ.get("BGP_TOOL_TRACEROUTE_TIMEOUT", "15"))
# whois 二进制路径（留空则禁用 whois 功能）
WHOIS_BIN = os.environ.get("BGP_TOOL_WHOIS_BIN", "whois")
# DN42 whois 服务器
WHOIS_SERVER = os.environ.get("BGP_TOOL_WHOIS_SERVER", "whois.dn42.us")
WHOIS_TIMEOUT = float(os.environ.get("BGP_TOOL_WHOIS_TIMEOUT", "10"))

# ---------- 安全配置 ----------
# 单 IP 每分钟最大请求数（0 表示不限制）
RATE_LIMIT = int(os.environ.get("BGP_TOOL_RATE_LIMIT", "60"))
# 仅允许执行的 birdc 命令前缀（白名单）
ALLOWED_COMMANDS = [
    "show status",
    "show protocols",
    "show route",
    "show memory",
    "show symbols",
    "show roa",
    "show bfd",
    "show route for",
    "show route protocol",
    "show route export",
    "show route count",
    "show route primary",
    "show route where",
    "show route all",
]
