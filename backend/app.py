# -*- coding: utf-8 -*-
"""
app.py —— BGP Tool for DN42 主应用

启动：python backend/app.py  或  gunicorn -w 1 -b 127.0.0.1:8421 backend.app:app

提供：
- REST API（/api/*）：status / protocols / routes / route lookup / memory / traceroute / whois / roa / dn42 info
- 前端静态资源服务（/）
- 鉴权（可选 API Key）+ 简易内存限流 + JSON 错误处理

适配 1C1G：单 worker 即可承载典型 LG 流量；缓存进一步降低 birdc 负载。
"""
import os
import sys
import time
import threading
from collections import defaultdict, deque

# 让 `import config` / `from backend import ...` 在任意工作目录下可用
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from flask import (
    Flask, request, jsonify, send_from_directory, abort, g,
)

import config
from backend import bird as bird_mod
from backend import dn42
from backend import demo
from backend import search as search_mod
from backend import aggregate

app = Flask(__name__, static_folder=None)
app.config["JSON_SORT_KEYS"] = False

FRONTEND_DIR = os.path.join(_BASE_DIR, "frontend", "static")


# ====================== 鉴权 ======================
def check_auth():
    """若配置了 API_KEY，则要求请求头 X-API-Key 或 ?key= 匹配。"""
    if not config.API_KEY:
        return True
    provided = request.headers.get("X-API-Key") or request.args.get("key", "")
    return provided == config.API_KEY


# ====================== 限流（内存滑动窗口） ======================
class RateLimiter:
    def __init__(self, max_req_per_min: int):
        self.max_req = max_req_per_min
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.max_req <= 0:
            return True
        now = time.time()
        with self._lock:
            dq = self._hits[key]
            while dq and now - dq[0] > 60:
                dq.popleft()
            if len(dq) >= self.max_req:
                return False
            dq.append(now)
            return True


rate_limiter = RateLimiter(config.RATE_LIMIT)


# ====================== 请求前置处理 ======================
@app.before_request
def _before():
    g.start = time.time()
    if not check_auth():
        return jsonify({"error": "未授权：API Key 无效或缺失"}), 401
    if not rate_limiter.allow(request.remote_addr or "unknown"):
        return jsonify({"error": "请求过于频繁，请稍后再试"}), 429


@app.after_request
def _after(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Server"] = "bgp-tool-dn42"
    return resp


# ====================== 工具函数 ======================
def bird_or_demo(fn_name: str, demo_fn, *args, **kwargs):
    """统一处理：birdc 可用则调用真实方法，否则尝试 demo 模式，否则报错。"""
    try:
        method = getattr(bird_mod.bird, fn_name)
        return method(*args, **kwargs)
    except bird_mod.BirdError as e:
        if config.DEMO_MODE:
            return demo_fn(*args, **kwargs)
        return {"error": str(e)}
    except FileNotFoundError as e:
        if config.DEMO_MODE:
            return demo_fn(*args, **kwargs)
        return {"error": f"缺少依赖：{e}"}


def ok(data):
    if isinstance(data, dict) and "error" in data:
        return jsonify(data), 502
    return jsonify(data)


# ====================== API 路由 ======================
@app.get("/api/health")
def health():
    return ok({
        "status": "ok",
        "demo_mode": config.DEMO_MODE,
        "site": config.SITE_NAME,
        "node": config.NODE_NAME,
    })


@app.get("/api/dn42/info")
def api_dn42_info():
    return ok(dn42.dn42_info())


@app.get("/api/status")
def api_status():
    def demo_status():
        return {"raw": demo.STATUS_RAW, "parsed": bird_mod.parse_status(demo.STATUS_RAW)}
    return ok(bird_or_demo("status", demo_status))


@app.get("/api/memory")
def api_memory():
    try:
        return ok(bird_mod.bird.memory())
    except bird_mod.BirdError as e:
        if config.DEMO_MODE:
            return ok({"raw": demo.MEMORY_RAW, "parsed": {"tables": []}})
        return ok({"error": str(e)})


@app.get("/api/protocols")
def api_protocols():
    name = request.args.get("name", "").strip()
    if name and not bird_mod.BirdClient.valid_protocol_name(name):
        return jsonify({"error": "非法的协议名"}), 400
    try:
        return ok(bird_mod.bird.protocols(name))
    except bird_mod.BirdError as e:
        if config.DEMO_MODE:
            if name:
                return ok({"raw": demo.protocol_detail_raw(name),
                           "parsed": {}})
            return ok({"raw": demo.protocols_raw(),
                       "parsed": bird_mod.parse_protocols(demo.protocols_raw())})
        return ok({"error": str(e)})


@app.get("/api/routes")
def api_routes():
    protocol = request.args.get("protocol", "").strip()
    if protocol and not bird_mod.BirdClient.valid_protocol_name(protocol):
        return jsonify({"error": "非法的协议名"}), 400
    family = request.args.get("family", "all")
    if family not in ("4", "6", "all"):
        return jsonify({"error": "family 必须为 4/6/all"}), 400
    count_only = request.args.get("count", "false").lower() in ("1", "true", "yes")
    primary = request.args.get("primary", "false").lower() in ("1", "true", "yes")
    all_details = request.args.get("all", "false").lower() in ("1", "true", "yes")
    try:
        return ok(bird_mod.bird.routes(
            protocol=protocol, family=family, count_only=count_only,
            primary=primary, all_details=all_details,
        ))
    except bird_mod.BirdError as e:
        if config.DEMO_MODE:
            routes = demo.ROUTES
            if protocol:
                routes = [r for r in routes if r["peer"] == protocol]
            if family == "4":
                routes = [r for r in routes if ":" not in r["prefix"]]
            elif family == "6":
                routes = [r for r in routes if ":" in r["prefix"]]
            if primary:
                routes = [r for r in routes if r["preferred"]]
            raw = demo.routes_raw(routes)
            if count_only:
                return ok({"raw": f"{len(routes)} of {len(demo.ROUTES)} routes",
                           "parsed": {"count": len(routes)}})
            return ok({"raw": raw, "parsed": bird_mod.parse_routes(raw)})
        return ok({"error": str(e)})


@app.get("/api/route/lookup/<path:target>")
def api_route_lookup(target):
    target = target.strip()
    if not bird_mod.BirdClient.valid_ip_or_prefix(target):
        return jsonify({"error": f"非法的 IP 或前缀: {target}"}), 400
    try:
        return ok(bird_mod.bird.route_lookup(target))
    except bird_mod.BirdError as e:
        if config.DEMO_MODE:
            hits = demo.route_lookup_raw(target)
            raw = demo.routes_raw(hits) if hits else f"% Network not in table"
            return ok({"raw": raw, "parsed": bird_mod.parse_routes(raw),
                       "target": target})
        return ok({"error": str(e)})


@app.get("/api/roa/<path:prefix>")
def api_roa(prefix):
    prefix = prefix.strip()
    if not bird_mod.BirdClient.valid_ip_or_prefix(prefix):
        return jsonify({"error": f"非法的前缀: {prefix}"}), 400
    try:
        data = bird_mod.bird.roa_check(prefix)
        # 根据是否有匹配路由简单判定 ROA 可达性
        routes = data.get("parsed", {}).get("routes", [])
        data["reachable"] = len(routes) > 0
        return ok(data)
    except bird_mod.BirdError as e:
        if config.DEMO_MODE:
            hits = demo.route_lookup_raw(prefix)
            raw = demo.routes_raw(hits) if hits else "% Network not in table"
            return ok({"raw": raw, "parsed": bird_mod.parse_routes(raw),
                       "prefix": prefix, "reachable": bool(hits)})
        return ok({"error": str(e)})


@app.get("/api/traceroute/<path:host>")
def api_traceroute(host):
    host = host.strip()
    if not bird_mod.BirdClient.valid_host(host):
        return jsonify({"error": "非法的主机名"}), 400
    return ok(dn42.traceroute(host))


@app.get("/api/whois")
def api_whois():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "缺少参数 q"}), 400
    if config.DEMO_MODE:
        q = query.lstrip("ASas").strip()
        if q.isdigit():
            return ok({"raw": demo.aut_num_whois(q), "query": query})
        return ok({"raw": demo.inetnum_whois(query), "query": query})
    return ok(dn42.whois(query))


# ---------- bgp.tools 风格聚合 API ----------
@app.get("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    result = search_mod.classify(q)
    if result["type"] == "unknown":
        return jsonify({"error": f"无法识别的查询: {q}"}), 400
    return ok(result)


@app.get("/api/as/<asn>")
def api_as_view(asn):
    asn = str(asn).strip().lstrip("ASas")
    if not asn.isdigit():
        return jsonify({"error": "非法的 ASN"}), 400
    data = aggregate.as_view(asn)
    if "error" in data:
        return jsonify(data), 404
    return ok(data)


@app.get("/api/prefix/<path:prefix>")
def api_prefix_view(prefix):
    data = aggregate.prefix_view(prefix)
    if "error" in data:
        return jsonify(data), 400
    return ok(data)


@app.post("/api/cache/clear")
def api_cache_clear():
    bird_mod.cache.clear()
    return ok({"cleared": True})


# ====================== 前端静态服务（SPA） ======================
@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    """静态资源直出；SPA 路由路径（/as/x、/prefix/y、/lg…）回退到 index.html。"""
    # 防目录穿越
    if ".." in filename or filename.startswith("/"):
        abort(404)
    full = os.path.join(FRONTEND_DIR, filename)
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    if os.path.exists(full):
        return send_from_directory(FRONTEND_DIR, filename)
    # 不是真实文件 → 视为前端路由，交给 SPA
    return send_from_directory(FRONTEND_DIR, "index.html")


# ====================== 错误处理 ======================
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "接口不存在"}), 404
    return send_from_directory(FRONTEND_DIR, "index.html"), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "服务器内部错误", "detail": str(e)}), 500


if __name__ == "__main__":
    print(f"[*] {config.SITE_NAME} 启动中...")
    print(f"[*] 监听: http://{config.HOST}:{config.PORT}")
    print(f"[*] BIRD socket: {config.BIRD_SOCKET} (restrict={config.BIRD_RESTRICT})")
    print(f"[*] Demo mode: {config.DEMO_MODE} | Cache: {config.CACHE_ENABLED}")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=False,
        threaded=True,
    )
