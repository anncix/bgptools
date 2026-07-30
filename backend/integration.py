# -*- coding: utf-8 -*-
"""
integration.py —— DN42 接入集成模块

作为 config / bird / dn42 之间的中央集成层，提供：
1. bird2 连接健康检查与自动降级（demo ↔ real）
2. ROA 表管理与自动更新状态监控
3. WireGuard 隧道状态检测
4. 接入就绪度诊断（部署前自检）
5. 节点信息聚合（供 /api/integration/status 使用）

设计目标：
- 零外部依赖，纯标准库
- 适配 1C1G VPS，所有检测轻量化
- 安全优先：所有外部命令调用均带超时与输入校验
"""
import os
import re
import time
import shutil
import subprocess
import ipaddress
from typing import Optional

import config


# ====================== bird2 连接健康检查 ======================
def bird_health() -> dict:
    """检测 bird2 守护进程的连接状态。

    返回：
    - reachable: birdc 是否可执行且控制套接字可达
    - socket_exists: 套接字文件是否存在
    - binary_found: birdc 二进制是否在 PATH 中
    - version: birdc 版本号（如可获取）
    - error: 错误信息（如有）
    """
    result = {
        "reachable": False,
        "socket_exists": False,
        "binary_found": False,
        "version": None,
        "error": None,
    }

    # 检查 birdc 二进制
    bin_path = shutil.which(config.BIRDC_BIN)
    if not bin_path:
        # 尝试直接路径
        if os.path.isfile(config.BIRDC_BIN) and os.access(config.BIRDC_BIN, os.X_OK):
            bin_path = config.BIRDC_BIN
    if not bin_path:
        result["error"] = f"birdc 二进制未找到 ({config.BIRDC_BIN})"
        return result
    result["binary_found"] = True

    # 检查控制套接字
    if not os.path.exists(config.BIRD_SOCKET):
        result["error"] = f"BIRD 控制套接字不存在 ({config.BIRD_SOCKET})"
        return result
    result["socket_exists"] = True

    # 尝试执行 show status 确认连通性
    try:
        argv = [bin_path]
        if config.BIRD_RESTRICT:
            argv.append("-r")
        argv.extend(["-s", config.BIRD_SOCKET, "show status"])
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=min(config.BIRD_TIMEOUT, 5),
            check=False,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        if proc.returncode == 0 or out:
            result["reachable"] = True
            # 提取版本号
            m = re.search(r"BIRD\s+([\d.]+)", out)
            if m:
                result["version"] = m.group(1)
        else:
            err = proc.stderr.decode("utf-8", errors="replace")
            result["error"] = err.strip() or f"birdc 退出码 {proc.returncode}"
    except subprocess.TimeoutExpired:
        result["error"] = "birdc 连接超时（套接字可能无响应）"
    except Exception as e:
        result["error"] = f"birdc 连接异常: {e}"

    return result


# ====================== 模式自动降级 ======================
def should_use_demo() -> dict:
    """判断是否应使用演示模式。

    逻辑：
    1. 若 DEMO_MODE 已显式开启 → 直接返回 True
    2. 若 DEMO_MODE 关闭但 birdc 不可用 → 建议开启 demo 模式
    3. 若 DEMO_MODE 关闭且 birdc 可用 → 使用真实模式
    """
    health = bird_health()
    forced_demo = config.DEMO_MODE

    if forced_demo:
        return {
            "use_demo": True,
            "reason": "DEMO_MODE 已通过环境变量显式开启",
            "bird_health": health,
        }

    if not health["reachable"]:
        return {
            "use_demo": True,
            "reason": f"bird2 不可达（{health['error']}），建议设置 BGP_TOOL_DEMO_MODE=true 或安装 bird2",
            "bird_health": health,
            "auto_fallback": True,
        }

    return {
        "use_demo": False,
        "reason": "bird2 连接正常，使用真实路由数据",
        "bird_health": health,
    }


# ====================== ROA 表管理 ======================
def roa_status() -> dict:
    """检查 ROA 表的更新状态。

    检测：
    - ROA 配置文件是否存在
    - 文件最后修改时间（判断是否需要更新）
    - ROA 条目数量（best-effort）
    """
    roa_paths = {
        "ipv4": "/etc/bird/roa/dn42_roa_bird2_4.conf",
        "ipv6": "/etc/bird/roa/dn42_roa_bird2_6.conf",
    }
    # 也检查 setup.sh 中使用的路径
    alt_paths = {
        "ipv4": "/etc/bird/roa_dn42.conf",
    }

    result = {
        "v4": {"exists": False, "path": None, "entries": 0, "last_updated": None},
        "v6": {"exists": False, "path": None, "entries": 0, "last_updated": None},
        "update_command": _roa_update_command(),
    }

    for family in ("v4", "v6"):
        # 尝试主路径
        for path_key in ("ipv4", "ipv6"):
            if family != ("v4" if path_key == "ipv4" else "v6"):
                continue
            paths_to_check = [roa_paths.get(path_key, ""), alt_paths.get(path_key, "")]
            for p in paths_to_check:
                if p and os.path.exists(p):
                    entry = result[family]
                    entry["exists"] = True
                    entry["path"] = p
                    mtime = os.path.getmtime(p)
                    entry["last_updated"] = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(mtime)
                    )
                    # 统计条目数（每行一个 route 对象）
                    try:
                        with open(p, "r") as f:
                            entry["entries"] = sum(
                                1 for line in f if line.strip().startswith("route")
                            )
                    except Exception:
                        pass
                    break

    return result


def _roa_update_command() -> str:
    """返回 ROA 更新的 cron 命令字符串。"""
    return (
        '*/15 * * * * curl -sfSLR -o /etc/bird/roa/dn42_roa_bird2_4.conf '
        '-z /etc/bird/roa/dn42_roa_bird2_4.conf '
        'https://dn42.burble.com/roa/dn42_roa_bird2_4.conf && '
        'curl -sfSLR -o /etc/bird/roa/dn42_roa_bird2_6.conf '
        '-z /etc/bird/roa/dn42_roa_bird2_6.conf '
        'https://dn42.burble.com/roa/dn42_roa_bird2_6.conf && '
        'birdc configure'
    )


# ====================== WireGuard 隧道检测 ======================
def wireguard_status() -> dict:
    """检测 WireGuard 隧道状态（best-effort，不依赖 wg 命令时返回基本信息）。"""
    result = {
        "wg_available": False,
        "interfaces": [],
        "error": None,
    }

    wg_bin = shutil.which("wg")
    if not wg_bin:
        result["error"] = "wg 命令未安装（WireGuard 可能未配置）"
        return result

    result["wg_available"] = True

    try:
        proc = subprocess.run(
            [wg_bin, "show"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")
            result["error"] = err.strip() or "wg show 执行失败"
            return result

        # 解析 wg show 输出
        interfaces = []
        current = None
        for line in out.splitlines():
            if not line.startswith("\t") and not line.startswith("  "):
                # 接口名行
                if current:
                    interfaces.append(current)
                parts = line.strip().split()
                current = {
                    "name": parts[0] if parts else "",
                    "public_key": parts[1] if len(parts) > 1 else "",
                    "rx": 0,
                    "tx": 0,
                    "peers": 0,
                }
            elif current and "peer" in line.lower():
                current["peers"] += 1
            elif current:
                m = re.match(r"\s+(rx|tx):\s*(\d+)", line)
                if m:
                    current[m.group(1)] = int(m.group(2))
        if current:
            interfaces.append(current)
        result["interfaces"] = interfaces

    except subprocess.TimeoutExpired:
        result["error"] = "wg show 超时"
    except Exception as e:
        result["error"] = f"wg 检测异常: {e}"

    return result


# ====================== 接入就绪度诊断 ======================
def readiness_check() -> dict:
    """部署前自检：检查所有接入 DN42 所需的组件状态。

    返回各组件的就绪状态与建议操作。
    """
    checks = []

    # 1. bird2 检查
    bh = bird_health()
    checks.append({
        "component": "bird2",
        "status": "ok" if bh["reachable"] else ("warn" if bh["binary_found"] else "fail"),
        "detail": bh,
        "suggestion": "" if bh["reachable"] else "安装 bird2 并启动服务: apt install bird2 && systemctl start bird",
    })

    # 2. birdc 受限模式检查
    checks.append({
        "component": "birdc_restricted",
        "status": "ok" if config.BIRD_RESTRICT else "warn",
        "detail": {"restricted": config.BIRD_RESTRICT},
        "suggestion": "" if config.BIRD_RESTRICT else "建议开启受限模式 BGP_TOOL_BIRD_RESTRICT=true，仅允许 show 命令",
    })

    # 3. ROA 表检查
    roa = roa_status()
    roa_ok = roa["v4"]["exists"] or roa["v6"]["exists"]
    checks.append({
        "component": "roa_table",
        "status": "ok" if roa_ok else "warn",
        "detail": roa,
        "suggestion": "" if roa_ok else "配置 ROA 自动更新 cron: " + _roa_update_command(),
    })

    # 4. ASN 配置检查
    node_asn = str(config.NODE_ASN)
    asn_valid = node_asn.isdigit() and 4242420000 <= int(node_asn) <= 4242429999
    checks.append({
        "component": "node_asn",
        "status": "ok" if asn_valid else "fail",
        "detail": {"asn": node_asn, "valid_dn42": asn_valid},
        "suggestion": "" if asn_valid else "NODE_ASN 必须在 DN42 范围内 (4242420000-4242429999)",
    })

    # 5. MY_ASN 配置检查
    my_asn = str(getattr(config, "MY_ASN", ""))
    my_asn_valid = my_asn.isdigit() and 4242420000 <= int(my_asn) <= 4242429999
    checks.append({
        "component": "my_asn",
        "status": "ok" if my_asn_valid else "warn",
        "detail": {"my_asn": my_asn, "valid": my_asn_valid},
        "suggestion": "" if my_asn_valid else "设置 BGP_TOOL_MY_ASN 为你的 DN42 ASN，用于 AS Path 分析",
    })

    # 6. API Key 检查
    checks.append({
        "component": "api_key",
        "status": "ok" if config.API_KEY else "warn",
        "detail": {"configured": bool(config.API_KEY)},
        "suggestion": "" if config.API_KEY else "公网暴露务必设置 BGP_TOOL_API_KEY",
    })

    # 7. traceroute 检查
    tr_bin = shutil.which(config.TRACEROUTE_BIN) if config.TRACEROUTE_BIN else None
    checks.append({
        "component": "traceroute",
        "status": "ok" if tr_bin else "warn",
        "detail": {"binary": config.TRACEROUTE_BIN, "found": bool(tr_bin)},
        "suggestion": "" if tr_bin else "安装 traceroute: apt install traceroute",
    })

    # 8. whois 检查
    who_bin = shutil.which(config.WHOIS_BIN) if config.WHOIS_BIN else None
    checks.append({
        "component": "whois",
        "status": "ok" if who_bin else "warn",
        "detail": {"binary": config.WHOIS_BIN, "found": bool(who_bin)},
        "suggestion": "" if who_bin else "安装 whois: apt install whois",
    })

    # 9. WireGuard 检查
    wg = wireguard_status()
    checks.append({
        "component": "wireguard",
        "status": "ok" if wg["wg_available"] and wg["interfaces"] else ("warn" if wg["wg_available"] else "warn"),
        "detail": wg,
        "suggestion": "" if wg["interfaces"] else "配置 WireGuard 隧道连接 DN42 peer",
    })

    # 10. 演示模式检查
    checks.append({
        "component": "demo_mode",
        "status": "info",
        "detail": {"demo_mode": config.DEMO_MODE},
        "suggestion": "生产环境应关闭 DEMO_MODE 以使用真实 bird2 数据" if config.DEMO_MODE else "",
    })

    # 汇总
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    warn_count = sum(1 for c in checks if c["status"] == "warn")
    overall = "ready" if fail_count == 0 and warn_count == 0 else (
        "not_ready" if fail_count > 0 else "ready_with_warnings"
    )

    return {
        "overall": overall,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "checks": checks,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ====================== 节点信息聚合 ======================
def node_summary() -> dict:
    """聚合当前节点的接入状态信息，供 /api/integration/status 使用。"""
    mode = should_use_demo()
    roa = roa_status()

    return {
        "site_name": config.SITE_NAME,
        "node_name": config.NODE_NAME,
        "node_asn": config.NODE_ASN,
        "my_asn": getattr(config, "MY_ASN", config.NODE_ASN),
        "demo_mode": config.DEMO_MODE,
        "effective_mode": "demo" if mode["use_demo"] else "real",
        "mode_reason": mode["reason"],
        "bird_health": mode["bird_health"],
        "roa_status": roa,
        "bird_socket": config.BIRD_SOCKET,
        "bird_restricted": config.BIRD_RESTRICT,
        "cache_enabled": config.CACHE_ENABLED,
        "api_key_configured": bool(config.API_KEY),
    }
