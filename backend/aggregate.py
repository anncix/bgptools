# -*- coding: utf-8 -*-
"""
aggregate.py —— ASN 页 / 前缀页聚合视图

模仿 bgp.tools 的 /as/<asn> 与 /prefix/<p> 页面结构，
把 birdc 路由表 + whois 数据聚合成前端可直接渲染的 JSON。

真实模式：扫描 birdc 路由表推断 origin/upstream，whois 提供注册信息。
演示模式：使用 demo.py 内置拓扑，保证数据自洽。
"""
import ipaddress
import re

import config
from backend import demo
from backend import dn42


def _is_demo() -> bool:
    return config.DEMO_MODE


# ====================== ASN 视图 ======================
def as_view(asn: str) -> dict:
    asn = str(asn).strip()
    if not dn42.is_dn42_asn(asn):
        return {"error": f"AS{asn} 不在 DN42 ASN 段 (4242420000-4242429999)"}

    if _is_demo():
        return _demo_as_view(asn)

    # ---- 真实模式：best-effort 组装 ----
    routes = _real_routes()
    originated = [r for r in routes if r["path"] and r["path"][-1] == asn]
    upstreams = _real_upstreams(asn, routes)
    who = dn42.whois(f"AS{asn}")
    name = _parse_whois_field(who.get("raw", ""), "as-name") or f"AS{asn}"
    return {
        "asn": asn,
        "name": name,
        "is_mine": asn == str(config.NODE_ASN),
        "dn42": True,
        "prefixes": [_route_brief(r) for r in originated],
        "upstreams": [{"asn": u, "name": None} for u in upstreams],
        "whois": who.get("raw", ""),
        "registered_on": _parse_whois_field(who.get("raw", ""), "created"),
        "network_status": "Active, allocated under DN42",
    }


def _demo_as_view(asn: str) -> dict:
    name = demo.ASN_NAMES.get(asn)
    if not name:
        return {"error": f"演示数据中不存在 AS{asn}（可试 {', '.join(list(demo.ASN_NAMES)[:4])}）"}
    originated = demo.prefixes_originated(asn)
    upstreams = demo.as_path_upstreams(asn)
    peer_info = next((p for p in demo.PEERS if p["asn"] == asn), None)
    return {
        "asn": asn,
        "name": name,
        "is_mine": asn == demo.MY_ASN,
        "dn42": True,
        "prefixes": [_route_brief(r) for r in originated],
        "upstreams": [
            {"asn": u, "name": demo.ASN_NAMES.get(u)} for u in upstreams
        ],
        "peering": {
            "is_direct_peer": peer_info is not None,
            "neighbor": peer_info["neighbor"] if peer_info else None,
            "established": peer_info["established"] if peer_info else None,
        },
        "whois": demo.aut_num_whois(asn),
        "registered_on": "2014-06-22",
        "network_status": "Active, allocated under DN42",
    }


# ====================== 前缀视图 ======================
def prefix_view(prefix: str) -> dict:
    try:
        net = ipaddress.ip_network(prefix, strict=False)
    except ValueError:
        return {"error": f"非法的前缀: {prefix}"}
    prefix = str(net)

    if _is_demo():
        return _demo_prefix_view(net)

    routes = _real_routes()
    exact = [r for r in routes if r["prefix"] == prefix]
    origin = exact[0]["path"][-1] if exact and exact[0]["path"] else None
    best_path = exact[0]["path"] if exact else []
    who = dn42.whois(prefix)

    # 收集所有唯一 AS 路径
    all_paths = []
    seen_path_tuples = set()
    for r in exact:
        path_tuple = tuple(r["path"])
        if path_tuple not in seen_path_tuples:
            seen_path_tuples.add(path_tuple)
            all_paths.append({
                "path": r["path"],
                "peer": r.get("peer", ""),
                "via": r.get("via", ""),
                "preferred": r.get("preferred", False),
                "roa": r.get("roa", "unknown"),
            })

    return {
        "prefix": prefix,
        "family": net.version,
        "num_addresses": net.num_addresses,
        "origin_as": origin,
        "as_name": None,
        "origin_as_name": None,
        "roa": "unknown",
        "seen": bool(exact),
        "as_path": best_path,
        "all_paths": all_paths,
        "less_specifics": [],
        "whois": who.get("raw", ""),
    }


def _demo_prefix_view(net) -> dict:
    prefix = str(net)
    routes = demo.route_lookup_raw(prefix)
    exact = [r for r in routes if r["prefix"] == prefix]
    # 最长前缀匹配不到时用包含它的路由
    best = exact[0] if exact else (routes[0] if routes else None)
    origin = best["path"][-1] if best else None
    roa = best["roa"] if best else "unknown"
    w = demo.PREFIX_WHOIS.get(prefix)

    # 收集该前缀的所有唯一 AS 路径（可能有多条路由到达同一前缀）
    all_paths = []
    seen_path_tuples = set()
    for r in exact:
        path_tuple = tuple(r["path"])
        if path_tuple not in seen_path_tuples:
            seen_path_tuples.add(path_tuple)
            all_paths.append({
                "path": r["path"],
                "peer": r.get("peer", ""),
                "via": r.get("via", ""),
                "preferred": r.get("preferred", False),
                "roa": r.get("roa", "unknown"),
            })

    return {
        "prefix": prefix,
        "family": net.version,
        "num_addresses": net.num_addresses,
        "origin_as": origin,
        "as_name": demo.ASN_NAMES.get(origin) if origin else None,
        "origin_as_name": demo.ASN_NAMES.get(origin) if origin else None,
        "roa": roa,
        "seen": best is not None,
        "as_path": best["path"] if best else [],
        "all_paths": all_paths,
        "less_specifics": _demo_less_specifics(net),
        "whois": demo.inetnum_whois(prefix),
        "registered_to": w["mnt-by"] if w else None,
        "registered_on": w["created"] if w else None,
    }


def _demo_less_specifics(net) -> list:
    """生成 less-specific 公告示例（包含该前缀的更大前缀）。"""
    out = []
    for r in demo.ROUTES:
        try:
            rn = ipaddress.ip_network(r["prefix"], strict=False)
        except ValueError:
            continue
        if rn.version == net.version and net.subnet_of(rn) and rn != net:
            out.append({"prefix": r["prefix"], "origin_as": r["path"][-1],
                        "name": demo.ASN_NAMES.get(r["path"][-1])})
    # 额外展示 DN42 主网段作为兜底上下文
    if net.version == 4 and str(net) != "172.20.0.0/14":
        out.append({"prefix": "172.20.0.0/14", "origin_as": None,
                    "name": "DN42 主网络（聚合段）"})
    return out


# ====================== 真实模式辅助 ======================
def _real_routes() -> list:
    """从 birdc 取路由并提取完整 AS path（best-effort）。"""
    from backend import bird as bird_mod
    try:
        data = bird_mod.bird.routes(all_details=True)
    except Exception:
        return []
    routes = []
    for item in (data.get("parsed") or {}).get("routes", []):
        # 提取完整 AS Path（BIRD 输出 "AS4242422601 AS4242420666 i"）
        raw = item.get("as_info") or ""
        # 优先使用 parse_routes 已解析的 as_path 列表
        if item.get("as_path"):
            path = item["as_path"]
        else:
            path = re.findall(r'AS(\d+)', raw) if raw else []
        # ROA 状态：优先使用 parse_routes 已解析的 roa 字段
        roa = item.get("roa", "unknown")
        routes.append({
            "prefix": item.get("prefix", ""),
            "path": path,
            "peer": (item.get("source") or "").split()[0],
            "via": (item.get("nexthops") or [""])[0].replace("via ", ""),
            "metric": item.get("metric", ""),
            "preferred": item.get("preferred", False),
            "roa": roa,
        })
    return routes


def _real_upstreams(asn: str, routes: list) -> list:
    ups = set()
    for r in routes:
        path = r.get("path") or []
        if asn in path:
            i = path.index(asn)
            if i > 0:
                ups.add(path[i - 1])
    return sorted(ups)


def _route_brief(r: dict) -> dict:
    return {
        "prefix": r["prefix"],
        "roa": r.get("roa", "unknown"),
        "via": r.get("via", ""),
        "peer": r.get("peer", ""),
        "path": r.get("path", []),
    }


def _parse_whois_field(text: str, field: str) -> str:
    for line in text.splitlines():
        if line.lower().startswith(field.lower()):
            return line.split(":", 1)[1].strip()
    return ""
