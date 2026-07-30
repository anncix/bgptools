# -*- coding: utf-8 -*-
"""
bird.py —— BIRD2 守护进程交互层

职责：
1. 通过 `birdc -r`（受限模式）执行白名单内的 show 命令，获取原始文本输出。
2. 对输出做结构化解析（protocols / route / status / memory）。
3. 提供带 TTL 的内存缓存，降低 birdc 调用频次与系统负载（适配 1C1G）。
4. 当 birdc 不可用且开启 DEMO_MODE 时，返回逼真的模拟数据。

安全要点：
- 仅执行命令白名单中的命令；任何写操作（configure/restart/disable...）一律拒绝。
- 对用户输入做格式校验（IP / 前缀 / 协议名），防止命令注入。
- 所有子进程调用都带超时，避免阻塞。
"""
import re
import time
import shlex
import subprocess
import ipaddress
import threading
from typing import Optional

import config


# ====================== 缓存实现 ======================
class TTLCache:
    """极简线程安全的 TTL 内存缓存，零外部依赖。"""

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: int):
        if not config.CACHE_ENABLED or ttl <= 0:
            return None
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            value, expire_at = item
            if time.time() > expire_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value, ttl: int):
        if not config.CACHE_ENABLED or ttl <= 0:
            return
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def clear(self):
        with self._lock:
            self._store.clear()


cache = TTLCache()


# ====================== BIRD 客户端 ======================
class BirdError(Exception):
    pass


class BirdClient:
    """封装与 birdc 的交互与解析。"""

    def __init__(self):
        self.bin = config.BIRDC_BIN
        self.socket = config.BIRD_SOCKET
        self.restrict = config.BIRD_RESTRICT
        self.timeout = config.BIRD_TIMEOUT

    # ---------- 底层执行 ----------
    def _run(self, command: str, timeout: Optional[float] = None) -> str:
        """执行一条 birdc 命令，返回原始输出文本。"""
        command = command.strip()
        if not command:
            raise BirdError("空命令")
        if not self._is_allowed(command):
            raise BirdError(f"命令被安全策略拒绝: {command}")

        # 构造命令行：birdc [-r] -s <socket> "<command>"
        argv = [self.bin]
        if self.restrict:
            argv.append("-r")
        argv.extend(["-s", self.socket, command])

        try:
            proc = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout or self.timeout,
                check=False,
            )
        except FileNotFoundError:
            raise BirdError(
                f"找不到 birdc 二进制 ({self.bin})，请确认已安装 bird2 或调整 BGP_TOOL_BIRDC_BIN"
            )
        except subprocess.TimeoutExpired:
            raise BirdError(f"birdc 执行超时（>{self.timeout}s）")

        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0 and not out:
            # 部分 birdc 版本非 0 退出但仍有 stdout，优先看 stdout
            raise BirdError(err.strip() or f"birdc 退出码 {proc.returncode}")

        # 去掉 BIRD 的提示行（首行 "BIRD x.x.x ready."）与尾部的提示符
        return self._strip_banner(out)

    @staticmethod
    def _strip_banner(text: str) -> str:
        lines = text.splitlines()
        cleaned = []
        for ln in lines:
            s = ln.strip()
            # 跳过版本横幅与空提示行
            if re.match(r"^BIRD [\d.]+ ready\.?\s*$", s):
                continue
            if s == "":
                continue
            cleaned.append(ln)
        return "\n".join(cleaned).strip()

    # ---------- 命令白名单校验 ----------
    def _is_allowed(self, command: str) -> bool:
        # 拒绝包含分号、换行、管道等元字符的命令（防止命令注入）
        if re.search(r'[;\n\r|`$&><]', command):
            return False
        low = command.lower().strip()
        # 绝对禁止的写/控制命令
        forbidden = [
            "configure", "restart", "disable", "enable", "reload",
            "shutdown", "exit", "quit", "dump", "eval", "add", "delete",
            "flush", "graceful", "mrtdump",
        ]
        first_word = low.split()[0] if low.split() else ""
        if first_word in forbidden:
            return False
        for allowed in config.ALLOWED_COMMANDS:
            if low.startswith(allowed):
                return True
        return False

    # ---------- 输入校验 ----------
    @staticmethod
    def valid_ip_or_prefix(value: str) -> bool:
        value = value.strip()
        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def valid_protocol_name(name: str) -> bool:
        # BIRD 协议名仅允许字母数字下划线连字符，长度受限
        return bool(re.match(r"^[A-Za-z0-9_\-]{1,64}$", name))

    @staticmethod
    def valid_host(host: str) -> bool:
        host = host.strip()
        if BirdClient.valid_ip_or_prefix(host):
            return True
        # 域名/主机名
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,253}$", host):
            return True
        return False

    # ====================== 高层 API（带缓存） ======================
    def status(self) -> dict:
        raw = self._cached("show status", config.CACHE_TTL_STATUS,
                           lambda: self._run("show status"))
        return {"raw": raw, "parsed": parse_status(raw)}

    def memory(self) -> dict:
        raw = self._cached("show memory", config.CACHE_TTL_MEMORY,
                           lambda: self._run("show memory"))
        return {"raw": raw, "parsed": parse_memory(raw)}

    def protocols(self, name: str = "") -> dict:
        cmd = "show protocols" + (f" all {name}" if name else "")
        ttl = config.CACHE_TTL_PROTOCOLS
        raw = self._cached(cmd, ttl, lambda: self._run(cmd))
        result = {"raw": raw, "parsed": parse_protocols(raw)}
        if name:
            result["parsed"] = parse_protocol_detail(raw, name)
        return result

    def routes(self, protocol: str = "", family: str = "all",
               count_only: bool = False, primary: bool = False,
               all_details: bool = False) -> dict:
        parts = ["show route"]
        if family == "4":
            parts.append("where net.type = NET_IP4")
        elif family == "6":
            parts.append("where net.type = NET_IP6")
        if primary:
            parts.append("primary")
        if protocol:
            parts.append(f"protocol {protocol}")
        if all_details:
            parts.append("all")
        if count_only:
            parts.append("count")
        cmd = " ".join(parts)
        raw = self._cached(cmd, config.CACHE_TTL_ROUTES,
                           lambda: self._run(cmd))
        return {"raw": raw, "parsed": parse_routes(raw, count_only)}

    def route_lookup(self, target: str) -> dict:
        if not self.valid_ip_or_prefix(target):
            raise BirdError(f"非法的 IP 或前缀: {target}")
        cmd = f"show route for {target}"
        raw = self._cached(cmd, config.CACHE_TTL_LOOKUP,
                           lambda: self._run(cmd))
        return {"raw": raw, "parsed": parse_routes(raw), "target": target}

    def roa_check(self, prefix: str) -> dict:
        if not self.valid_ip_or_prefix(prefix):
            raise BirdError(f"非法的前缀: {prefix}")
        cmd = f"show route for {prefix}"
        raw = self._cached(cmd, config.CACHE_TTL_LOOKUP,
                           lambda: self._run(cmd))
        return {"raw": raw, "parsed": parse_routes(raw), "prefix": prefix}

    # ---------- 缓存装饰 ----------
    def _cached(self, key: str, ttl: int, producer):
        hit = cache.get(key, ttl)
        if hit is not None:
            return hit
        value = producer()
        cache.set(key, value, ttl)
        return value


# ====================== 解析器 ======================
def parse_status(raw: str) -> dict:
    """解析 show status 输出为结构化字段。

    bird2 的 `show status` 典型输出（含时间，内部含冒号，不能简单按冒号切分）：
        Router ID is 172.20.0.1
        Hostname node1
        Current server time is 2026-07-30 12:00:00
        Last reboot on 2026-07-28 09:12:33
        Last reconfiguration on 2026-07-30 11:00:00
        Daemon is up and running
    因此用关键字前缀正则提取，而非冒号分割。
    """
    info = {}
    patterns = {
        "router_id": r"Router ID is\s+(.+)",
        "hostname": r"Hostname\s+(.+)",
        "current_server_time": r"Current server time is\s+(.+)",
        "last_reboot": r"Last reboot on\s+(.+)",
        "last_reconfiguration": r"Last reconfiguration on\s+(.+)",
        "status": r"Daemon is\s+(.+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, raw)
        if m:
            info[key] = m.group(1).strip()
    # 兜底：仍把形如 "Key: Value"（无内部冒号）的行也收录
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z][\w ]*?):\s*(.+)$", line)
        if m:
            k = m.group(1).strip().lower().replace(" ", "_")
            info.setdefault(k, m.group(2).strip())
    return info


def parse_memory(raw: str) -> dict:
    """解析 show memory 输出。"""
    tables = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        tables.append({"line": line.strip(), "tokens": parts})
    return {"tables": tables}


def parse_protocols(raw: str) -> list:
    """解析 show protocols 表格为 peer 列表。"""
    peers = []
    lines = raw.splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if line.lower().startswith("name") and "proto" in line.lower():
            header_idx = i
            break
    if header_idx < 0:
        # 没有表头时整体返回
        for line in lines:
            if line.strip():
                peers.append({"raw": line.strip()})
        return peers

    start = header_idx + 1
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        peer = {
            "name": parts[0],
            "proto": parts[1],
            "table": parts[2],
            "state": parts[3],
            "since": parts[4],
            "info": parts[5] if len(parts) > 5 else "",
        }
        # BGP 会话状态判定
        peer["established"] = "Established" in peer["info"]
        peer["bgp"] = peer["proto"].upper() == "BGP"
        peers.append(peer)
    return peers


def parse_protocol_detail(raw: str, name: str) -> dict:
    """解析 show protocols all <name> 的详细输出。"""
    detail = {"name": name, "sections": {}}
    current = "general"
    buffer = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        # Channel / BGP 等小节标题通常顶格且无冒号
        if re.match(r"^\s*(Channel|BGP|Timers|Description|Route|Output|Input)", line):
            if buffer:
                detail["sections"][current] = "\n".join(buffer)
            current = line.strip().rstrip(":")
            buffer = []
        else:
            buffer.append(line)
    if buffer:
        detail["sections"][current] = "\n".join(buffer)
    # 提取关键统计
    text = raw
    m = re.search(r"Routes:\s*([0-9]+)\s+imported,\s*([0-9]+)\s+exported", text)
    if m:
        detail["imported"] = int(m.group(1))
        detail["exported"] = int(m.group(2))
    return detail


def parse_routes(raw: str, count_only: bool = False) -> dict:
    """解析 show route 输出为路由条目列表。"""
    if count_only:
        m = re.search(r"(\d+)\s+routes", raw)
        return {"count": int(m.group(1)) if m else None, "raw": raw}

    routes = []
    # 主条目行：前缀 + 类型 + [来源 时间] + 优先级 + [AS信息]
    main_re = re.compile(
        r"^(\S+)\s+"                       # 前缀
        r"(unicast|blackhole|unreachable|prohibit)\s+"  # 类型
        r"\[([^\]]+)\]\s*"                 # [协议 时间]
        r"(\*?)\s*"                        # 是否首选
        r"\((\d+)\)"                       # 优先级
        r"(?:\s*\[([^\]]*)\])?"            # 可选 [AS信息]
    )
    current = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        m = main_re.match(line.strip())
        if m:
            prefix, rtype, source, star, metric, asinfo = m.groups()
            current = {
                "prefix": prefix,
                "type": rtype,
                "source": source.strip(),
                "preferred": bool(star),
                "metric": metric,
                "as_info": asinfo.strip() if asinfo else "",
                "as_path": [],
                "roa": "unknown",
                "nexthops": [],
            }
            # 主行可能内联下一跳
            routes.append(current)
        else:
            # 缩进行：下一跳 / BGP 属性
            if current is not None:
                stripped = line.strip()
                if stripped.startswith("via ") or stripped.startswith("dev "):
                    current["nexthops"].append(stripped)
                # 提取 ROA 校验结果（优先检查，因为 BGP.roa 行也含 "BGP."）
                # 格式: "BGP.roa: VALID" 或 "ROA: valid"
                elif "roa" in stripped.lower():
                    current["as_path_line"] = current.get("as_path_line", "")
                    roa_match = re.search(r'roa[:\s]+(\w+)', stripped, re.IGNORECASE)
                    if roa_match:
                        roa_val = roa_match.group(1).lower()
                        if roa_val in ("valid", "invalid", "unknown"):
                            current["roa"] = roa_val
                # 从 BGP.as_path 行提取 AS 号
                elif "as_path" in stripped.lower() or ("BGP." in stripped and "path" in stripped.lower()):
                    current["as_path_line"] = stripped
                    # 格式: "BGP.as_path: 4242422601 4242420666"
                    path_match = re.search(r'(?:BGP\.as_path|AS path):\s*(.+)', stripped, re.IGNORECASE)
                    if path_match:
                        asns = re.findall(r'\d+', path_match.group(1))
                        if asns and not current.get("as_info"):
                            current["as_info"] = " ".join(f"AS{a}" for a in asns) + " i"
                        # 同时存储解析后的 AS Path 列表
                        current["as_path"] = asns
    return {"routes": routes, "count": len(routes)}


# 全局单例
bird = BirdClient()
