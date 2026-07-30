# -*- coding: utf-8 -*-
"""
admin.py —— DN42 BGP Tool 后台管理系统

参考 autopeer 项目的设计理念，为 bgptool 提供完整的后台管理能力：
1. 管理员认证（Session + 密码哈希）
2. BGP 会话管理（查看/启用/禁用/重启 peer）
3. ROA 管理（状态监控 + 手动更新触发 + 更新历史）
4. 配置管理（运行时配置查看与覆盖）
5. API Key 管理（签发/吊销/列表）
6. 审计日志（所有管理操作记录）
7. 系统监控（CPU/内存/网络/BIRD 状态 + 历史快照）
8. 缓存管理（统计/清除/ TTL 调整）

设计约束：
- 使用 SQLite（stdlib sqlite3），零外部依赖，适配 1C1G
- 管理员写操作通过独立通道执行（绕过 bird.py 只读限制），但带完整审计
- 后台路由挂载在 /admin/api/* 下，与公共 API 隔离
"""
import os
import re
import time
import json
import sqlite3
import secrets
import hashlib
import threading
import subprocess
import shutil
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional

from flask import Blueprint, request, jsonify, session, g

import config

# ====================== 常量 ======================
ADMIN_BP = Blueprint("admin", __name__, url_prefix="/admin/api")

_DB_LOCK = threading.Lock()
_METRICS_THREAD = None
_METRICS_STOP = threading.Event()

# 不需要鉴权的路由白名单
_PUBLIC_ROUTES = {"/admin/api/login", "/admin/api/session"}


# ====================== 数据库层 ======================
def _db_path() -> str:
    """返回 SQLite 数据库文件路径。"""
    return getattr(config, "ADMIN_DB_PATH", "/opt/bgp-tool/data/admin.db")


def _get_db() -> sqlite3.Connection:
    """获取线程局部 SQLite 连接（WAL 模式，支持并发读）。"""
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构（幂等）。"""
    os.makedirs(os.path.dirname(_db_path()), exist_ok=True)
    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role        TEXT DEFAULT 'admin',
                    created_at  TEXT DEFAULT (datetime('now')),
                    last_login  TEXT
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    key         TEXT UNIQUE NOT NULL,
                    name        TEXT DEFAULT '',
                    created_at  TEXT DEFAULT (datetime('now')),
                    last_used   TEXT,
                    revoked     INTEGER DEFAULT 0,
                    created_by  TEXT DEFAULT 'system'
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT DEFAULT (datetime('now')),
                    username    TEXT DEFAULT 'system',
                    action      TEXT NOT NULL,
                    target      TEXT DEFAULT '',
                    detail      TEXT DEFAULT '',
                    ip_address  TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS metrics_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT DEFAULT (datetime('now')),
                    cpu_percent REAL DEFAULT 0,
                    memory_percent REAL DEFAULT 0,
                    memory_used_mb REAL DEFAULT 0,
                    routes_count INTEGER DEFAULT 0,
                    peers_count INTEGER DEFAULT 0,
                    peers_established INTEGER DEFAULT 0,
                    bird_reachable INTEGER DEFAULT 0,
                    net_rx_bytes INTEGER DEFAULT 0,
                    net_tx_bytes INTEGER DEFAULT 0,
                    disk_percent REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS roa_updates (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT DEFAULT (datetime('now')),
                    status      TEXT DEFAULT 'unknown',
                    entries_v4  INTEGER DEFAULT 0,
                    entries_v6  INTEGER DEFAULT 0,
                    triggered_by TEXT DEFAULT 'cron',
                    error_msg   TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS config_overrides (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    key         TEXT UNIQUE NOT NULL,
                    value       TEXT NOT NULL,
                    value_type  TEXT DEFAULT 'string',
                    updated_at  TEXT DEFAULT (datetime('now')),
                    updated_by  TEXT DEFAULT 'system'
                );
            """)
            conn.commit()

            # 创建默认管理员账号（首次初始化）
            cur = conn.execute("SELECT COUNT(*) FROM admin_users")
            if cur.fetchone()[0] == 0:
                default_user = getattr(config, "ADMIN_USERNAME", "admin")
                default_pass = getattr(config, "ADMIN_PASSWORD", "changeme")
                pw_hash = _hash_password(default_pass)
                conn.execute(
                    "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, 'superadmin')",
                    (default_user, pw_hash),
                )
                conn.commit()
        finally:
            conn.close()


def _hash_password(password: str) -> str:
    """使用 PBKDF2 + 随机盐哈希密码。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return f"pbkdf2:sha256${salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """验证密码是否匹配存储的哈希。"""
    try:
        if stored.startswith("pbkdf2:sha256$"):
            # 格式: pbkdf2:sha256${salt_hex}${dk_hex}
            parts = stored.split("$")
            salt = bytes.fromhex(parts[1])
            dk = bytes.fromhex(parts[2])
            return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000) == dk
        # 兼容 werkzeug 格式（万一）
        from werkzeug.security import check_password_hash
        return check_password_hash(stored, password)
    except Exception:
        return False


def _audit_log(username: str, action: str, target: str = "", detail: str = "", ip: str = ""):
    """记录审计日志。"""
    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute(
                "INSERT INTO audit_logs (username, action, target, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
                (username, action, target, detail, ip),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()


# ====================== 认证中间件 ======================
@ADMIN_BP.before_request
def _check_auth():
    """管理员鉴权：排除公开路由，其余要求登录。"""
    if request.path in _PUBLIC_ROUTES:
        return None

    # 检查 session 中的管理员身份
    if not session.get("admin_user"):
        return jsonify({"error": "未登录或会话已过期"}), 401

    g.admin_user = session["admin_user"]
    return None


def require_superadmin(fn):
    """装饰器：仅超级管理员可访问。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("admin_role") != "superadmin":
            return jsonify({"error": "需要超级管理员权限"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ====================== 系统监控 ======================
def _read_proc_stat() -> dict:
    """读取 /proc/stat 获取 CPU 时间。"""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()[1:]
        return {
            "user": int(parts[0]), "nice": int(parts[1]),
            "system": int(parts[2]), "idle": int(parts[3]),
            "iowait": int(parts[4]) if len(parts) > 4 else 0,
            "total": sum(int(x) for x in parts),
        }
    except Exception:
        return {}


def _read_meminfo() -> dict:
    """读取 /proc/meminfo 获取内存信息。"""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", info.get("MemFree", 0))
        used = total - available
        return {
            "total_mb": round(total / 1024, 1),
            "used_mb": round(used / 1024, 1),
            "percent": round(used / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        return {"total_mb": 0, "used_mb": 0, "percent": 0}


def _read_disk_usage(path: str = "/") -> dict:
    """获取磁盘使用率。"""
    try:
        stat = os.statvfs(path)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        return {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "percent": round(used / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}


def _read_net_dev() -> dict:
    """读取 /proc/net/dev 获取网络流量。"""
    try:
        rx_total = 0
        tx_total = 0
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" not in line:
                    continue
                iface = line.split(":")[0].strip()
                if iface in ("lo",):
                    continue
                parts = line.split(":")[1].split()
                rx_total += int(parts[0])
                tx_total += int(parts[8])
        return {"rx_bytes": rx_total, "tx_bytes": tx_total}
    except Exception:
        return {"rx_bytes": 0, "tx_bytes": 0}


def _get_uptime() -> str:
    """获取系统运行时间。"""
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        m = int((secs % 3600) // 60)
        return f"{d}d {h}h {m}m"
    except Exception:
        return "unknown"


def collect_metrics() -> dict:
    """采集当前系统指标快照。"""
    from backend import integration

    mem = _read_meminfo()
    disk = _read_disk_usage()
    net = _read_net_dev()
    bird_health = integration.bird_health()

    # 获取 peer 和 route 计数
    peers_count = 0
    peers_established = 0
    routes_count = 0
    try:
        from backend import bird as bird_mod
        protos = bird_mod.bird.protocols()
        parsed = protos.get("parsed", [])
        if isinstance(parsed, list):
            peers_count = len(parsed)
            peers_established = sum(1 for p in parsed if p.get("established"))
    except Exception:
        pass
    try:
        from backend import bird as bird_mod
        routes_data = bird_mod.bird.routes(count_only=True)
        routes_count = (routes_data.get("parsed") or {}).get("count", 0)
    except Exception:
        pass

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": _get_cpu_percent(),
        "memory": mem,
        "disk": disk,
        "network": net,
        "uptime": _get_uptime(),
        "bird_reachable": bird_health.get("reachable", False),
        "bird_version": bird_health.get("version"),
        "peers_count": peers_count,
        "peers_established": peers_established,
        "routes_count": routes_count,
    }


_prev_cpu = {"total": 0, "idle": 0}


def _get_cpu_percent() -> float:
    """计算 CPU 使用率（基于两次采样的差值）。"""
    global _prev_cpu
    stat = _read_proc_stat()
    if not stat:
        return 0.0
    total_diff = stat["total"] - _prev_cpu["total"]
    idle_diff = stat["idle"] - _prev_cpu["idle"]
    _prev_cpu = {"total": stat["total"], "idle": stat["idle"]}
    if total_diff <= 0:
        return 0.0
    return round((1 - idle_diff / total_diff) * 100, 1)


def _save_metrics_snapshot():
    """采集并保存指标快照到数据库。"""
    m = collect_metrics()
    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute("""
                INSERT INTO metrics_history
                (cpu_percent, memory_percent, memory_used_mb, routes_count,
                 peers_count, peers_established, bird_reachable,
                 net_rx_bytes, net_tx_bytes, disk_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m["cpu_percent"],
                m["memory"]["percent"],
                m["memory"]["used_mb"],
                m["routes_count"],
                m["peers_count"],
                m["peers_established"],
                1 if m["bird_reachable"] else 0,
                m["network"]["rx_bytes"],
                m["network"]["tx_bytes"],
                m["disk"]["percent"],
            ))
            # 保留最近 7 天的数据
            conn.execute(
                "DELETE FROM metrics_history WHERE timestamp < datetime('now', '-7 days')"
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()


def start_metrics_collector(interval: int = 60):
    """启动后台指标采集线程。"""
    global _METRICS_THREAD
    if _METRICS_THREAD and _METRICS_THREAD.is_alive():
        return

    _METRICS_STOP.clear()

    def _loop():
        while not _METRICS_STOP.wait(interval):
            try:
                _save_metrics_snapshot()
            except Exception:
                pass

    _METRICS_THREAD = threading.Thread(target=_loop, daemon=True, name="metrics-collector")
    _METRICS_THREAD.start()


def stop_metrics_collector():
    """停止指标采集线程。"""
    _METRICS_STOP.set()


# ====================== BGP 会话管理（安全写操作） ======================
def _safe_birdc_exec(command: str, timeout: int = 15) -> dict:
    """安全执行 birdc 写命令（绕过 bird.py 只读限制，但记录审计）。

    仅允许 enable/disable/restart/configure 命令，且严格校验协议名。
    """
    command = command.strip()
    # 仅允许特定命令
    allowed_prefixes = ("enable ", "disable ", "restart ", "configure")
    if not any(command.startswith(p) for p in allowed_prefixes):
        return {"ok": False, "error": f"命令不在允许范围: {command}"}

    # 协议名校验
    for prefix in ("enable ", "disable ", "restart "):
        if command.startswith(prefix):
            proto = command[len(prefix):].strip()
            if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", proto):
                return {"ok": False, "error": f"非法协议名: {proto}"}

    bin_path = shutil.which(config.BIRDC_BIN) or config.BIRDC_BIN
    argv = [bin_path]
    if config.BIRD_RESTRICT:
        argv.append("-r")  # 受限模式无法执行写操作，需要去掉
    # 写操作需要非受限模式
    argv = [bin_path, "-s", config.BIRD_SOCKET, command]

    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")
        if proc.returncode == 0:
            return {"ok": True, "output": out.strip()}
        return {"ok": False, "error": err.strip() or out.strip() or f"退出码 {proc.returncode}"}
    except FileNotFoundError:
        return {"ok": False, "error": f"birdc 未找到 ({bin_path})"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "birdc 执行超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _trigger_roa_update() -> dict:
    """触发 ROA 数据手动更新。"""
    roa_dir = "/etc/bird/roa"
    urls = {
        "v4": ("https://dn42.burble.com/roa/dn42_roa_bird2_4.conf",
               f"{roa_dir}/dn42_roa_bird2_4.conf"),
        "v6": ("https://dn42.burble.com/roa/dn42_roa_bird2_6.conf",
               f"{roa_dir}/dn42_roa_bird2_6.conf"),
    }

    result = {"v4": {"ok": False, "entries": 0}, "v6": {"ok": False, "entries": 0}}

    for family, (url, path) in urls.items():
        try:
            proc = subprocess.run(
                ["curl", "-sfSLR", "-o", path, "-z", path, url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            if proc.returncode == 0 and os.path.exists(path):
                count = sum(1 for line in open(path) if line.strip().startswith("route"))
                result[family] = {"ok": True, "entries": count}
            else:
                err = proc.stderr.decode("utf-8", errors="replace")
                result[family] = {"ok": False, "entries": 0, "error": err.strip()}
        except Exception as e:
            result[family] = {"ok": False, "entries": 0, "error": str(e)}

    # 如果下载成功，触发 birdc configure
    if result["v4"]["ok"] or result["v6"]["ok"]:
        reload_result = _safe_birdc_exec("configure")
        result["bird_reload"] = reload_result

    # 记录到数据库
    status = "success" if (result["v4"]["ok"] and result["v6"]["ok"]) else (
        "partial" if (result["v4"]["ok"] or result["v6"]["ok"]) else "failed"
    )
    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute("""
                INSERT INTO roa_updates (status, entries_v4, entries_v6, triggered_by, error_msg)
                VALUES (?, ?, ?, 'manual', ?)
            """, (
                status,
                result["v4"]["entries"],
                result["v6"]["entries"],
                json.dumps(result.get("bird_reload", {})),
            ))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    return result


# ====================== API 路由 ======================

# ---------- 认证 ----------
@ADMIN_BP.post("/login")
def admin_login():
    """管理员登录。"""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    with _DB_LOCK:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            conn.close()

    if not row or not _verify_password(password, row["password_hash"]):
        _audit_log(username, "login_failed", "", "", request.remote_addr)
        return jsonify({"error": "用户名或密码错误"}), 401

    session["admin_user"] = username
    session["admin_role"] = row["role"]
    session.permanent = True

    # 更新最后登录时间
    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute(
                "UPDATE admin_users SET last_login = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
        finally:
            conn.close()

    _audit_log(username, "login_success", "", "", request.remote_addr)
    return jsonify({"username": username, "role": row["role"]})


@ADMIN_BP.post("/logout")
def admin_logout():
    """管理员登出。"""
    user = session.get("admin_user", "unknown")
    session.clear()
    _audit_log(user, "logout")
    return jsonify({"ok": True})


@ADMIN_BP.get("/session")
def admin_session_check():
    """检查当前会话状态。"""
    if session.get("admin_user"):
        return jsonify({
            "logged_in": True,
            "username": session["admin_user"],
            "role": session.get("admin_role", "admin"),
        })
    return jsonify({"logged_in": False})


# ---------- 仪表盘 ----------
@ADMIN_BP.get("/dashboard")
def admin_dashboard():
    """仪表盘总览数据。"""
    from backend import integration

    metrics = collect_metrics()
    node = integration.node_summary()
    roa = integration.roa_status()

    # 最近审计日志
    with _DB_LOCK:
        conn = _get_db()
        try:
            recent_logs = conn.execute(
                "SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10"
            ).fetchall()
            recent_roa = conn.execute(
                "SELECT * FROM roa_updates ORDER BY id DESC LIMIT 5"
            ).fetchall()
            key_count = conn.execute("SELECT COUNT(*) FROM api_keys WHERE revoked = 0").fetchone()[0]
        finally:
            conn.close()

    return jsonify({
        "metrics": metrics,
        "node": node,
        "roa": roa,
        "api_keys_active": key_count,
        "recent_logs": [dict(r) for r in recent_logs],
        "recent_roa_updates": [dict(r) for r in recent_roa],
    })


# ---------- BGP 会话管理 ----------
@ADMIN_BP.get("/peers")
def admin_peers():
    """列出所有 BGP peer 及状态。"""
    from backend import bird as bird_mod
    try:
        data = bird_mod.bird.protocols()
        parsed = data.get("parsed", [])
        if isinstance(parsed, list):
            return jsonify({"peers": parsed, "raw": data.get("raw", "")})
        return jsonify({"peers": [], "raw": data.get("raw", "")})
    except bird_mod.BirdError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ADMIN_BP.post("/peers/<name>/enable")
def admin_peer_enable(name):
    """启用 BGP peer。"""
    if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", name):
        return jsonify({"error": "非法协议名"}), 400

    result = _safe_birdc_exec(f"enable {name}")
    _audit_log(g.admin_user, "peer_enable", name, json.dumps(result), request.remote_addr)
    status = 200 if result["ok"] else 502
    return jsonify(result), status


@ADMIN_BP.post("/peers/<name>/disable")
def admin_peer_disable(name):
    """禁用 BGP peer。"""
    if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", name):
        return jsonify({"error": "非法协议名"}), 400

    result = _safe_birdc_exec(f"disable {name}")
    _audit_log(g.admin_user, "peer_disable", name, json.dumps(result), request.remote_addr)
    status = 200 if result["ok"] else 502
    return jsonify(result), status


@ADMIN_BP.post("/peers/<name>/restart")
def admin_peer_restart(name):
    """重启 BGP peer。"""
    if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", name):
        return jsonify({"error": "非法协议名"}), 400

    result = _safe_birdc_exec(f"restart {name}")
    _audit_log(g.admin_user, "peer_restart", name, json.dumps(result), request.remote_addr)
    status = 200 if result["ok"] else 502
    return jsonify(result), status


# ---------- ROA 管理 ----------
@ADMIN_BP.get("/roa")
def admin_roa_status():
    """ROA 表当前状态。"""
    from backend import integration
    return jsonify(integration.roa_status())


@ADMIN_BP.post("/roa/update")
def admin_roa_update():
    """手动触发 ROA 数据更新。"""
    result = _trigger_roa_update()
    _audit_log(g.admin_user, "roa_update", "", json.dumps(result), request.remote_addr)
    return jsonify(result)


@ADMIN_BP.get("/roa/history")
def admin_roa_history():
    """ROA 更新历史。"""
    limit = min(int(request.args.get("limit", 50)), 200)
    with _DB_LOCK:
        conn = _get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM roa_updates ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
    return jsonify({"history": [dict(r) for r in rows]})


# ---------- 配置管理 ----------
@ADMIN_BP.get("/config")
def admin_config_view():
    """查看当前配置（脱敏）。"""
    safe_config = {
        "SITE_NAME": config.SITE_NAME,
        "NODE_NAME": config.NODE_NAME,
        "NODE_ASN": config.NODE_ASN,
        "MY_ASN": getattr(config, "MY_ASN", config.NODE_ASN),
        "HOST": config.HOST,
        "PORT": config.PORT,
        "DEMO_MODE": config.DEMO_MODE,
        "BIRD_RESTRICT": config.BIRD_RESTRICT,
        "BIRD_SOCKET": config.BIRD_SOCKET,
        "BIRDC_BIN": config.BIRDC_BIN,
        "BIRD_TIMEOUT": config.BIRD_TIMEOUT,
        "CACHE_ENABLED": config.CACHE_ENABLED,
        "CACHE_TTL_STATUS": config.CACHE_TTL_STATUS,
        "CACHE_TTL_PROTOCOLS": config.CACHE_TTL_PROTOCOLS,
        "CACHE_TTL_ROUTES": config.CACHE_TTL_ROUTES,
        "CACHE_TTL_LOOKUP": config.CACHE_TTL_LOOKUP,
        "CACHE_TTL_MEMORY": config.CACHE_TTL_MEMORY,
        "RATE_LIMIT": config.RATE_LIMIT,
        "API_KEY_CONFIGURED": bool(config.API_KEY),
        "TRACEROUTE_BIN": config.TRACEROUTE_BIN,
        "WHOIS_BIN": config.WHOIS_BIN,
    }

    # 读取配置覆盖
    with _DB_LOCK:
        conn = _get_db()
        try:
            overrides = conn.execute("SELECT * FROM config_overrides").fetchall()
        finally:
            conn.close()

    return jsonify({
        "current": safe_config,
        "overrides": [dict(r) for r in overrides],
    })


@ADMIN_BP.put("/config")
def admin_config_update():
    """更新配置覆盖（不会直接修改运行时配置，仅记录覆盖值供重启后生效）。"""
    data = request.get_json(silent=True) or {}
    key = data.get("key", "").strip()
    value = str(data.get("value", ""))
    value_type = data.get("type", "string")

    if not key:
        return jsonify({"error": "key 不能为空"}), 400

    # 仅允许覆盖白名单中的配置项
    allowed_keys = {
        "CACHE_TTL_STATUS", "CACHE_TTL_PROTOCOLS", "CACHE_TTL_ROUTES",
        "CACHE_TTL_LOOKUP", "CACHE_TTL_MEMORY", "RATE_LIMIT",
        "SITE_NAME", "NODE_NAME",
    }
    if key not in allowed_keys:
        return jsonify({"error": f"不允许覆盖配置项: {key}"}), 400

    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute("""
                INSERT INTO config_overrides (key, value, value_type, updated_at, updated_by)
                VALUES (?, ?, ?, datetime('now'), ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    value_type = excluded.value_type,
                    updated_at = datetime('now'),
                    updated_by = excluded.updated_by
            """, (key, value, value_type, g.admin_user))
            conn.commit()
        finally:
            conn.close()

    _audit_log(g.admin_user, "config_update", key, value, request.remote_addr)

    # 对部分配置即时生效
    if key.startswith("CACHE_TTL_") and hasattr(config, key):
        setattr(config, key, int(value) if value_type == "int" else value)
    elif key == "RATE_LIMIT":
        from backend import app as app_mod
        app_mod.rate_limiter.max_req = int(value)

    return jsonify({"ok": True, "key": key, "value": value})


# ---------- API Key 管理 ----------
@ADMIN_BP.get("/api-keys")
def admin_api_keys_list():
    """列出所有 API Key。"""
    with _DB_LOCK:
        conn = _get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM api_keys ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
    return jsonify({"keys": [dict(r) for r in rows]})


@ADMIN_BP.post("/api-keys")
def admin_api_keys_create():
    """创建新的 API Key。"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip() or "unnamed"
    new_key = secrets.token_urlsafe(32)

    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute(
                "INSERT INTO api_keys (key, name, created_by) VALUES (?, ?, ?)",
                (new_key, name, g.admin_user),
            )
            conn.commit()
        finally:
            conn.close()

    _audit_log(g.admin_user, "api_key_create", name, "", request.remote_addr)
    return jsonify({"key": new_key, "name": name})


@ADMIN_BP.delete("/api-keys/<int:key_id>")
def admin_api_keys_revoke(key_id):
    """吊销 API Key。"""
    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute(
                "UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM api_keys WHERE id = ?", (key_id,)
            ).fetchone()
        finally:
            conn.close()

    if row:
        _audit_log(g.admin_user, "api_key_revoke", row["name"], f"id={key_id}", request.remote_addr)
    return jsonify({"ok": True})


# ---------- 审计日志 ----------
@ADMIN_BP.get("/audit-logs")
def admin_audit_logs():
    """查询审计日志（分页）。"""
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(int(request.args.get("per_page", 50)), 200)
    offset = (page - 1) * per_page

    with _DB_LOCK:
        conn = _get_db()
        try:
            total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
        finally:
            conn.close()

    return jsonify({
        "logs": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


# ---------- 系统监控 ----------
@ADMIN_BP.get("/metrics")
def admin_metrics():
    """当前系统实时指标。"""
    return jsonify(collect_metrics())


@ADMIN_BP.get("/metrics/history")
def admin_metrics_history():
    """历史指标数据（默认最近 24 小时）。"""
    hours = min(int(request.args.get("hours", 24)), 168)
    with _DB_LOCK:
        conn = _get_db()
        try:
            rows = conn.execute(
                """SELECT * FROM metrics_history
                   WHERE timestamp >= datetime('now', ?)
                   ORDER BY id ASC""",
                (f"-{hours} hours",),
            ).fetchall()
        finally:
            conn.close()
    return jsonify({"history": [dict(r) for r in rows]})


# ---------- 缓存管理 ----------
@ADMIN_BP.get("/cache/stats")
def admin_cache_stats():
    """缓存统计信息。"""
    from backend import bird as bird_mod
    cache = bird_mod.cache
    with cache._lock:
        entries = len(cache._store)
        keys = list(cache._store.keys())
    return jsonify({
        "enabled": config.CACHE_ENABLED,
        "entries": entries,
        "keys": keys,
        "ttl_config": {
            "status": config.CACHE_TTL_STATUS,
            "protocols": config.CACHE_TTL_PROTOCOLS,
            "routes": config.CACHE_TTL_ROUTES,
            "lookup": config.CACHE_TTL_LOOKUP,
            "memory": config.CACHE_TTL_MEMORY,
        },
    })


@ADMIN_BP.post("/cache/clear")
def admin_cache_clear():
    """清空缓存。"""
    from backend import bird as bird_mod
    bird_mod.cache.clear()
    _audit_log(g.admin_user, "cache_clear")
    return jsonify({"ok": True})


# ---------- BIRD 配置管理 ----------
@ADMIN_BP.get("/bird/config")
def admin_bird_config():
    """查看 BIRD 配置文件内容。"""
    config_path = "/etc/bird/bird.conf"
    try:
        with open(config_path) as f:
            content = f.read()
        return jsonify({"path": config_path, "content": content})
    except FileNotFoundError:
        return jsonify({"error": f"配置文件不存在: {config_path}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ADMIN_BP.post("/bird/reload")
def admin_bird_reload():
    """触发 BIRD 配置重载（birdc configure）。"""
    result = _safe_birdc_exec("configure")
    _audit_log(g.admin_user, "bird_reload", "", json.dumps(result), request.remote_addr)
    status = 200 if result["ok"] else 502
    return jsonify(result), status


# ---------- WireGuard 管理 ----------
@ADMIN_BP.get("/wireguard")
def admin_wireguard():
    """WireGuard 隧道状态。"""
    from backend import integration
    return jsonify(integration.wireguard_status())


# ---------- 系统信息 ----------
@ADMIN_BP.get("/system")
def admin_system():
    """系统信息。"""
    mem = _read_meminfo()
    disk = _read_disk_usage()
    return jsonify({
        "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "uptime": _get_uptime(),
        "memory": mem,
        "disk": disk,
        "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        "pid": os.getpid(),
    })


# ---------- 用户管理（仅超级管理员） ----------
@ADMIN_BP.get("/users")
@require_superadmin
def admin_users_list():
    """列出管理员用户。"""
    with _DB_LOCK:
        conn = _get_db()
        try:
            rows = conn.execute(
                "SELECT id, username, role, created_at, last_login FROM admin_users ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
    return jsonify({"users": [dict(r) for r in rows]})


@ADMIN_BP.post("/users")
@require_superadmin
def admin_users_create():
    """创建新管理员。"""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "admin")

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if role not in ("admin", "superadmin"):
        return jsonify({"error": "角色必须是 admin 或 superadmin"}), 400

    pw_hash = _hash_password(password)
    with _DB_LOCK:
        conn = _get_db()
        try:
            conn.execute(
                "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, pw_hash, role),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "用户名已存在"}), 409
        finally:
            conn.close()

    _audit_log(g.admin_user, "user_create", username, f"role={role}", request.remote_addr)
    return jsonify({"ok": True, "username": username, "role": role})


@ADMIN_BP.post("/users/<int:user_id>/password")
@require_superadmin
def admin_users_password(user_id):
    """修改用户密码。"""
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if len(password) < 6:
        return jsonify({"error": "密码长度至少 6 位"}), 400

    pw_hash = _hash_password(password)
    with _DB_LOCK:
        conn = _get_db()
        try:
            cur = conn.execute(
                "UPDATE admin_users SET password_hash = ? WHERE id = ?",
                (pw_hash, user_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return jsonify({"error": "用户不存在"}), 404
        finally:
            conn.close()

    _audit_log(g.admin_user, "user_password_change", f"id={user_id}", "", request.remote_addr)
    return jsonify({"ok": True})


@ADMIN_BP.delete("/users/<int:user_id>")
@require_superadmin
def admin_users_delete(user_id):
    """删除管理员用户（不能删除自己）。"""
    current_user = session.get("admin_user")
    with _DB_LOCK:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT username FROM admin_users WHERE id = ?", (user_id,)
            ).fetchone()
            if not row:
                return jsonify({"error": "用户不存在"}), 404
            if row["username"] == current_user:
                return jsonify({"error": "不能删除当前登录用户"}), 400
            conn.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    _audit_log(g.admin_user, "user_delete", row["username"], "", request.remote_addr)
    return jsonify({"ok": True})
