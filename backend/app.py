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
            return ok(bird_mod.demo_routes(prefix))
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


@app.get("/api/as-path/search")
def api_as_path_search():
    """全网 AS Path 搜索。

    参数 q 支持两种形式：
    - 单个 ASN（如 "4242421234" 或 "AS4242421234"）：返回该 ASN 的完整 AS Path 图
    - 两个 ASN（如 "4242421234 4242422601"）：返回两个 ASN 之间的可达路径
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "缺少查询参数 q"}), 400
    if config.DEMO_MODE:
        return ok(demo.search_as_paths(query))
    # 真实模式：从 birdc 路由表聚合 AS Path
    try:
        routes = bird_mod.bird.routes(all_details=True)
        parsed = routes.get("parsed", {}) if isinstance(routes, dict) else {}
        route_list = parsed.get("routes", []) if isinstance(parsed, dict) else []
        if not route_list:
            return ok({"error": "当前路由表为空，无法分析 AS Path"})
        return ok(_search_as_paths_real(query, route_list))
    except bird_mod.BirdError as e:
        return ok({"error": str(e)})
    except Exception as e:
        return ok({"error": f"AS Path 搜索失败: {e}"})


def _parse_real_as_path(route_item: dict) -> list:
    """从 BIRD 解析的路由条目中提取 AS Path 列表。

    BIRD 输出的 as_info 格式为 "AS4242422601 AS4242420666 i"，
    需要提取所有 AS 号（去掉 AS 前缀）。
    """
    import re
    raw = route_item.get("as_info") or route_item.get("as_path") or ""
    if isinstance(raw, list):
        return [str(a) for a in raw]
    # 从 "AS4242422601 AS4242420666 i" 中提取所有 AS 号
    return re.findall(r'AS(\d+)', raw)


def _search_as_paths_real(query: str, route_list: list) -> dict:
    """真实模式下的 AS Path 搜索，结构与 demo.search_as_paths 一致。"""
    import re
    asns = re.findall(r'(?:AS)?(\d{1,10})', query, re.IGNORECASE)
    if not asns:
        return {"error": "无法识别 ASN，请输入如 AS4242421234 或 4242421234 4242422601"}

    my_asn = str(config.MY_ASN) if hasattr(config, 'MY_ASN') else ""

    # 构建 path -> [prefixes] 的映射，同时收集节点信息
    path_prefix_map = {}
    name_map = {}
    node_prefix_count = {}  # ASN -> 起源前缀数

    for r in route_list:
        path = _parse_real_as_path(r)
        if not path:
            continue
        prefix = r.get("prefix", "")
        key = tuple(path)
        path_prefix_map.setdefault(key, []).append(prefix)
        for a in path:
            if a not in name_map:
                name_map[a] = f"AS{a}"
        # 起源前缀（path 最后一个 AS）
        origin = path[-1]
        node_prefix_count[origin] = node_prefix_count.get(origin, 0) + 1

    # 上游/下游/对等方计算（与 demo 逻辑一致）
    def _upstreams(asn):
        ups = set()
        for path in path_prefix_map:
            if asn in path:
                i = path.index(asn)
                if i > 0:
                    ups.add(path[i - 1])
        return sorted(ups)

    def _downstreams(asn):
        downs = set()
        for path in path_prefix_map:
            if asn in path:
                i = len(path) - 1 - path[::-1].index(asn)
                if i < len(path) - 1:
                    downs.add(path[i + 1])
        return sorted(downs)

    def _peers(asn):
        ups = set(_upstreams(asn))
        peers = set()
        for path in path_prefix_map:
            if asn not in path:
                continue
            i = path.index(asn)
            if i > 0:
                my_up = path[i - 1]
                for p2 in path_prefix_map:
                    for j in range(1, len(p2)):
                        if p2[j - 1] == my_up and p2[j] != asn and p2[j] not in ups:
                            peers.add(p2[j])
        return sorted(peers)

    if len(asns) == 1:
        asn = asns[0]

        # 本机 ASN 前插逻辑
        effective_paths = {}
        if asn == my_asn:
            for path, pfxs in path_prefix_map.items():
                new_path = (my_asn,) + path if my_asn not in path else path
                effective_paths.setdefault(new_path, []).extend(pfxs)
        else:
            effective_paths = path_prefix_map

        all_asns = set()
        for path in effective_paths:
            if asn in path:
                all_asns.update(path)
        if not all_asns:
            return {"error": f"AS{asn} 未出现在当前路由表的任何 AS Path 中"}

        nodes = [{"id": a, "name": name_map.get(a, f"AS{a}"),
                  "type": "edge", "is_origin": a == asn,
                  "is_tier1": False, "prefix_count": node_prefix_count.get(a, 0)}
                 for a in all_asns]
        edges = []
        edge_seen = set()
        edge_prefixes = {}
        for path, pfxs in effective_paths.items():
            if asn not in path:
                continue
            for i in range(len(path) - 1):
                k = (path[i], path[i + 1])
                if k not in edge_seen:
                    edge_seen.add(k)
                    edge_prefixes[k] = set()
                edge_prefixes[k].update(pfxs)
        for (s, t), pfxs in edge_prefixes.items():
            edges.append({"source": s, "target": t,
                          "prefixes": sorted(pfxs), "prefix_count": len(pfxs)})

        ups = _upstreams(asn)
        downs = _downstreams(asn)
        return {
            "query_type": "single", "origin": asn,
            "origin_name": name_map.get(asn, f"AS{asn}"),
            "nodes": nodes, "edges": edges,
            "upstreams": [{"asn": u, "name": name_map.get(u, f"AS{u}")} for u in ups],
            "downstreams": [{"asn": d, "name": name_map.get(d, f"AS{d}")} for d in downs],
            "peers": [{"asn": p, "name": name_map.get(p, f"AS{p}")} for p in _peers(asn)],
            "policies": [],
            "total_paths": len([p for p in effective_paths if asn in p]),
            "total_prefixes": node_prefix_count.get(asn, 0),
        }

    src, dst = asns[0], asns[1]
    if src == dst:
        return {"error": f"源 ASN 和目标 ASN 相同（AS{src}），请输入两个不同的 ASN"}

    # 本机 ASN 前插
    need_my = (src == my_asn or dst == my_asn)
    effective_paths = {}
    if need_my:
        for path, pfxs in path_prefix_map.items():
            new_path = (my_asn,) + path if my_asn not in path else path
            effective_paths.setdefault(new_path, []).extend(pfxs)
    else:
        effective_paths = path_prefix_map

    found_paths = []
    for path, prefixes in effective_paths.items():
        if src in path and dst in path:
            si, di = path.index(src), path.index(dst)
            sub = list(path[si:di + 1]) if si < di else list(path[di:si + 1])
            for pfx in prefixes:
                found_paths.append({
                    "path": sub, "prefix": pfx, "full_path": list(path),
                    "direction": "src→dst" if si < di else "dst→src",
                })
    path_asns = set()
    for fp in found_paths:
        path_asns.update(fp["path"])
    nodes = [{"id": a, "name": name_map.get(a, f"AS{a}"),
              "type": "edge", "is_origin": a in (src, dst),
              "is_tier1": False} for a in path_asns]
    edges = []
    edge_seen = set()
    for fp in found_paths:
        p = fp["path"]
        for i in range(len(p) - 1):
            k = (p[i], p[i + 1])
            if k not in edge_seen:
                edge_seen.add(k)
                edges.append({"source": p[i], "target": p[i + 1], "prefix": fp["prefix"]})
    return {
        "query_type": "pair", "src": src, "src_name": name_map.get(src, f"AS{src}"),
        "dst": dst, "dst_name": name_map.get(dst, f"AS{dst}"),
        "found": len(found_paths) > 0, "paths": found_paths,
        "nodes": nodes, "edges": edges, "total_paths": len(found_paths),
    }


@app.get("/api/as-path/graph/<asn>")
def api_as_path_graph(asn):
    """单个 ASN 的 AS Path 图（含上游/下游/网络策略）。"""
    asn = str(asn).strip().lstrip("ASas")
    if not asn.isdigit():
        return jsonify({"error": "非法的 ASN"}), 400
    if config.DEMO_MODE:
        if asn not in demo.ASN_NAMES:
            return jsonify({"error": f"AS{asn} 不在演示拓扑中"}), 404
        return ok(demo.as_path_graph(asn))
    return ok({"error": "真实模式 AS Path 图暂未实现，请使用 /api/as-path/search"})


# ---------- IX / IXP ----------
@app.get("/api/ix")
def api_ix_list():
    """所有互联网交换点列表。"""
    if config.DEMO_MODE:
        return ok({"ix_list": demo.ix_list()})
    return ok({"ix_list": [], "error": "真实模式暂不支持 IX 列表"})


@app.get("/api/ix/<ix_id>")
def api_ix_view(ix_id):
    """单个 IX 详细信息，含成员列表。"""
    if config.DEMO_MODE:
        data = demo.ix_view(ix_id)
        if data is None:
            return jsonify({"error": f"找不到 IX: {ix_id}"}), 404
        return ok(data)
    return ok({"error": "真实模式暂不支持 IX 详情"})


@app.get("/api/ix/asn/<asn>")
def api_ix_for_asn(asn):
    """查询某 ASN 参与的所有 IX。"""
    asn = str(asn).strip().lstrip("ASas")
    if config.DEMO_MODE:
        return ok({"asn": asn, "ix_list": demo.ix_for_asn(asn)})
    return ok({"asn": asn, "ix_list": []})


# ---------- DNS ----------
@app.get("/api/dns/lookup/<path:query>")
def api_dns_lookup(query):
    """DNS 查询：支持 IP 反向(PTR)和域名正向(A/AAAA)查找。
    
    返回格式统一为 {query, query_type, records: {TYPE: [values]}, description}
    以匹配前端 renderDnsPage 的期望。
    """
    query = query.strip()
    if config.DEMO_MODE:
        raw = demo.dns_lookup(query)
        # 转换为前端期望的统一格式
        records = {}
        if raw.get("found"):
            if raw.get("name"):
                records["PTR"] = raw["name"]
            if raw.get("A"):
                records["A"] = raw["A"]
            if raw.get("AAAA"):
                records["AAAA"] = raw["AAAA"]
        return ok({
            "query": raw.get("query", query),
            "query_type": raw.get("type", "unknown"),
            "records": records,
            "description": raw.get("description", ""),
        })
    return ok({"query": query, "query_type": "unknown", "records": {}, "error": "真实模式暂不支持 DNS 查询"})


@app.get("/api/dns/prefix/<path:prefix>")
def api_dns_for_prefix(prefix):
    """返回某前缀范围内的所有 DNS 记录。
    
    返回格式为 {prefix, records: {ip: {PTR, A, AAAA, description}}}
    以匹配前端 loadDnsForPrefix 的期望。
    """
    prefix = prefix.strip()
    if config.DEMO_MODE:
        raw = demo.dns_for_prefix(prefix)
        # 转换为前端期望的 {ip: record} 字典格式
        records_dict = {}
        for rec in raw.get("records", []):
            ip = rec.get("address", "")
            records_dict[ip] = {
                "PTR": rec.get("PTR", []),
                "A": rec.get("A", []),
                "AAAA": rec.get("AAAA", []),
                "description": rec.get("description", ""),
            }
        return ok({"prefix": prefix, "records": records_dict})
    return ok({"prefix": prefix, "records": {}})


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
