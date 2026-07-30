# -*- coding: utf-8 -*-
"""
demo.py —— 演示模式模拟数据

构造一个完整、自洽的虚拟 DN42 拓扑，用于：
1. 本地开发/体验（无 bird2 环境）
2. 单元测试的固定输入

拓扑包含：本机 ASN、8 个 peer（1 个 down）、40+ 个 ASN、80+ 条路由（v4/v6 混合）、
多层级 AS Path（含 AS Prepending 示例）、asn 名称表、ROA 状态、whois 样例对象。
所有数据互相关联（路由 AS path 与 peers/prefixes 一致），保证 ASN 页、
前缀页与 AS Path 页聚合结果自洽。
"""
import config


# ====================== 虚拟 DN42 拓扑 ======================
# 本机 ASN（演示模式固定使用 4242421234，与拓扑数据一致）
MY_ASN = "4242421234"

# DN42 中的 "Tier 1" 节点 —— 连接最广、被多数人 peer 的核心中转 AS
# 对应 bgp.tools 中全球 Tier 1 的概念，在 DN42 中是最大的 transit 提供者
DN42_TIER1 = {
    "4242422601": "BURBLE",
    "4242423914": "KIOUBIT",
    "4242422547": "LANTIAN",
    "4242421376": "PEERABLE",
}

# ASN → 名称（对应 DN42 registry 的 aut-num as-name）
# 共 32 个 ASN，覆盖 Tier1 / Transit / Edge 三层
ASN_NAMES = {
    # === 本机 ===
    "4242421234": "MY-NET",
    # === DN42 Tier 1 核心中转 ===
    "4242422601": "BURBLE-MNT",
    "4242423914": "KIOUBIT-MNT",
    "4242422547": "LANTIAN-MNT",
    "4242421376": "PEERABLE-NET",
    # === 二级 Transit（通过 Tier1 中转）===
    "4242420666": "ALICE-NET",
    "4242422688": "DN42-ANYCAST-DNS",
    "4242423088": "JPIA-NET",
    "4242423750": "SUNNET",
    "4242422464": "ROUTER-SERVER",
    "4242420927": "NEXUS-NET",
    # === 边缘/叶节点 AS ===
    "4242427777": "SMALL-NET",
    "4242428888": "TINY-NET",
    "4242429999": "EDGE-NET",
    "4242424444": "REMOTE-NET",
    "4242425555": "FAR-NET",
    "4242426666": "ISOLATED-NET",
    "4242427770": "INDIE-NET",
    "4242422233": "MESH-NET",
    "4242423344": "STAR-NET",
    "4242421816": "SERVING-NET",
    "4242421080": "GAME-NET",
    "4242421926": "MEDIA-NET",
    "4242423476": "LAB-NET",
    "4242424100": "CLOUD-NET",
    "4242424200": "DEV-NET",
    "4242424300": "TEST-NET",
    "4242424400": "DEMO-NET",
    "4242424500": "PILOT-NET",
    "4242424600": "BETA-NET",
    "4242424700": "ALPHA-NET",
    "4242424800": "GAMMA-NET",
    "4242424900": "OMEGA-NET",
    # === 额外边缘 AS（扩展拓扑复杂度）===
    "4242425000": "NOVA-NET",
    "4242425100": "PHOENIX-NET",
    "4242425200": "ORION-NET",
    "4242425300": "LYRA-NET",
    "4242425400": "DRACO-NET",
    "4242425500": "HYDRA-NET",
    "4242425600": "PEGASUS-NET",
    "4242425700": "CYGNUS-NET",
    # === 扩展 Transit（新增二级中转）===
    "4242426100": "ZENITH-NET",
    "4242426200": "APEX-NET",
    # === 扩展边缘 AS（更多叶节点，增加拓扑广度）===
    "4242425800": "NEBULA-NET",
    "4242425900": "PULSAR-NET",
    "4242426000": "QUASAR-NET",
    "4242426300": "VORTEX-NET",
    "4242426400": "ECLIPSE-NET",
    "4242426500": "AURORA-NET",
    "4242426600": "COSMOS-NET",
    "4242426700": "GALAXY-NET",
}

# ASN 类型标签
ASN_TYPES = {}
for asn in DN42_TIER1:
    ASN_TYPES[asn] = "tier1"
for asn in ["4242420666", "4242422688", "4242423088", "4242423750",
            "4242422464", "4242420927", "4242426100", "4242426200"]:
    ASN_TYPES[asn] = "transit"
for asn in ASN_NAMES:
    if asn not in ASN_TYPES:
        ASN_TYPES[asn] = "edge"

# BGP 会话（对应 show protocols 的 BGP 行）
# 8 个 peer：6 个 up，2 个 down
PEERS = [
    {
        "name": "peer_burble", "asn": "4242422601",
        "neighbor": "fd42:4242:2601::1", "source": "fd42:4242:2601::2",
        "state": "up", "info": "2026-07-28 10:02:11  Established",
        "established": True, "imported": 2150, "exported": 41,
    },
    {
        "name": "peer_kioubit", "asn": "4242423914",
        "neighbor": "fd00:3914::1", "source": "fd00:3914::2",
        "state": "up", "info": "2026-07-28 10:05:55  Established",
        "established": True, "imported": 1980, "exported": 41,
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
        "established": True, "imported": 1870, "exported": 39,
    },
    {
        "name": "peer_peerable", "asn": "4242421376",
        "neighbor": "fd42:1376::1", "source": "fd42:1376::2",
        "state": "up", "info": "2026-07-28 10:12:00  Established",
        "established": True, "imported": 1640, "exported": 37,
    },
    {
        "name": "peer_sunnet", "asn": "4242423750",
        "neighbor": "fd42:3750::1", "source": "fd42:3750::2",
        "state": "up", "info": "2026-07-28 10:14:33  Established",
        "established": True, "imported": 920, "exported": 28,
    },
    {
        "name": "peer_jpia", "asn": "4242423088",
        "neighbor": "fd42:3088::1", "source": "fd42:3088::2",
        "state": "up", "info": "2026-07-28 10:16:10  Established",
        "established": True, "imported": 530, "exported": 25,
    },
    {
        "name": "peer_nexus", "asn": "4242420927",
        "neighbor": "172.21.92.1", "source": "172.21.92.2",
        "state": "start",
        "info": "2026-07-28 10:18:00  Active        Socket: Connection refused",
        "established": False, "imported": 0, "exported": 0,
    },
]

# 路由表条目（对应 show route 主行）
# 每条: prefix, path(完整AS路径), via(下一跳), peer(来源协议),
#       metric, preferred, roa(valid/invalid/unknown)
# 44 条路由，覆盖多层 AS Path：直连、1跳、2跳、3跳、4跳
ROUTES = [
    # === 本机起源前缀（path 长度=1）===
    {"prefix": "172.23.24.0/24",  "path": ["4242421234"],                               "via": "dev dn42-eth0",                  "peer": "direct1",      "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1234::/48",  "path": ["4242421234"],                               "via": "dev dn42-eth0",                  "peer": "direct1",      "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.23.24.0/25",  "path": ["4242421234"],                               "via": "dev dn42-eth0",                  "peer": "direct1",      "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1234:1::/48","path": ["4242421234"],                               "via": "dev dn42-eth0",                  "peer": "direct1",      "metric": "100", "preferred": True,  "roa": "valid"},

    # === Tier1 直连前缀（path 长度=1，通过直连 peer 学到）===
    {"prefix": "172.21.10.0/24",  "path": ["4242422601"],                               "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd42:4242:2601::/48", "path": ["4242422601"],                           "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.22.114.0/24", "path": ["4242422547"],                               "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:2547::/48",  "path": ["4242422547"],                               "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.20.150.0/24", "path": ["4242423914"],                               "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:3914::/48",  "path": ["4242423914"],                               "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.21.37.0/24",  "path": ["4242421376"],                               "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd42:1376::/48",  "path": ["4242421376"],                               "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},

    # === 二级 Transit 前缀（path 长度=2，通过 Tier1 中转）===
    {"prefix": "172.20.44.0/24",  "path": ["4242422601", "4242420666"],                 "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:666::/48",   "path": ["4242423914", "4242420666"],                 "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.20.0.53/32",  "path": ["4242423914", "4242422688"],                 "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd42:d42:d42:53::1/128", "path": ["4242422601", "4242422688"],           "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.21.88.0/24",  "path": ["4242422547", "4242423088"],                 "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:3088::/48",  "path": ["4242423914", "4242423088"],                 "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.22.75.0/24",  "path": ["4242421376", "4242423750"],                 "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd42:3750::/48",  "path": ["4242422601", "4242423750"],                 "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.23.64.0/24",  "path": ["4242423914", "4242422464"],                 "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "unknown"},
    {"prefix": "fd00:2464::/48",  "path": ["4242421376", "4242422464"],                 "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.20.92.0/24",  "path": ["4242422547", "4242420927"],                 "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:927::/48",   "path": ["4242422601", "4242420927"],                 "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "unknown"},

    # === 三级路径（path 长度=3，Tier1 → Transit → Edge）===
    {"prefix": "172.20.77.0/24",  "path": ["4242422601", "4242420666", "4242427777"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:7777::/48",  "path": ["4242423914", "4242420666", "4242427777"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.20.88.0/24",  "path": ["4242422547", "4242423088", "4242428888"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:8888::/48",  "path": ["4242423914", "4242423088", "4242428888"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.20.99.0/24",  "path": ["4242422601", "4242423750", "4242429999"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "invalid"},
    {"prefix": "fd00:9999::/48",  "path": ["4242421376", "4242423750", "4242429999"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.21.44.0/24",  "path": ["4242423914", "4242420666", "4242424444"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4444::/48",  "path": ["4242422547", "4242420927", "4242424444"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.21.55.0/24",  "path": ["4242422601", "4242420927", "4242425555"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "unknown"},
    {"prefix": "fd00:5555::/48",  "path": ["4242423914", "4242422464", "4242425555"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.22.66.0/24",  "path": ["4242421376", "4242423088", "4242426666"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6666::/48",  "path": ["4242422547", "4242423750", "4242426666"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},

    # === 四级路径（path 长度=4，Tier1 → Transit → Transit2 → Edge）===
    {"prefix": "172.20.777.0/24", "path": ["4242422601", "4242420666", "4242427777", "4242427770"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:7770::/48",  "path": ["4242423914", "4242420666", "4242427777", "4242427770"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.22.233.0/24", "path": ["4242422547", "4242423088", "4242428888", "4242422233"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:2233::/48",  "path": ["4242423914", "4242423088", "4242428888", "4242422233"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "unknown"},
    {"prefix": "172.23.344.0/24", "path": ["4242421376", "4242423750", "4242429999", "4242423344"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:3344::/48",  "path": ["4242422601", "4242423750", "4242429999", "4242423344"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},

    # === 更多边缘 AS 前缀（通过不同路径到达）===
    {"prefix": "172.21.816.0/24", "path": ["4242423914", "4242420666", "4242421816"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1816::/48",  "path": ["4242422547", "4242420927", "4242421816"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.20.108.0/24", "path": ["4242422601", "4242420666", "4242421080"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1080::/48",  "path": ["4242423914", "4242422464", "4242421080"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.22.926.0/24", "path": ["4242421376", "4242423750", "4242421926"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1926::/48",  "path": ["4242422601", "4242420927", "4242421926"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.21.476.0/24", "path": ["4242422547", "4242423088", "4242423476"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:3476::/48",  "path": ["4242423914", "4242423088", "4242423476"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},

    # === 最长路径（5跳，Tier1 → Transit → Transit2 → Transit3 → Edge）===
    {"prefix": "172.20.410.0/24", "path": ["4242422601", "4242420666", "4242427777", "4242427770", "4242424100"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4100::/48",  "path": ["4242423914", "4242420666", "4242427777", "4242427770", "4242424100"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.22.490.0/24", "path": ["4242422547", "4242423088", "4242428888", "4242422233", "4242424900"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "unknown"},
    {"prefix": "fd00:4900::/48",  "path": ["4242421376", "4242423750", "4242429999", "4242423344", "4242424900"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},

    # === 补充边缘 AS 路径（确保所有 ASN 都出现在拓扑中）===
    # DEV-NET (4242424200) — 通过 BURBLE → ALICE 中转
    {"prefix": "172.21.420.0/24", "path": ["4242422601", "4242420666", "4242424200"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4200::/48",  "path": ["4242423914", "4242420666", "4242424200"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # TEST-NET (4242424300) — 通过 LANTIAN → JPIA 中转
    {"prefix": "172.22.430.0/24", "path": ["4242422547", "4242423088", "4242424300"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "unknown"},
    {"prefix": "fd00:4300::/48",  "path": ["4242423914", "4242423088", "4242424300"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # DEMO-NET (4242424400) — 通过 PEERABLE → SUNNET 中转
    {"prefix": "172.23.440.0/24", "path": ["4242421376", "4242423750", "4242424400"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4400::/48",  "path": ["4242422601", "4242423750", "4242424400"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    # PILOT-NET (4242424500) — 通过 BURBLE → NEXUS 中转
    {"prefix": "172.21.450.0/24", "path": ["4242422601", "4242420927", "4242424500"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4500::/48",  "path": ["4242422547", "4242420927", "4242424500"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    # BETA-NET (4242424600) — 通过 KIOUBIT → ROUTER-SERVER 中转
    {"prefix": "172.20.460.0/24", "path": ["4242423914", "4242422464", "4242424600"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4600::/48",  "path": ["4242421376", "4242422464", "4242424600"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "unknown"},
    # ALPHA-NET (4242424700) — 通过 LANTIAN → SUNNET 中转
    {"prefix": "172.22.470.0/24", "path": ["4242422547", "4242423750", "4242424700"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4700::/48",  "path": ["4242423914", "4242423750", "4242424700"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # GAMMA-NET (4242424800) — 通过 BURBLE → ALICE → SMALL-NET 中转（3跳）
    {"prefix": "172.21.480.0/24", "path": ["4242422601", "4242420666", "4242427777", "4242424800"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:4800::/48",  "path": ["4242423914", "4242420666", "4242427777", "4242424800"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},

    # === 交叉路径（增加拓扑复杂度，让两 ASN 间有多条路径）===
    # CLOUD-NET 也可通过 KIOUBIT 到达（与 BURBLE 路径形成对比）
    {"prefix": "172.20.4101.0/24","path": ["4242423914", "4242420666", "4242427777", "4242427770", "4242424100"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # OMEGA-NET 也可通过 BURBLE 到达（与 LANTIAN 路径形成对比）
    {"prefix": "172.22.4901.0/24","path": ["4242422601", "4242423750", "4242429999", "4242423344", "4242424900"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # DEV-NET 也可通过 LANTIAN 到达（多路径）
    {"prefix": "172.21.4201.0/24","path": ["4242422547", "4242420927", "4242424200"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},
    # GAMMA-NET 也可通过 PEERABLE 到达
    {"prefix": "172.21.4801.0/24","path": ["4242421376", "4242423750", "4242429999", "4242424800"],  "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": False, "roa": "valid"},
    # PILOT-NET 也可通过 KIOUBIT 到达
    {"prefix": "172.21.4501.0/24","path": ["4242423914", "4242422464", "4242424500"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "unknown"},

    # === 跨 Tier1 对等路径（Tier1 之间互相中转）===
    # BURBLE → KIOUBIT 对等：通过 KIOUBIT 到达 ALICE-NET 的备用路径
    {"prefix": "172.20.4401.0/24","path": ["4242422601", "4242423914", "4242420666"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # KIOUBIT → LANTIAN 对等：通过 LANTIAN 到达 JPIA 的备用路径
    {"prefix": "172.20.4402.0/24","path": ["4242423914", "4242422547", "4242423088"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # BURBLE → PEERABLE 对等：通过 PEERABLE 到达 SUNNET 的备用路径
    {"prefix": "172.20.4403.0/24","path": ["4242422601", "4242421376", "4242423750"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # LANTIAN → PEERABLE 对等
    {"prefix": "172.20.4404.0/24","path": ["4242422547", "4242421376", "4242422464"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},

    # === 新增边缘 AS 路由 ===
    # NOVA-NET (4242425000) — 通过 BURBLE → ALICE → SMALL-NET（4跳）
    {"prefix": "172.21.500.0/24", "path": ["4242422601", "4242420666", "4242427777", "4242425000"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5000::/48",  "path": ["4242423914", "4242420666", "4242427777", "4242425000"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # NOVA-NET 备用路径 — 通过 LANTIAN → JPIA → TINY-NET（不同路径到达同一目的）
    {"prefix": "172.21.501.0/24", "path": ["4242422547", "4242423088", "4242428888", "4242425000"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},

    # PHOENIX-NET (4242425100) — 通过 KIOUBIT → ROUTER-SERVER（3跳）
    {"prefix": "172.22.510.0/24", "path": ["4242423914", "4242422464", "4242425100"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5100::/48",  "path": ["4242421376", "4242422464", "4242425100"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    # PHOENIX-NET 备用路径 — 通过 BURBLE → NEXUS
    {"prefix": "172.22.511.0/24", "path": ["4242422601", "4242420927", "4242425100"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "unknown"},

    # ORION-NET (4242425200) — 通过 PEERABLE → SUNNET → EDGE-NET（4跳）
    {"prefix": "172.23.520.0/24", "path": ["4242421376", "4242423750", "4242429999", "4242425200"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5200::/48",  "path": ["4242422601", "4242423750", "4242429999", "4242425200"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    # ORION-NET 备用路径 — 通过 LANTIAN → JPIA
    {"prefix": "172.23.521.0/24", "path": ["4242422547", "4242423088", "4242425200"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},

    # LYRA-NET (4242425300) — 通过 BURBLE → ALICE（3跳，直连 ALICE）
    {"prefix": "172.21.530.0/24", "path": ["4242422601", "4242420666", "4242425300"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5300::/48",  "path": ["4242423914", "4242420666", "4242425300"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # LYRA-NET 备用路径 — 通过 KIOUBIT → ROUTER-SERVER
    {"prefix": "172.21.531.0/24", "path": ["4242423914", "4242422464", "4242425300"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},

    # DRACO-NET (4242425400) — 通过 LANTIAN → SUNNET（3跳）
    {"prefix": "172.22.540.0/24", "path": ["4242422547", "4242423750", "4242425400"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5400::/48",  "path": ["4242423914", "4242423750", "4242425400"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # DRACO-NET 备用路径 — 通过 PEERABLE → SUNNET
    {"prefix": "172.22.541.0/24", "path": ["4242421376", "4242423750", "4242425400"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": False, "roa": "unknown"},

    # HYDRA-NET (4242425500) — 通过 BURBLE → NEXUS → FAR-NET（4跳）
    {"prefix": "172.21.550.0/24", "path": ["4242422601", "4242420927", "4242425555", "4242425500"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5500::/48",  "path": ["4242423914", "4242420927", "4242425555", "4242425500"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # HYDRA-NET 备用路径 — 通过 PEERABLE → SUNNET → EDGE-NET
    {"prefix": "172.21.551.0/24", "path": ["4242421376", "4242423750", "4242429999", "4242425500"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": False, "roa": "valid"},

    # PEGASUS-NET (4242425600) — 通过 KIOUBIT → ALICE → SMALL-NET → INDIE-NET（5跳，最长路径之一）
    {"prefix": "172.22.560.0/24", "path": ["4242423914", "4242420666", "4242427777", "4242427770", "4242425600"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5600::/48",  "path": ["4242422601", "4242420666", "4242427777", "4242427770", "4242425600"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    # PEGASUS-NET 备用路径 — 通过 LANTIAN → JPIA → TINY-NET → MESH-NET
    {"prefix": "172.22.561.0/24", "path": ["4242422547", "4242423088", "4242428888", "4242422233", "4242425600"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "unknown"},

    # CYGNUS-NET (4242425700) — 通过 PEERABLE → SUNNET → EDGE-NET → STAR-NET（5跳）
    {"prefix": "172.23.570.0/24", "path": ["4242421376", "4242423750", "4242429999", "4242423344", "4242425700"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:5700::/48",  "path": ["4242422601", "4242423750", "4242429999", "4242423344", "4242425700"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    # CYGNUS-NET 备用路径 — 通过 KIOUBIT → ROUTER-SERVER
    {"prefix": "172.23.571.0/24", "path": ["4242423914", "4242422464", "4242425700"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},

    # === 更多多路径交叉（让 AS Path 搜索产生丰富的多路径结果）===
    # STAR-NET 也可通过 KIOUBIT → ALICE 到达
    {"prefix": "172.23.3441.0/24","path": ["4242423914", "4242420666", "4242427777", "4242423344"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # TINY-NET 也可通过 BURBLE → ALICE 到达
    {"prefix": "172.20.881.0/24", "path": ["4242422601", "4242420666", "4242428888"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # MESH-NET 也可通过 PEERABLE → SUNNET 到达
    {"prefix": "172.22.2331.0/24","path": ["4242421376", "4242423750", "4242429999", "4242422233"],  "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": False, "roa": "valid"},
    # REMOTE-NET 也可通过 LANTIAN → NEXUS 到达
    {"prefix": "172.21.441.0/24", "path": ["4242422547", "4242420927", "4242424444"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},
    # FAR-NET 也可通过 KIOUBIT → ROUTER-SERVER 到达
    {"prefix": "172.21.552.0/24", "path": ["4242423914", "4242422464", "4242425555"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # ISOLATED-NET 也可通过 BURBLE → SUNNET 到达
    {"prefix": "172.22.661.0/24", "path": ["4242422601", "4242423750", "4242426666"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},

    # === 跨 Tier1 多路径路由（同一对 Tier1 间存在多条路径）===
    # BURBLE → KIOUBIT 多路径：通过不同下游到达同一目的
    {"prefix": "172.20.4411.0/24","path": ["4242422601", "4242423914", "4242420666", "4242427777"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "172.20.4412.0/24","path": ["4242422601", "4242423914", "4242422464"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:4412::/48",  "path": ["4242422601", "4242423914", "4242423088"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # KIOUBIT → LANTIAN 多路径
    {"prefix": "172.20.4421.0/24","path": ["4242423914", "4242422547", "4242423088", "4242428888"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "172.20.4422.0/24","path": ["4242423914", "4242422547", "4242423750"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:4422::/48",  "path": ["4242423914", "4242422547", "4242420927"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # BURBLE → PEERABLE 多路径
    {"prefix": "172.20.4431.0/24","path": ["4242422601", "4242421376", "4242423750", "4242429999"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "172.20.4432.0/24","path": ["4242422601", "4242421376", "4242422464"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:4432::/48",  "path": ["4242422601", "4242421376", "4242423088"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # LANTIAN → PEERABLE 多路径
    {"prefix": "172.20.4441.0/24","path": ["4242422547", "4242421376", "4242423750", "4242425400"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "172.20.4442.0/24","path": ["4242422547", "4242421376", "4242422464", "4242424600"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},
    # 三 Tier1 级联路径（BURBLE → KIOUBIT → LANTIAN）
    {"prefix": "172.20.4451.0/24","path": ["4242422601", "4242423914", "4242422547", "4242423088", "4242423476"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:4451::/48",  "path": ["4242422601", "4242423914", "4242422547", "4242423750", "4242424700"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # 三 Tier1 级联路径（KIOUBIT → BURBLE → PEERABLE）
    {"prefix": "172.20.4452.0/24","path": ["4242423914", "4242422601", "4242421376", "4242423750", "4242424400"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:4452::/48",  "path": ["4242423914", "4242422601", "4242421376", "4242422464", "4242425100"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # 四 Tier1 全穿路径（BURBLE → KIOUBIT → LANTIAN → PEERABLE）
    {"prefix": "172.20.4461.0/24","path": ["4242422601", "4242423914", "4242422547", "4242421376", "4242423750", "4242425200"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:4461::/48",  "path": ["4242422601", "4242423914", "4242422547", "4242421376", "4242422464", "4242425300"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # 反向四 Tier1（PEERABLE → LANTIAN → KIOUBIT → BURBLE）
    {"prefix": "172.20.4462.0/24","path": ["4242421376", "4242422547", "4242423914", "4242422601", "4242420666", "4242425300"],  "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": False, "roa": "valid"},

    # === AS Prepending 示例（同一 ASN 在路径中重复出现，模拟流量工程）===
    # BURBLE 做 AS Prepending：路径中出现两次 BURBLE
    {"prefix": "172.21.1001.0/24","path": ["4242422601", "4242422601", "4242420666", "4242427777"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1001::/48",  "path": ["4242422601", "4242422601", "4242420666", "4242427777"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    # KIOUBIT 做 3x Prepending：路径中出现三次 KIOUBIT
    {"prefix": "172.21.1002.0/24","path": ["4242423914", "4242423914", "4242423914", "4242422464", "4242424600"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1002::/48",  "path": ["4242423914", "4242423914", "4242423914", "4242422464", "4242424600"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "unknown"},
    # ALICE 做 Prepending（中间节点 prepending）
    {"prefix": "172.21.1003.0/24","path": ["4242422601", "4242420666", "4242420666", "4242427777", "4242427770"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:1003::/48",  "path": ["4242423914", "4242420666", "4242420666", "4242427777", "4242427770"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # LANTIAN 做 2x Prepending
    {"prefix": "172.21.1004.0/24","path": ["4242422547", "4242422547", "4242423088", "4242428888"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:1004::/48",  "path": ["4242422547", "4242422547", "4242423088", "4242428888"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    # 多节点同时 Prepending（BURBLE + ALICE 都 prepending）
    {"prefix": "172.21.1005.0/24","path": ["4242422601", "4242422601", "4242420666", "4242420666", "4242427777", "4242427770", "4242424100"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "fd00:1005::/48",  "path": ["4242423914", "4242423914", "4242420666", "4242420666", "4242427777", "4242427770", "4242424100"],  "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},

    # === 新 Transit ASN 路由（ZENITH-NET / APEX-NET 作为新二级中转）===
    # ZENITH-NET (4242426100) — 通过 BURBLE 中转
    {"prefix": "172.21.610.0/24", "path": ["4242422601", "4242426100"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6100::/48",  "path": ["4242423914", "4242426100"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # APEX-NET (4242426200) — 通过 LANTIAN 中转
    {"prefix": "172.22.620.0/24", "path": ["4242422547", "4242426200"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6200::/48",  "path": ["4242421376", "4242426200"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "unknown"},
    # ZENITH 作为中转到达边缘 AS
    {"prefix": "172.21.611.0/24", "path": ["4242422601", "4242426100", "4242425800"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6101::/48",  "path": ["4242423914", "4242426100", "4242425800"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # APEX 作为中转到达边缘 AS
    {"prefix": "172.22.621.0/24", "path": ["4242422547", "4242426200", "4242425900"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6201::/48",  "path": ["4242421376", "4242426200", "4242425900"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},

    # === 新边缘 AS 路由（多路径到达，增加搜索复杂度）===
    # NEBULA-NET (4242425800) — 多路径
    {"prefix": "172.21.580.0/24", "path": ["4242423914", "4242426100", "4242425800"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # PULSAR-NET (4242425900) — 多路径
    {"prefix": "172.22.590.0/24", "path": ["4242422601", "4242426200", "4242425900"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "unknown"},
    # QUASAR-NET (4242426000) — 通过 BURBLE → ZENITH → NEBULA（4跳）
    {"prefix": "172.21.600.0/24", "path": ["4242422601", "4242426100", "4242425800", "4242426000"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6000::/48",  "path": ["4242423914", "4242426100", "4242425800", "4242426000"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # VORTEX-NET (4242426300) — 通过 LANTIAN → APEX → PULSAR（4跳）
    {"prefix": "172.22.630.0/24", "path": ["4242422547", "4242426200", "4242425900", "4242426300"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6300::/48",  "path": ["4242421376", "4242426200", "4242425900", "4242426300"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    # ECLIPSE-NET (4242426400) — 通过 KIOUBIT → ZENITH（3跳）
    {"prefix": "172.21.640.0/24", "path": ["4242423914", "4242426100", "4242426400"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6400::/48",  "path": ["4242422601", "4242426100", "4242426400"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "unknown"},
    # AURORA-NET (4242426500) — 通过 PEERABLE → APEX（3跳）
    {"prefix": "172.23.650.0/24", "path": ["4242421376", "4242426200", "4242426500"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6500::/48",  "path": ["4242422547", "4242426200", "4242426500"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},
    # COSMOS-NET (4242426600) — 通过 BURBLE → ZENITH → QUASAR（4跳）
    {"prefix": "172.21.660.0/24", "path": ["4242422601", "4242426100", "4242425800", "4242426000", "4242426600"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6600::/48",  "path": ["4242423914", "4242426100", "4242425800", "4242426000", "4242426600"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": True,  "roa": "valid"},
    # GALAXY-NET (4242426700) — 通过 LANTIAN → APEX → VORTEX（4跳）
    {"prefix": "172.22.670.0/24", "path": ["4242422547", "4242426200", "4242425900", "4242426300", "4242426700"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "fd00:6700::/48",  "path": ["4242421376", "4242426200", "4242425900", "4242426300", "4242426700"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": True,  "roa": "unknown"},

    # === 新旧拓扑交叉路径（连接新增 Transit 与旧 Edge，产生丰富的多路径搜索结果）===
    # NEBULA-NET 也可通过旧路径 BURBLE → ALICE 到达
    {"prefix": "172.21.581.0/24", "path": ["4242422601", "4242420666", "4242427777", "4242425800"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    # PULSAR-NET 也可通过旧路径 KIOUBIT → ROUTER-SERVER 到达
    {"prefix": "172.22.591.0/24", "path": ["4242423914", "4242422464", "4242425900"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # QUASAR-NET 备用路径 — 通过 KIOUBIT → ZENITH
    {"prefix": "172.21.601.0/24", "path": ["4242423914", "4242426100", "4242425800", "4242426000"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "unknown"},
    # ECLIPSE-NET 备用路径 — 通过 PEERABLE → APEX
    {"prefix": "172.21.641.0/24", "path": ["4242421376", "4242426200", "4242426400"],   "via": "fd42:1376::1 on wg-peerable",     "peer": "peer_peerable","metric": "100", "preferred": False, "roa": "valid"},
    # COSMOS-NET 备用路径 — 通过跨 Tier1 KIOUBIT → BURBLE → ZENITH
    {"prefix": "172.21.661.0/24", "path": ["4242423914", "4242422601", "4242426100", "4242425800", "4242426000", "4242426600"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "100", "preferred": False, "roa": "valid"},
    # GALAXY-NET 备用路径 — 通过跨 Tier1 BURBLE → LANTIAN → APEX
    {"prefix": "172.22.671.0/24", "path": ["4242422601", "4242422547", "4242426200", "4242425900", "4242426300", "4242426700"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},

    # === 新 Transit 间对等路径（ZENITH ↔ APEX 互相中转）===
    {"prefix": "172.20.6101.0/24","path": ["4242422601", "4242426100", "4242426200", "4242426500"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": False, "roa": "valid"},
    {"prefix": "172.20.6102.0/24","path": ["4242422547", "4242426200", "4242426100", "4242426400"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": False, "roa": "valid"},

    # === 本机到新 ASN 的路径（确保 MY_ASN 搜索能找到新节点）===
    {"prefix": "172.20.6103.0/24","path": ["4242422601", "4242426100", "4242425800", "4242426000", "4242426600"],  "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "100", "preferred": True,  "roa": "valid"},
    {"prefix": "172.20.6104.0/24","path": ["4242422547", "4242426200", "4242425900", "4242426300", "4242426700"],  "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "100", "preferred": True,  "roa": "valid"},

    # === 同一前缀多路径（模拟 BGP multipath / 多上游到达同一目的地）===
    # anycast DNS 172.20.0.53/32 — 通过 3 个不同 peer 到达，3 条不同 AS Path
    {"prefix": "172.20.0.53/32",  "path": ["4242422601", "4242422688"],                 "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "200", "preferred": False, "roa": "valid"},
    {"prefix": "172.20.0.53/32",  "path": ["4242422547", "4242423914", "4242422688"],   "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "200", "preferred": False, "roa": "valid"},
    # 172.20.77.0/24 — 通过 KIOUBIT 备用路径
    {"prefix": "172.20.77.0/24",  "path": ["4242423914", "4242420666", "4242427777"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "200", "preferred": False, "roa": "valid"},
    # 172.21.10.0/24 — BURBLE 起源前缀，也可通过 LANTIAN 到达
    {"prefix": "172.21.10.0/24",  "path": ["4242422547", "4242422601"],                 "via": "172.22.76.184 on wg-lantian",     "peer": "peer_lantian", "metric": "200", "preferred": False, "roa": "valid"},
    # 172.20.99.0/24 — 通过 KIOUBIT 备用路径（不同 Tier1 中转）
    {"prefix": "172.20.99.0/24",  "path": ["4242423914", "4242423750", "4242429999"],   "via": "fd00:3914::1 on wg-kioubit",      "peer": "peer_kioubit", "metric": "200", "preferred": False, "roa": "invalid"},
    # fd00:7777::/48 — 通过 BURBLE 备用路径
    {"prefix": "fd00:7777::/48",  "path": ["4242422601", "4242420666", "4242427777"],   "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "200", "preferred": False, "roa": "valid"},
    # 172.20.150.0/24 — KIOUBIT 起源，也可通过 BURBLE 到达
    {"prefix": "172.20.150.0/24", "path": ["4242422601", "4242423914"],                 "via": "fd42:4242:2601::1 on wg-burble",   "peer": "peer_burble",  "metric": "200", "preferred": False, "roa": "valid"},
]

# 前缀 whois（inetnum/inet6num）样例 —— 扩展覆盖更多前缀
PREFIX_WHOIS = {
    "172.21.10.0/24": {"netname": "BURBLE-NETWORK", "descr": "burble.dn42", "admin-c": "BURBLE-DN42", "mnt-by": "BURBLE-MNT", "cidr": "172.21.10.0/24", "created": "2022-03-14"},
    "172.22.114.0/24": {"netname": "LANTIAN-NET", "descr": "Lan Tian @ lantian.pub", "admin-c": "LANTIAN-DN42", "mnt-by": "LANTIAN-MNT", "cidr": "172.22.114.0/24", "created": "2020-11-02"},
    "172.23.24.0/24": {"netname": "MY-NET", "descr": "My DN42 Network", "admin-c": "ME-DN42", "mnt-by": "MY-MNT", "cidr": "172.23.24.0/24", "created": "2024-01-20"},
    "172.20.44.0/24": {"netname": "ALICE-NET", "descr": "Alice's Lab", "admin-c": "ALICE-DN42", "mnt-by": "ALICE-MNT", "cidr": "172.20.44.0/24", "created": "2023-06-08"},
    "172.20.150.0/24": {"netname": "KIOUBIT-NET", "descr": "Kioubit DN42", "admin-c": "KIOUBIT-DN42", "mnt-by": "KIOUBIT-MNT", "cidr": "172.20.150.0/24", "created": "2021-08-15"},
    "172.21.37.0/24": {"netname": "PEERABLE-NET", "descr": "Peerable Network", "admin-c": "PEERABLE-DN42", "mnt-by": "PEERABLE-MNT", "cidr": "172.21.37.0/24", "created": "2022-11-30"},
    "172.20.77.0/24": {"netname": "SMALL-NET", "descr": "Small Network", "admin-c": "SMALL-DN42", "mnt-by": "SMALL-MNT", "cidr": "172.20.77.0/24", "created": "2023-09-12"},
    "172.20.88.0/24": {"netname": "TINY-NET", "descr": "Tiny Network", "admin-c": "TINY-DN42", "mnt-by": "TINY-MNT", "cidr": "172.20.88.0/24", "created": "2024-02-01"},
    "172.20.99.0/24": {"netname": "EDGE-NET", "descr": "Edge Network", "admin-c": "EDGE-DN42", "mnt-by": "EDGE-MNT", "cidr": "172.20.99.0/24", "created": "2023-12-15"},
    "172.21.44.0/24": {"netname": "REMOTE-NET", "descr": "Remote Network", "admin-c": "REMOTE-DN42", "mnt-by": "REMOTE-MNT", "cidr": "172.21.44.0/24", "created": "2023-04-22"},
    "172.21.55.0/24": {"netname": "FAR-NET", "descr": "Far Away Network", "admin-c": "FAR-DN42", "mnt-by": "FAR-MNT", "cidr": "172.21.55.0/24", "created": "2024-03-10"},
    "172.22.66.0/24": {"netname": "ISOLATED-NET", "descr": "Isolated Network", "admin-c": "ISOLATED-DN42", "mnt-by": "ISOLATED-MNT", "cidr": "172.22.66.0/24", "created": "2023-07-18"},
    "172.21.816.0/24": {"netname": "SERVING-NET", "descr": "Serving Network", "admin-c": "SERVING-DN42", "mnt-by": "SERVING-MNT", "cidr": "172.21.816.0/24", "created": "2023-10-05"},
    "172.20.108.0/24": {"netname": "GAME-NET", "descr": "Gaming Network", "admin-c": "GAME-DN42", "mnt-by": "GAME-MNT", "cidr": "172.20.108.0/24", "created": "2024-01-08"},
    "172.22.926.0/24": {"netname": "MEDIA-NET", "descr": "Media Network", "admin-c": "MEDIA-DN42", "mnt-by": "MEDIA-MNT", "cidr": "172.22.926.0/24", "created": "2023-11-20"},
    "172.21.476.0/24": {"netname": "LAB-NET", "descr": "Lab Network", "admin-c": "LAB-DN42", "mnt-by": "LAB-MNT", "cidr": "172.21.476.0/24", "created": "2024-04-15"},
    "172.20.410.0/24": {"netname": "CLOUD-NET", "descr": "Cloud Network", "admin-c": "CLOUD-DN42", "mnt-by": "CLOUD-MNT", "cidr": "172.20.410.0/24", "created": "2024-05-01"},
    "172.22.490.0/24": {"netname": "OMEGA-NET", "descr": "Omega Network", "admin-c": "OMEGA-DN42", "mnt-by": "OMEGA-MNT", "cidr": "172.22.490.0/24", "created": "2024-06-10"},
    "172.21.1001.0/24": {"netname": "PREPEND-TEST", "descr": "AS Prepending Test Network", "admin-c": "BURBLE-DN42", "mnt-by": "BURBLE-MNT", "cidr": "172.21.1001.0/24", "created": "2024-07-01"},
    "172.21.610.0/24": {"netname": "ZENITH-NET", "descr": "Zenith Transit Network", "admin-c": "ZENITH-DN42", "mnt-by": "ZENITH-MNT", "cidr": "172.21.610.0/24", "created": "2024-07-15"},
    "172.22.620.0/24": {"netname": "APEX-NET", "descr": "Apex Transit Network", "admin-c": "APEX-DN42", "mnt-by": "APEX-MNT", "cidr": "172.22.620.0/24", "created": "2024-07-20"},
    "172.21.580.0/24": {"netname": "NEBULA-NET", "descr": "Nebula Network", "admin-c": "NEBULA-DN42", "mnt-by": "NEBULA-MNT", "cidr": "172.21.580.0/24", "created": "2024-08-01"},
    "172.22.590.0/24": {"netname": "PULSAR-NET", "descr": "Pulsar Network", "admin-c": "PULSAR-DN42", "mnt-by": "PULSAR-MNT", "cidr": "172.22.590.0/24", "created": "2024-08-05"},
    "172.21.600.0/24": {"netname": "QUASAR-NET", "descr": "Quasar Network", "admin-c": "QUASAR-DN42", "mnt-by": "QUASAR-MNT", "cidr": "172.21.600.0/24", "created": "2024-08-10"},
    "172.22.630.0/24": {"netname": "VORTEX-NET", "descr": "Vortex Network", "admin-c": "VORTEX-DN42", "mnt-by": "VORTEX-MNT", "cidr": "172.22.630.0/24", "created": "2024-08-15"},
    "172.21.640.0/24": {"netname": "ECLIPSE-NET", "descr": "Eclipse Network", "admin-c": "ECLIPSE-DN42", "mnt-by": "ECLIPSE-MNT", "cidr": "172.21.640.0/24", "created": "2024-08-20"},
    "172.23.650.0/24": {"netname": "AURORA-NET", "descr": "Aurora Network", "admin-c": "AURORA-DN42", "mnt-by": "AURORA-MNT", "cidr": "172.23.650.0/24", "created": "2024-08-25"},
    "172.21.660.0/24": {"netname": "COSMOS-NET", "descr": "Cosmos Network", "admin-c": "COSMOS-DN42", "mnt-by": "COSMOS-MNT", "cidr": "172.21.660.0/24", "created": "2024-09-01"},
    "172.22.670.0/24": {"netname": "GALAXY-NET", "descr": "Galaxy Network", "admin-c": "GALAXY-DN42", "mnt-by": "GALAXY-MNT", "cidr": "172.22.670.0/24", "created": "2024-09-05"},
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


# ====================== 互联网交换点（IX/IXP）数据 ======================
# 每个成员 ASN 均来自上方 ASN_NAMES，确保名称可解析、与 ROUTES 自洽。
# 覆盖地区：欧洲 / 亚洲 / 北美 / 南美 / 大洋洲
IX_DATA = [
    {
        "id": "dn42-ix-eu",
        "name": "DN42-IX Europe",
        "city": "Frankfurt, DE",
        "country": "DE",
        "ipv4_prefix": "172.20.0.0/24",
        "ipv6_prefix": "fd42:4242:0099::/64",
        "members": ["4242422601", "4242423914", "4242422547", "4242421376", "4242420666"],
        "route_server": "4242422601",
        "peering_policy": "open",
        "traffic": "1.2 Gbps",
        "established": "2019-01-15",
    },
    {
        "id": "dn42-ix-asia",
        "name": "DN42-IX Asia",
        "city": "Tokyo, JP",
        "country": "JP",
        "ipv4_prefix": "172.22.108.0/24",
        "ipv6_prefix": "fd42:4242:0108::/64",
        "members": [
            "4242423088", "4242422547", "4242423750",
            "4242422601", "4242423914", "4242422464",
        ],
        "route_server": "4242423088",
        "peering_policy": "open",
        "traffic": "850 Mbps",
        "established": "2020-05-20",
    },
    {
        "id": "dn42-ix-na",
        "name": "DN42-IX North America",
        "city": "New York, US",
        "country": "US",
        "ipv4_prefix": "172.23.101.0/24",
        "ipv6_prefix": "fd42:4242:0101::/64",
        "members": [
            "4242421376", "4242422601", "4242423914", "4242420666",
            "4242420927", "4242426100", "4242426200",
        ],
        "route_server": "4242421376",
        "peering_policy": "selective",
        "traffic": "1.5 Gbps",
        "established": "2019-11-03",
    },
    {
        "id": "dn42-ix-sa",
        "name": "DN42-IX South America",
        "city": "Sao Paulo, BR",
        "country": "BR",
        "ipv4_prefix": "172.20.199.0/24",
        "ipv6_prefix": "fd42:4242:0199::/64",
        "members": [
            "4242423750", "4242423088", "4242422547",
            "4242429999", "4242425000", "4242421234",
        ],
        "route_server": "4242423750",
        "peering_policy": "open",
        "traffic": "430 Mbps",
        "established": "2021-03-08",
    },
    {
        "id": "dn42-ix-oc",
        "name": "DN42-IX Oceania",
        "city": "Sydney, AU",
        "country": "AU",
        "ipv4_prefix": "172.21.166.0/24",
        "ipv6_prefix": "fd42:4242:0166::/64",
        "members": [
            "4242423914", "4242422601", "4242425600",
            "4242425700", "4242426100",
        ],
        "route_server": "4242423914",
        "peering_policy": "open",
        "traffic": "320 Mbps",
        "established": "2022-07-14",
    },
]


# ====================== DNS 模拟记录（按地址/前缀分组）======================
# 键为 IP 地址（亦是其 A/AAAA 记录中的地址）；PTR 为该地址的反向域名。
# 与 ROUTES / PREFIX_WHOIS 中的前缀保持自洽（地址取自对应网络的网关）。
DNS_RECORDS = {
    # === DN42 Anycast DNS 解析器（出现在 ROUTES 中的 anycast 前缀）===
    "172.20.0.53": {
        "PTR": ["dns.dn42"],
        "A": ["172.20.0.53"],
        "AAAA": ["fd42:d42:d42:53::1"],
        "description": "DN42 Anycast DNS Resolver",
    },
    "fd42:d42:d42:53::1": {
        "PTR": ["dns.dn42"],
        "A": ["172.20.0.53"],
        "AAAA": ["fd42:d42:d42:53::1"],
        "description": "DN42 Anycast DNS Resolver (IPv6)",
    },
    # === 本机 MY-NET（4242421234）===
    "172.23.24.1": {
        "PTR": ["node1.my-net.dn42"],
        "A": ["172.23.24.1"],
        "AAAA": ["fd00:1234::1"],
        "description": "MY-NET router (本机)",
    },
    "fd00:1234::1": {
        "PTR": ["node1.my-net.dn42"],
        "A": ["172.23.24.1"],
        "AAAA": ["fd00:1234::1"],
        "description": "MY-NET router (本机, IPv6)",
    },
    # === Tier1 / Transit 网关 ===
    "172.21.10.1": {
        "PTR": ["gw.burble.dn42"],
        "A": ["172.21.10.1"],
        "AAAA": ["fd42:4242:2601::1"],
        "description": "BURBLE gateway",
    },
    "172.22.114.1": {
        "PTR": ["gw.lantian.dn42"],
        "A": ["172.22.114.1"],
        "AAAA": ["fd00:2547::1"],
        "description": "LANTIAN gateway",
    },
    "172.20.150.1": {
        "PTR": ["gw.kioubit.dn42"],
        "A": ["172.20.150.1"],
        "AAAA": ["fd00:3914::1"],
        "description": "KIOUBIT gateway",
    },
    "172.21.37.1": {
        "PTR": ["gw.peerable.dn42"],
        "A": ["172.21.37.1"],
        "AAAA": ["fd42:1376::1"],
        "description": "PEERABLE gateway",
    },
    "172.20.44.1": {
        "PTR": ["gw.alice.dn42"],
        "A": ["172.20.44.1"],
        "AAAA": ["fd00:666::1"],
        "description": "ALICE gateway",
    },
    "172.21.88.1": {
        "PTR": ["gw.jpia.dn42"],
        "A": ["172.21.88.1"],
        "AAAA": ["fd00:3088::1"],
        "description": "JPIA gateway",
    },
    "172.22.75.1": {
        "PTR": ["gw.sunnet.dn42"],
        "A": ["172.22.75.1"],
        "AAAA": ["fd42:3750::1"],
        "description": "SUNNET gateway",
    },
    "172.20.92.1": {
        "PTR": ["gw.nexus.dn42"],
        "A": ["172.20.92.1"],
        "AAAA": ["fd00:927::1"],
        "description": "NEXUS gateway",
    },
    "172.21.610.1": {
        "PTR": ["gw.zenith.dn42"],
        "A": ["172.21.610.1"],
        "AAAA": ["fd00:6100::1"],
        "description": "ZENITH transit gateway",
    },
    "172.22.620.1": {
        "PTR": ["gw.apex.dn42"],
        "A": ["172.22.620.1"],
        "AAAA": ["fd00:6200::1"],
        "description": "APEX transit gateway",
    },
}


# ====================== AS Path 分析功能 ======================

def _effective_routes_for(asn: str) -> list:
    """返回对指定 ASN 有效的路由列表。

    若 ASN 是本机（MY_ASN），将本机前插到所有路径开头，
    因为本机是路由接收方，其 ASN 不在 AS_PATH 中，但从全网视角看应位于路径起点。
    """
    if asn == MY_ASN:
        result = []
        for r in ROUTES:
            path = list(r["path"])
            if MY_ASN not in path:
                path = [MY_ASN] + path
            result.append({**r, "path": path})
        return result
    return ROUTES


def as_path_upstreams(asn: str) -> list:
    """从路由表推断 ASN 的上游（path 中出现在它前面的 AS）。"""
    ups = set()
    for r in _effective_routes_for(asn):
        path = r["path"]
        if asn in path:
            i = path.index(asn)
            if i > 0:
                ups.add(path[i - 1])
    return sorted(ups)


def as_path_downstreams(asn: str) -> list:
    """从路由表推断 ASN 的下游（path 中出现在它后面的 AS）。

    使用最后一次出现位置，正确处理 AS Prepending（如 [A, B, B, C] 查 B 时下游为 C）。
    """
    downs = set()
    for r in _effective_routes_for(asn):
        path = r["path"]
        if asn in path:
            # 使用最后一次出现位置，跳过 AS Prepending 的重复
            i = len(path) - 1 - path[::-1].index(asn)
            if i < len(path) - 1:
                downs.add(path[i + 1])
    return sorted(downs)


def as_path_peers(asn: str) -> list:
    """从路由表推断 ASN 的对等方。

    对等方定义：与查询 ASN 拥有共同上游的 AS（即同层 AS）。
    这比"同路径中非上下游"更精确，避免了将远距离 AS 误判为 peer。
    """
    ups = set(as_path_upstreams(asn))
    peers = set()
    # 收集所有路径中，上游与查询 ASN 相同的其他 ASN
    for r in _effective_routes_for(asn):
        path = r["path"]
        if asn not in path:
            continue
        i = path.index(asn)
        # 查找同一路径中、有相同上游（i-1 位置相同）的其他 ASN
        if i > 0:
            my_upstream = path[i - 1]
            # 在其他路径中找同样以 my_upstream 为上游的 ASN
            for r2 in _effective_routes_for(asn):
                p2 = r2["path"]
                for j in range(1, len(p2)):
                    if p2[j - 1] == my_upstream and p2[j] != asn and p2[j] not in ups:
                        peers.add(p2[j])
    return sorted(peers)


def prefixes_originated(asn: str) -> list:
    """ASN 起源的所有前缀（path 最后一个 AS）。"""
    return [r for r in ROUTES if r["path"] and r["path"][-1] == asn]


def as_path_all_paths(asn: str) -> list:
    """获取所有经过该 ASN 的完整 AS 路径（去重）。

    每条路径是一个 AS 列表，如 ["4242421234", "4242422601", "4242420666"]。
    """
    seen = set()
    paths = []
    for r in _effective_routes_for(asn):
        path = tuple(r["path"])
        if asn in path and path not in seen:
            seen.add(path)
            paths.append(list(path))
    return paths


def as_path_truncated_paths(asn: str) -> list:
    """在第一个 Tier1 处截断 AS 路径（模仿 bgp.tools Network Policy）。

    例如路径 ["4242421234", "4242422601", "4242420666", "4242427777"]
    截断为 ["4242421234", "4242422601"]（4242422601 是从左到右第一个 Tier1）。
    从查看者视角（最左 AS），截断到第一个 Tier1 边界。
    """
    paths = as_path_all_paths(asn)
    truncated = []
    seen = set()
    for path in paths:
        # 从左往右找第一个 Tier1（查看者视角的最近 Tier1 边界）
        cut_idx = -1
        for i in range(len(path)):
            if path[i] in DN42_TIER1:
                cut_idx = i
                break
        if cut_idx >= 0:
            t = tuple(path[:cut_idx + 1])
        else:
            t = tuple(path)
        if t not in seen:
            seen.add(t)
            truncated.append(list(t))
    return truncated


def as_path_network_policies(asn: str) -> list:
    """按截断后的 AS 路径分组，生成 Network Policy（模仿 bgp.tools）。

    返回每个策略的名称、截断路径、关联前缀列表。
    """
    import hashlib

    truncated = as_path_truncated_paths(asn)
    # 生成稳定的策略名称（基于路径哈希）
    adjectives = ["mystifying", "nostalgic", "eager", "tranquil", "vibrant",
                  "serene", "curious", "gentle", "swift", "hidden",
                  "golden", "crimson", "silver", "ancient", "distant"]
    nouns = ["ride", "river", "trail", "voyage", "journey", "path",
             "current", "breeze", "horizon", "meadow", "canyon",
             "summit", "valley", "bridge", "forest"]

    policies = []
    for i, path in enumerate(truncated):
        # 基于路径内容生成确定性随机名
        h = int(hashlib.md5(str(path).encode()).hexdigest(), 16)
        adj = adjectives[h % len(adjectives)]
        noun = nouns[(h >> 8) % len(nouns)]
        name = f"{adj}_{noun}"

        # 找到属于该策略的前缀
        path_tuple = tuple(path)
        related_prefixes = []
        for r in _effective_routes_for(asn):
            rp = tuple(r["path"])
            # 截断到相同的 Tier1（从左往右找第一个 Tier1）
            cut = -1
            for j in range(len(rp)):
                if rp[j] in DN42_TIER1:
                    cut = j
                    break
            truncated_rp = tuple(rp[:cut + 1]) if cut >= 0 else rp
            if truncated_rp == path_tuple:
                related_prefixes.append(r["prefix"])

        policies.append({
            "name": name,
            "path": path,
            "prefixes": related_prefixes,
            "prefix_count": len(related_prefixes),
        })
    return policies


def as_path_graph(asn: str) -> dict:
    """生成 AS Path 图的节点和边数据，用于前端可视化。

    返回:
        {
            "nodes": [{"id": "4242422601", "name": "BURBLE", "type": "tier1", ...}],
            "edges": [{"source": "4242421234", "target": "4242422601", "prefixes": [...]}],
            "origin": "4242421234",
            "policies": [...],
            "upstreams": [...],
            "downstreams": [...],
        }
    """
    paths = as_path_all_paths(asn)

    # 收集所有涉及到的 ASN
    all_asns = set()
    for path in paths:
        all_asns.update(path)

    # 生成节点
    nodes = []
    for a in all_asns:
        node_type = ASN_TYPES.get(a, "edge")
        nodes.append({
            "id": a,
            "name": ASN_NAMES.get(a, f"AS{a}"),
            "type": node_type,
            "is_origin": a == asn,
            "is_tier1": a in DN42_TIER1,
            "prefix_count": len(prefixes_originated(a)),
        })

    # 生成边（每条边是路径中相邻的 AS 对）
    edge_map = {}  # (src, dst) -> set of prefixes
    for r in _effective_routes_for(asn):
        path = r["path"]
        if asn not in path:
            continue
        for i in range(len(path) - 1):
            key = (path[i], path[i + 1])
            if key not in edge_map:
                edge_map[key] = set()
            edge_map[key].add(r["prefix"])

    edges = []
    for (src, dst), prefixes in edge_map.items():
        edges.append({
            "source": src,
            "target": dst,
            "prefixes": sorted(prefixes),
            "prefix_count": len(prefixes),
        })

    return {
        "origin": asn,
        "origin_name": ASN_NAMES.get(asn, f"AS{asn}"),
        "nodes": nodes,
        "edges": edges,
        "upstreams": [{"asn": u, "name": ASN_NAMES.get(u)} for u in as_path_upstreams(asn)],
        "downstreams": [{"asn": d, "name": ASN_NAMES.get(d)} for d in as_path_downstreams(asn)],
        "peers": [{"asn": p, "name": ASN_NAMES.get(p)} for p in as_path_peers(asn)],
        "policies": as_path_network_policies(asn),
        "total_paths": len(paths),
        "total_prefixes": len(prefixes_originated(asn)),
    }


# ====================== 全网 AS Path 搜索 ======================

def search_as_paths(query: str) -> dict:
    """搜索全网 AS Path，查找两个 ASN 之间的路径。

    支持:
    - "AS1234 AS5678" 或 "1234 5678" — 查找两个 ASN 之间的路径
    - "AS1234" — 查找该 ASN 的所有路径
    """
    import re

    # 解析查询（与 search.py 保持一致：允许 1-10 位数字）
    asns = re.findall(r'(?:AS)?(\d{1,10})', query, re.IGNORECASE)

    if not asns:
        return {"error": "无法识别 ASN，请输入如 AS4242421234 或 4242421234 4242422601"}

    if len(asns) == 1:
        # 单个 ASN：返回该 ASN 的完整 AS Path 图
        asn = asns[0]
        if asn not in ASN_NAMES:
            return {"error": f"AS{asn} 不在演示拓扑中"}
        graph = as_path_graph(asn)
        graph["query_type"] = "single"
        return graph

    # 两个 ASN：查找之间的路径
    src, dst = asns[0], asns[1]

    # 边界情况：src == dst
    if src == dst:
        return {"error": f"源 ASN 和目标 ASN 相同（AS{src}），请输入两个不同的 ASN"}

    if src not in ASN_NAMES or dst not in ASN_NAMES:
        missing = src if src not in ASN_NAMES else dst
        return {"error": f"AS{missing} 不在演示拓扑中（可用 ASN: {', '.join(list(ASN_NAMES)[:8])}...）"}

    # 构建有效路由列表：若某个 ASN 是本机（MY_ASN），则将其前插到所有路径
    # 复用 _effective_routes_for 逻辑保持一致性
    need_my_asn = (src == MY_ASN or dst == MY_ASN)
    effective_routes = []
    for r in ROUTES:
        path = list(r["path"])
        if need_my_asn and MY_ASN not in path:
            path = [MY_ASN] + path
        effective_routes.append({**r, "path": path})

    # 在所有路由路径中查找 src→dst 或 dst→src 的路径
    found_paths = []
    for r in effective_routes:
        path = r["path"]
        if src in path and dst in path:
            si = path.index(src)
            di = path.index(dst)
            # 提取 src 到 dst 之间的子路径
            if si < di:
                sub_path = path[si:di + 1]
            else:
                sub_path = path[di:si + 1]
            found_paths.append({
                "path": sub_path,
                "prefix": r["prefix"],
                "full_path": path,
                "direction": "src→dst" if si < di else "dst→src",
            })

    # 生成路径图
    path_asns = set()
    for fp in found_paths:
        path_asns.update(fp["path"])

    nodes = []
    for a in path_asns:
        node_type = ASN_TYPES.get(a, "edge")
        nodes.append({
            "id": a,
            "name": ASN_NAMES.get(a, f"AS{a}"),
            "type": node_type,
            "is_origin": a == src or a == dst,
            "is_tier1": a in DN42_TIER1,
        })

    edges = []
    edge_seen = set()
    for fp in found_paths:
        p = fp["path"]
        for i in range(len(p) - 1):
            key = (p[i], p[i + 1])
            if key not in edge_seen:
                edge_seen.add(key)
                edges.append({
                    "source": p[i],
                    "target": p[i + 1],
                    "prefix": fp["prefix"],
                })

    return {
        "query_type": "pair",
        "src": src,
        "src_name": ASN_NAMES.get(src),
        "dst": dst,
        "dst_name": ASN_NAMES.get(dst),
        "found": len(found_paths) > 0,
        "paths": found_paths,
        "nodes": nodes,
        "edges": edges,
        "total_paths": len(found_paths),
    }


# ====================== 模拟 whois 输出 ======================
def aut_num_whois(asn: str) -> str:
    """构造 DN42 aut-num 对象（真实 whois 输出风格）。"""
    name = ASN_NAMES.get(asn, f"AS{asn}")
    admin = name.replace("-MNT", "-DN42").replace("-NET", "-DN42")
    mnt = name if name.endswith('MNT') else name + '-MNT'
    return (
        f"aut-num:            AS{asn}\n"
        f"as-name:            {name}\n"
        f"descr:              {name} DN42 network\n"
        f"admin-c:            {admin}\n"
        f"tech-c:             {admin}\n"
        f"mnt-by:             {mnt}\n"
        f"source:             DN42"
    )


def inetnum_whois(prefix: str) -> str:
    """构造 DN42 inetnum/inet6num 对象。"""
    w = PREFIX_WHOIS.get(prefix)
    if not w:
        return f"% No entries found for {prefix} in DN42 registry."
    family = "inet6num" if ":" in prefix else "inetnum"
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


# ====================== 互联网交换点（IX/IXP）查询功能 ======================

def ix_list():
    """返回所有 IX 的简要信息列表。

    不展开成员详情，仅给出成员数量与路由服务器名称，便于列表展示。
    """
    result = []
    for ix in IX_DATA:
        rs = ix["route_server"]
        result.append({
            "id": ix["id"],
            "name": ix["name"],
            "city": ix["city"],
            "country": ix["country"],
            "ipv4_prefix": ix["ipv4_prefix"],
            "ipv6_prefix": ix["ipv6_prefix"],
            "member_count": len(ix["members"]),
            "route_server": rs,
            "route_server_name": ASN_NAMES.get(rs, f"AS{rs}"),
            "peering_policy": ix["peering_policy"],
            "traffic": ix["traffic"],
            "established": ix["established"],
        })
    return result


def ix_view(ix_id):
    """返回单个 IX 的详细信息，包括成员 ASN 的名称和起源前缀数。

    若 ix_id 不存在返回 None。成员中标注是否为该 IX 的路由服务器，
    并附带该 ASN 起源的前缀列表与数量（复用 prefixes_originated）。
    """
    ix = next((x for x in IX_DATA if x["id"] == ix_id), None)
    if not ix:
        return None

    rs = ix["route_server"]
    members = []
    for asn in ix["members"]:
        originated = prefixes_originated(asn)
        members.append({
            "asn": asn,
            "name": ASN_NAMES.get(asn, f"AS{asn}"),
            "type": ASN_TYPES.get(asn, "edge"),
            "is_route_server": asn == rs,
            "originated_prefix_count": len(originated),
            "originated_prefixes": [r["prefix"] for r in originated],
        })

    return {
        "id": ix["id"],
        "name": ix["name"],
        "city": ix["city"],
        "country": ix["country"],
        "ipv4_prefix": ix["ipv4_prefix"],
        "ipv6_prefix": ix["ipv6_prefix"],
        "route_server": rs,
        "route_server_name": ASN_NAMES.get(rs, f"AS{rs}"),
        "peering_policy": ix["peering_policy"],
        "traffic": ix["traffic"],
        "established": ix["established"],
        "member_count": len(members),
        "members": members,
    }


def ix_for_asn(asn):
    """返回该 ASN 参与的所有 IX（简要信息）。

    若该 ASN 是某 IX 的路由服务器，对应条目标记 is_route_server=True。
    若未参与任何 IX，返回空列表。
    """
    result = []
    for ix in IX_DATA:
        if asn in ix["members"]:
            rs = ix["route_server"]
            result.append({
                "id": ix["id"],
                "name": ix["name"],
                "city": ix["city"],
                "country": ix["country"],
                "ipv4_prefix": ix["ipv4_prefix"],
                "ipv6_prefix": ix["ipv6_prefix"],
                "route_server": rs,
                "route_server_name": ASN_NAMES.get(rs, f"AS{rs}"),
                "peering_policy": ix["peering_policy"],
                "traffic": ix["traffic"],
                "established": ix["established"],
                "is_route_server": asn == rs,
                "member_count": len(ix["members"]),
            })
    return result


# ====================== DNS 查询功能 ======================

def dns_lookup(name_or_ip):
    """DNS 查询，支持正向（A/AAAA）和反向（PTR）查找。

    输入可以是：
    - 域名（如 "dns.dn42"）→ 正向查找，返回 A/AAAA 记录
    - IP 地址（如 "172.20.0.53"）→ 反向查找，返回 PTR 记录

    返回 dict，包含 query / type / found 及对应记录字段。
    """
    import ipaddress

    query = (name_or_ip or "").strip()
    if not query:
        return {"query": name_or_ip, "type": "unknown", "found": False}

    # 判断输入是 IP 还是域名
    is_ip = False
    try:
        ipaddress.ip_address(query)
        is_ip = True
    except ValueError:
        is_ip = False

    if is_ip:
        # 反向查找：IP → PTR
        record = DNS_RECORDS.get(query)
        if record:
            return {
                "query": query,
                "type": "PTR",
                "found": True,
                "name": list(record.get("PTR", [])),
                "A": list(record.get("A", [])),
                "AAAA": list(record.get("AAAA", [])),
                "description": record.get("description", ""),
            }
        return {
            "query": query,
            "type": "PTR",
            "found": False,
            "name": [],
            "description": "",
        }

    # 正向查找：域名 → A/AAAA（遍历所有记录，匹配 PTR 中的域名）
    query_lower = query.lower()
    a_records = []
    aaaa_records = []
    description = ""
    for record in DNS_RECORDS.values():
        ptrs = [p.lower() for p in record.get("PTR", [])]
        if query_lower in ptrs:
            a_records.extend(record.get("A", []))
            aaaa_records.extend(record.get("AAAA", []))
            if not description and record.get("description"):
                description = record["description"]

    # 去重并保序
    a_records = list(dict.fromkeys(a_records))
    aaaa_records = list(dict.fromkeys(aaaa_records))
    found = bool(a_records or aaaa_records)
    return {
        "query": query,
        "type": "A/AAAA",
        "found": found,
        "A": a_records,
        "AAAA": aaaa_records,
        "description": description,
    }


def dns_for_prefix(prefix):
    """返回该前缀相关的 DNS 记录。

    给定一个 CIDR 前缀（如 "172.20.0.0/24"），返回所有键 IP 落在该前缀内的
    DNS 记录。也支持直接传入单个 IP（按 /32 或 /128 处理）。
    """
    import ipaddress

    query = (prefix or "").strip()
    if not query:
        return {"prefix": prefix, "records": [], "count": 0}

    # 构造网络对象
    try:
        if "/" in query:
            net = ipaddress.ip_network(query, strict=False)
        else:
            ip = ipaddress.ip_address(query)
            net = ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}", strict=False)
    except ValueError:
        return {"prefix": prefix, "records": [], "count": 0}

    records = []
    for key, record in DNS_RECORDS.items():
        try:
            key_ip = ipaddress.ip_address(key)
        except ValueError:
            # 键不是合法 IP，跳过
            continue
        # 仅比较同版本地址，避免 subnet_of 跨版本抛错
        if key_ip.version != net.version:
            continue
        key_net = ipaddress.ip_network(f"{key_ip}/{key_ip.max_prefixlen}", strict=False)
        if key_net.subnet_of(net) or key_net == net:
            records.append({
                "address": key,
                "PTR": list(record.get("PTR", [])),
                "A": list(record.get("A", [])),
                "AAAA": list(record.get("AAAA", [])),
                "description": record.get("description", ""),
            })

    return {
        "prefix": prefix,
        "records": records,
        "count": len(records),
    }
