# -*- coding: utf-8 -*-
"""
dn42.py —— DN42 网络专用辅助功能

包含：
- DN42 地址空间与 ASN 范围常量（来自 dn42.dev 官方文档）
- AS 路径解析与高亮
- whois 查询（DN42 registry）
- traceroute 执行
- DN42 IP/ASN 归属判定
"""
import re
import shlex
import subprocess
import ipaddress
import threading

import config

# 全局 Traceroute 锁，限制并发数为 1
_traceroute_lock = threading.Lock()


# ====================== DN42 网络常量 ======================
# ASN 范围：4242420000 - 4242429999（私有 ASN 段）
ASN_MIN = 4242420000
ASN_MAX = 4242429999

# DN42 主地址空间
IPv4_PREFIXES = [
    ("DN42 主网络", "172.20.0.0/14"),
    ("ChaosVPN", "172.31.0.0/16"),
    ("ChaosVPN", "10.100.0.0/14"),
    ("neoNetwork", "10.127.0.0/16"),
    ("Freifunk", "10.0.0.0/8"),
]
IPv6_PREFIXES = [
    ("DN42 ULA", "fd00::/8"),
    ("DN42 Anycast", "fd42:d42:d42::/48"),
]

# Anycast 保留地址（DN42 内常用服务）
ANYCAST_V4 = [
    ("DN42 DNS", "172.20.0.53"),
    ("DN42 Wiki(anycast)", "172.23.235.4"),
]
ANYCAST_V6 = [
    ("DN42 DNS", "fd42:d42:d42:53::1"),
]

# 编译为网络对象便于判定
_NETS_V4 = [ipaddress.ip_network(c) for _, c in IPv4_PREFIXES]
_NETS_V6 = [ipaddress.ip_network(c) for _, c in IPv6_PREFIXES]


def is_dn42_asn(asn) -> bool:
    try:
        n = int(asn)
        return ASN_MIN <= n <= ASN_MAX
    except (TypeError, ValueError):
        return False


def is_dn42_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    nets = _NETS_V4 if ip.version == 4 else _NETS_V6
    return any(ip in net for net in nets)


def dn42_info() -> dict:
    """返回 DN42 网络基本元信息，供前端展示。"""
    return {
        "asn_range": {"min": ASN_MIN, "max": ASN_MAX},
        "ipv4_prefixes": [{"name": n, "cidr": c} for n, c in IPv4_PREFIXES],
        "ipv6_prefixes": [{"name": n, "cidr": c} for n, c in IPv6_PREFIXES],
        "anycast_v4": [{"name": n, "ip": c} for n, c in ANYCAST_V4],
        "anycast_v6": [{"name": n, "ip": c} for n, c in ANYCAST_V6],
        "node": {"name": config.NODE_NAME, "asn": config.NODE_ASN},
        "site": config.SITE_NAME,
    }


# ====================== AS 路径解析 ======================
def parse_as_path(text: str) -> list:
    """从 'AS path: 4242420001 4242420002 4242420003' 提取 ASN 列表。"""
    m = re.search(r"AS path:\s*(.*)", text)
    if not m:
        return []
    return [a for a in re.findall(r"\d+", m.group(1))]


def parse_as_from_route_line(line: str) -> str:
    """从路由行的 [AS424242xxxxi] 提取 ASN。"""
    m = re.search(r"\[AS(\d+)", line)
    return m.group(1) if m else ""


def highlight_as_path(asns: list) -> list:
    """标注每个 ASN 是否为 DN42。"""
    return [{"asn": a, "dn42": is_dn42_asn(a)} for a in asns]


# ====================== whois 查询 ======================
def whois(query: str) -> dict:
    """对 DN42 registry 执行 whois 查询。"""
    if not config.WHOIS_BIN:
        return {"error": "whois 未配置", "raw": ""}
    query = query.strip()
    if not query:
        return {"error": "空查询", "raw": ""}
    # 仅允许字母数字及少量符号，防注入
    if not re.match(r"^[A-Za-z0-9_\-:./ ]{1,128}$", query):
        return {"error": "查询包含非法字符", "raw": ""}

    argv = [config.WHOIS_BIN, "-h", config.WHOIS_SERVER, query]
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=config.WHOIS_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        return {"error": f"找不到 whois 二进制 ({config.WHOIS_BIN})", "raw": ""}
    except subprocess.TimeoutExpired:
        return {"error": "whois 查询超时", "raw": ""}

    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0 and not out:
        return {"error": err.strip(), "raw": ""}
    return {"raw": out.strip(), "query": query}


# ====================== traceroute ======================
def traceroute(host: str) -> dict:
    """从本节点执行 traceroute。限制并发数为 1。"""
    if not config.TRACEROUTE_BIN:
        return {"error": "traceroute 未配置", "raw": ""}
    host = host.strip()
    if not host:
        return {"error": "空主机", "raw": ""}
    if not re.match(r"^[A-Za-z0-9.\-:]{1,253}$", host):
        return {"error": "主机名非法", "raw": ""}

    if not _traceroute_lock.acquire(blocking=False):
        return {"error": "当前有其他 traceroute 正在运行，请稍后再试", "raw": ""}
    
    try:
        argv = [
            config.TRACEROUTE_BIN,
            "-w", "2",            # 每跳等待秒数
            "-q", "1",            # 每跳探测次数（降低负载）
            "-m", str(config.TRACEROUTE_MAX_HOPS),
            host,
        ]
        try:
            proc = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=config.TRACEROUTE_TIMEOUT,
                check=False,
            )
        except FileNotFoundError:
            return {"error": f"找不到 traceroute 二进制 ({config.TRACEROUTE_BIN})", "raw": ""}
        except subprocess.TimeoutExpired:
            return {"error": "traceroute 超时", "raw": ""}

        out = proc.stdout.decode("utf-8", errors="replace")
        return {"raw": out.strip(), "hops": parse_traceroute(out), "target": host}
    finally:
        _traceroute_lock.release()


def parse_traceroute(text: str) -> list:
    """将 traceroute 输出解析为跳数列表。"""
    hops = []
    for line in text.splitlines():
        m = re.match(r"^\s*(\d+)\s+(.*)$", line)
        if m:
            hops.append({"hop": int(m.group(1)), "line": m.group(2).strip()})
    return hops
