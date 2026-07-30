# -*- coding: utf-8 -*-
"""
demo.py —— 演示模式模拟数据

构造一个完整、自洽的虚拟 DN42 拓扑，用于：
1. 本地开发/体验（无 bird2 环境）
2. 单元测试的固定输入

拓扑包含：本机 ASN、4 个 peer（1 个 down）、8 个前缀（v4/v6）、
asn 名称表、ROA 状态、whois 样例对象。所有数据互相关联（路由 AS path
与 peers/prefixes 一致），保证 ASN 页与前缀页聚合结果自洽。
"""
import config


# ====================== 虚拟 DN42 拓扑 ======================
# 本机 ASN（与 config.NODE_ASN 一致时为本机起源）
MY_ASN = config.NODE_ASN or "4242421234"

# ASN → 名称（对应 DN42 registry 的 aut-num as-name）
ASN_NAMES = {
    "4242421234": "MY-NET",
    "4242422601": "BURBLE-MNT",
    "4242423914": "KIOUBIT-MNT",
    "4242422547": "LANTIAN-MNT",
    "4242420666": "ALICE-NET",
    "4242422688": "DN42-ANYCAST-DNS",
}

# BGP 会话（对应 show protocols 的 BGP 行）
# state: Established / Active(连接失败)
PEERS = [
    {
        "name": "peer_burble", "asn": "4242422601",
        "neighbor": "fd42:4242:2601::1", "source": "fd42:4242:2601::2",
        "state": "up", "info": "2026-07-28 10:02:11  Established",
        "established": True, "imported": 1523, "exported": 41,
    },
    {
        "name": "peer_kioubit", "asn": "4242423914",
        "neighbor": "fd00:3914::1", "source": "fd00:3914::2",
        "state": "up", "info": "2026-07-28 10:05:55  Established",
        "established": True, "imported": 1489, "exported": 41,
    },
    {
        "name": "peer_alice", "asn": "4242420666",
        "neighbor": "172.23.66.1", "source": "172.23.66.2",
        "state": "start",
        "info": "2026-07-28 10:08:00  Active        Socket: Connection refused",
        "established": False, "imported": 0, "exported": 0,
    },
    {
        "name": "peer_lantian", "asn": "4242422547",
        "neighbor": "172.22.76.184", "source": "172.22.76.185",
        "state": "up", "info": "2026-07-28 10:10:21  Established",
        "established": True, "imported": 1611, "exported": 39,
    },
]

# 路由表条目（对应 show route 主行）
# 每条: prefix, origin(最后AS), path(完整AS路径), via(下一跳), peer(来源协议),
#       metric, preferred, roa(valid/invalid/unknown)
ROUTES = [
    {"prefix": "172.23.24.0/24",  "path": ["4242421234"],                       "via": "dev dn42-eth0",            "peer": "direct1",      "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1234::/48",  "path": ["4242421234"],                       "via": "dev dn42-eth0",            "peer": "direct1",      "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.21.10.0/24",  "path": ["4242422601"],                       "via": "fd42:4242:2601::1 on wg-burble", "peer": "peer_burble", "metric": "100", "preferred": True, "roa": "valid"},
    {"prefix": "fd42:4242:2601::/48", "path": ["4242422601"],                   "via": "fd42:4242:2601::1 on wg-burble", "peer": "peer_burble", "metric": "100", "preferred": True, "roa": "valid"},
    {"prefix": "172.22.114.0/24", "path": ["4242422547"],                       "via": "172.22.76.184 on wg-lantian", "peer": "peer_lantian", "metric": "100", "preferred": True, "roa": "valid"},
    {"prefix": "fd00:2547::/48",  "path": ["4242422601", "4242422547"],         "via": "fd42:4242:2601::1 on wg-burble", "peer": "peer_burble", "metric": "100", "preferred": True, "roa": "unknown"},
    {"prefix": "fd00:dead:beef::/48", "path": ["4242423914", "4242422547", "4242422601"], "via": "fd00:3914::1 on wg-kioubit", "peer": "peer_kioubit", "metric": "100", "preferred": True, "roa": "invalid"},
    {"prefix": "172.20.44.0/24",  "path": ["4242422601", "4242420666"],         "via": "fd42:4242:2601::1 on wg-burble", "peer": "peer_burble", "metric": "100", "preferred": True, "roa": "valid"},
    {"prefix": "fd00:666::/48",   "path": ["4242423914", "4242420666"],         "via": "fd00:3914::1 on wg-kioubit", "peer": "peer_kioubit", "metric": "100", "preferred": True, "roa": "valid"},
    {"prefix": "172.20.0.53/32",  "path": ["4242423914", "4242422688"],         "via": "fd00:3914::1 on wg-kioubit", "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd42:d42:d42:53::1/128", "path": ["4242422601", "4242422688"],  "via": "fd42:4242:2601::1 on wg-burble", "peer": "peer_burble", "metric": "100", "preferred": True, "roa": "valid"},
]

# 前缀 whois（inetnum/inet6num）样例
PREFIX_WHOIS = {
    "172.21.10.0/24": {
        "netname": "BURBLE-NETWORK", "descr": "burble.dn42",
        "admin-c": "BURBLE-DN42", "mnt-by": "BURBLE-MNT",
        "cidr": "172.21.10.0/24", "created": "2022-03-14",
    },
    "172.22.114.0/24": {
        "netname": "LANTIAN-NET", "descr": "Lan Tian @ lantian.pub",
        "admin-c": "LANTIAN-DN42", "mnt-by": "LANTIAN-MNT",
        "cidr": "172.22.114.0/24", "created": "2020-11-02",
    },
    "172.23.24.0/24": {
        "netname": "MY-NET", "descr": "My DN42 Network",
        "admin-c": "ME-DN42", "mnt-by": "MY-MNT",
        "cidr": "172.23.24.0/24", "created": "2024-01-20",
    },
    "172.20.44.0/24": {
        "netname": "ALICE-NET", "descr": "Alice's Lab",
        "admin-c": "ALICE-DN42", "mnt-by": "ALICE-MNT",
        "cidr": "172.20.44.0/24", "created": "2023-06-08",
    },
}

# 节点状态（对应 show status）
STATUS_RAW = (
    f"Router ID is 172.23.24.1\n"
    f"Hostname {config.NODE_NAME or 'node1'}\n"
    f"Current server time is 2026-07-30 12:00:00\n"
    f"Last reboot on 2026-07-28 09:12:33\n"
    f"Last reconfiguration on 2026-07-28 10:10:30\n"
    f"Daemon is up and running\n"
    f"BIRD 2.0.12"
)

MEMORY_RAW = (
    "Routing tables:      1.21 MB\n"
    "Route attributes:    512.34 KB\n"
    "ROA tables:          256.00 KB\n"
    "Protocols:           148.20 KB\n"
    "Total:               2.09 MB"
)


# ====================== 模拟 whois 输出 ======================
def aut_num_whois(asn: str) -> str:
    """构造 DN42 aut-num 对象（真实 whois 输出风格）。"""
    name = ASN_NAMES.get(asn, f"AS{asn}")
    admin = name.replace("-MNT", "-DN42").replace("-NET", "-DN42")
    return (
        f"aut-num:            AS{asn}\n"
        f"as-name:            {name}\n"
        f"descr:              {name} DN42 network\n"
        f"admin-c:            {admin}\n"
        f"tech-c:             {admin}\n"
        f"mnt-by:             {name if name.endswith('MNT') else name + '-MNT'}\n"
        f"source:             DN42"
    )


def inetnum_whois(prefix: str) -> str:
    """构造 DN42 inetnum/inet6num 对象。"""
    w = PREFIX_WHOIS.get(prefix)
    if not w:
        return f"% No entries found for {prefix} in DN42 registry."
    addr_key = "inet6num" if ":" in prefix else "inetnum"
    addr_val = prefix if ":" in prefix else _v4_range(prefix)
    return (
        f"{addr_key}:        {addr_val}\n"
        f"netname:            {w['netname']}\n"
        f"descr:              {w['descr']}\n"
        f"country:            CN\n"
        f"admin-c:            {w['admin-c']}\n"
        f"tech-c:             {w['admin-c']}\n"
        f"mnt-by:             {w['mnt-by']}\n"
        f"status:             ASSIGNED\n"
        f"cidr:               {w['cidr']}\n"
        f"source:             DN42"
    )


def _v4_range(prefix: str) -> str:
    """172.21.10.0/24 -> 172.21.10.0 - 172.21.10.255"""
    import ipaddress
    net = ipaddress.ip_network(prefix, strict=False)
    return f"{net.network_address} - {net.broadcast_address}"


# ====================== bird 输出模拟（原始文本） ======================
def protocols_raw() -> str:
    lines = ["name          proto    table    state  since       info"]
    lines.append("kernel1       Kernel   master   up     2026-07-28")
    lines.append("device1       Device   master   up     2026-07-28")
    lines.append("direct1       Direct   master   up     2026-07-28")
    for p in PEERS:
        # 对齐到 14 列
        lines.append(f"{p['name']:<14}BGP      master   {p['state']:<7} {p['info']}")
    return "\n".join(lines)


def protocol_detail_raw(name: str) -> str:
    p = next((x for x in PEERS if x["name"] == name), None)
    if not p:
        return f"protocol {name} not found"
    return (
        f"  Name:       {p['name']}\n"
        f"  Type:       BGP\n"
        f"  Neighbor:   {p['neighbor']}\n"
        f"  Source:     {p['source']}\n"
        f"  Neighbor AS: {p['asn']}\n"
        f"  State:      {'Established' if p['established'] else 'Active'}\n"
        f"  Routes: {p['imported']} imported, {p['exported']} exported\n"
        f"  BGP Next hop: {p['source']}"
    )


def routes_raw(routes=None) -> str:
    routes = routes if routes is not None else ROUTES
    out = []
    for r in routes:
        star = " *" if r["preferred"] else "  "
        aspath = " ".join(r["path"]) + " i"
        out.append(
            f"{r['prefix']:<22} unicast [{r['peer']} 2026-07-28 10:10:01]"
            f"{star} ({r['metric']}) [AS{aspath}]"
        )
        out.append(f"\tvia {r['via']}")
    return "\n".join(out)


def route_lookup_raw(target: str) -> list:
    """模拟 show route for <target>：最长前缀匹配或包含匹配。"""
    import ipaddress
    try:
        if "/" in target:
            net = ipaddress.ip_network(target, strict=False)
        else:
            ip = ipaddress.ip_address(target)
            net = ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}", strict=False)
    except ValueError:
        return []
    hits = []
    for r in ROUTES:
        try:
            rn = ipaddress.ip_network(r["prefix"], strict=False)
        except ValueError:
            continue
        if rn.version == net.version and (net.subnet_of(rn) or net == rn or rn.subnet_of(net)):
            hits.append(r)
    return hits


def as_path_upstreams(asn: str) -> list:
    """从路由表推断 ASN 的上游（path 中出现在它前面的 AS）。"""
    ups = set()
    for r in ROUTES:
        path = r["path"]
        if asn in path:
            i = path.index(asn)
            if i > 0:
                ups.add(path[i - 1])
    return sorted(ups)


def prefixes_originated(asn: str) -> list:
    """ASN 起源的所有前缀（path 最后一个 AS）。"""
    return [r for r in ROUTES if r["path"] and r["path"][-1] == asn]
