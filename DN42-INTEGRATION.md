# DN42 接入方案与全网数据分析报告

## 一、全网数据分析

### 1.1 BGP 路由表概览

| 指标 | 演示模式数据 | 真实 DN42 预期 |
|------|-------------|---------------|
| 路由总数 | 174 条 | ~2,000-3,000 条 |
| IPv4 前缀 | 110 个 | ~1,500 个 |
| IPv6 前缀 | 64 个 | ~1,200 个 |
| BGP Peers | 8 个（6 up / 2 down） | 5-20 个 |
| 覆盖 ASN | 51 个 | 500-800 个 |

### 1.2 ROA 校验统计

| ROA 状态 | 数量 | 占比 | 说明 |
|----------|------|------|------|
| Valid | 155 | 89.1% | 前缀宣告与 ROA 记录一致 |
| Invalid | 2 | 1.1% | 可能存在路由劫持 |
| Unknown | 17 | 9.8% | Registry 中无 ROA 记录 |

### 1.3 AS Path 拓扑分析

**本机 AS4242421234 (MY-NET) 拓扑：**
- 连接节点：51 个 AS
- 起源前缀：4 个
- 下游网络：4 个

**核心中转 AS4242422601 (BURBLE) 拓扑：**
- 上游：2 个 | 下游：9 个 | 对等方：9 个
- 节点类型分布：Edge 32 / Transit 8 / Tier1 4

**拓扑层级结构：**
```
Tier1 (4个核心中转)
├── BURBLE (AS4242422601)
├── KIOUBIT (AS4242423914)
├── LANTIAN (AS4242422547)
└── PEERABLE (AS4242421376)

Transit (8个二级中转)
├── ALICE-NET, DN42-ANYCAST-DNS, JPIA-NET
├── SUNNET, ROUTER-SERVER, NEXUS-NET
└── ZENITH-NET, APEX-NET

Edge (32+ 边缘网络)
└── SMALL-NET, CLOUD-NET, NOVA-NET 等
```

### 1.4 IX/IXP 交换点分析

| IX 名称 | 城市 | 成员数 | 流量 | 建立时间 |
|---------|------|--------|------|----------|
| DN42-IX Europe | Frankfurt, DE | 5 | 1.2 Gbps | 2019-01 |
| DN42-IX Asia | Tokyo, JP | 6 | 850 Mbps | 2020-05 |
| DN42-IX North America | New York, US | 7 | 1.5 Gbps | 2019-11 |
| DN42-IX South America | Sao Paulo, BR | 6 | 430 Mbps | 2021-03 |
| DN42-IX Oceania | Sydney, AU | 5 | 320 Mbps | 2022-07 |

- 总交换点：5 个
- 总成员连接：29 个
- 参与 ASN：16 个
- 覆盖五大洲

### 1.5 DNS 解析分析

演示数据包含 14 条 DNS 记录，覆盖：
- Anycast DNS 解析器（172.20.0.53 / fd42:d42:d42:53::1）
- 各 IX 路由服务器网关
- 直连节点网关（burble、lantian、kioubit 等）
- 中转节点网关（alice、nexus、jpia 等）

---

## 二、DN42 接入方案

### 2.1 注册流程

#### 步骤 1：注册 DN42 Registry

```bash
# 1. 在 https://git.dn42.dev 注册账号
# 2. Fork dn42/registry 仓库
git clone https://git.dn42.dev/<你的用户名>/registry.git
cd registry
```

#### 步骤 2：创建 person 对象

在 `data/person/` 下创建文件 `<昵称>-DN42`：
```
person: Your Name
e-mail: your@email.com
pgp-fingerprint: <你的GPG密钥指纹>
nic-hdl: <昵称>-DN42
mnt-by: <昵称>-MNT
source: DN42
```

#### 步骤 3：创建 mntner 对象

在 `data/mntner/` 下创建文件 `<昵称>-MNT`：
```
mntner: <昵称>-MNT
admin-c: <昵称>-DN42
tech-c: <昵称>-DN42
auth: pgp-fingerprint <你的GPG密钥指纹>
mnt-by: <昵称>-MNT
source: DN42
```

#### 步骤 4：申请 ASN

使用 [DN42 Free ASN Explorer](https://explorer.burble.com/free#/asn) 查找可用 ASN（4242420000-4242423999 范围）。

在 `data/aut-num/` 下创建 `AS424242xxxx`：
```
aut-num: AS4242423999
as-name: AS-FOO-DN42
admin-c: <昵称>-DN42
tech-c: <昵称>-DN42
mnt-by: <昵称>-MNT
source: DN42
```

#### 步骤 5：申请 IP 前缀

**IPv4**（默认 /27，32 个地址）：

在 `data/inetnum/` 下创建 `172.20.150.0_27`：
```
inetnum: 172.20.150.0 - 172.20.150.31
cidr: 172.20.150.0/27
netname: FOO-NETWORK
descr: Network of FOO
country: CN
admin-c: <昵称>-DN42
tech-c: <昵称>-DN42
mnt-by: <昵称>-MNT
status: ASSIGNED
source: DN42
```

**IPv6**（默认 /48）：

在 `data/inet6num/` 下创建对应文件，使用 [ULA 生成器](https://simpledns.com/private-ipv6) 生成随机前缀。

#### 步骤 6：创建 route 对象（ROA 授权）

```
# data/route/172.20.150.0_27
route: 172.20.150.0/27
origin: AS4242423999
max-length: 27
mnt-by: <昵称>-MNT
source: DN42
```

#### 步骤 7：提交签名 PR

```bash
./fmt-my-stuff <昵称>-MNT     # 格式化
./check-my-stuff <昵称>-MNT   # 检查
git add .
git commit -S -m "Add FOO network objects"
git push origin master
# 在 git.dn42.dev 上创建 Pull Request
```

### 2.2 建立隧道（WireGuard）

```bash
# 安装 WireGuard
apt install wireguard wireguard-tools -y

# 生成密钥对
wg genkey | tee private.key | wg pubkey > public.key

# 配置 /etc/wireguard/wg-dn42.conf
[Interface]
PrivateKey = <你的私钥>
Address = 172.20.150.1/32
Address = fd35:4992:6a6d::1/128
ListenPort = 51821

[Peer]
PublicKey = <对端公钥>
Endpoint = <对端IP>:<对端端口>
AllowedIPs = 172.20.x.x/32, fd00:xxxx::/128
PersistentKeepalive = 25

# 启动
wg-quick up wg-dn42
systemctl enable wg-quick@wg-dn42
```

使用 [DN42 Peer Finder](https://peerfinder.dn42.dev/) 查找附近节点。

### 2.3 配置 bird2

#### 安装

```bash
apt install bird2 -y
```

#### 主配置 `/etc/bird/bird.conf`

参见项目 `deploy/bird.conf.example` 文件，关键配置：

```bash
define OWNAS = 4242423999;
define OWNIP = 172.20.150.1;
define OWNIPv6 = fd35:4992:6a6d::1;
define OWNNET = 172.20.150.0/27;
define OWNNETv6 = fd35:4992:6a6d::/48;

router id OWNIP;

# ROA 表
roa4 table dn42_roa;
roa6 table dn42_roa_v6;

# BGP 模板（含 ROA 校验）
template bgp dnpeers {
    local as OWNAS;
    path metric on;
    ipv4 {
        import filter {
            if is_valid_network() && !is_self_net() then {
                if (roa_check(dn42_roa, net, bgp_path.last) != ROA_VALID) then {
                    reject;
                } else accept;
            } else reject;
        };
        import limit 9000 action block;
    };
}

include "/etc/bird/peers/*";
```

#### ROA 表自动更新

```bash
# 添加 cron 任务，每 15 分钟更新 ROA
*/15 * * * * curl -sfSLR -o /etc/bird/roa_dn42.conf -z /etc/bird/roa_dn42.conf \
  https://dn42.burble.com/roa/dn42_roa_bird2_4.conf && birdc configure
```

#### Peer 配置

在 `/etc/bird/peers/` 下为每个 peer 创建配置：
```
protocol bgp BURBLE from dnpeers {
    neighbor <对端IP> as 4242422601;
}
```

#### 创建 dummy 接口（必需）

```bash
ip link add dn42-dummy type dummy
ip link set dev dn42-dummy up
ip addr add dev dn42-dummy 172.20.150.1/27
ip addr add dev dn42-dummy fd35:4992:6a6d::1/48
```

### 2.4 对接 DN42 Route Collector（获取全网数据）

DN42 GRC (Global Route Collector) 收集全网路由，可获取完整 BGP 视图：

| 项目 | 值 |
|------|-----|
| ASN | AS4242422602 |
| Hostname | collector.dn42 |
| IPv4 | 172.20.0.179 |
| IPv6 | fd42:d42:d42:179::1 |

```bash
# bird2 配置 - 连接 GRC
protocol bgp ROUTE_COLLECTOR {
    local as OWNAS;
    neighbor fd42:d42:d42:179::1 as 4242422602;
    multihop;
    ipv4 {
        add paths tx;
        import none;
        export filter { if source ~ [RTS_STATIC, RTS_BGP] then accept; reject; };
    };
    ipv6 {
        add paths tx;
        import none;
        export filter { if source ~ [RTS_STATIC, RTS_BGP] then accept; reject; };
    };
}
```

**查询真实路由数据的方式：**
- Web Looking Glass：https://lg.collector.dn42/
- MRT 数据下载：https://mrt.collector.dn42/master4_latest.mrt.bz2
- SSH 交互查询：`ssh shell@collector.dn42`

### 2.5 从演示模式切换到真实模式

修改环境变量：

```bash
# 关闭演示模式
export BGP_TOOL_DEMO_MODE=false

# 配置本机信息
export BGP_TOOL_NODE_NAME="my-node"
export BGP_TOOL_NODE_ASN="4242423999"
export BGP_TOOL_MY_ASN="4242423999"

# 启动
python3 backend/app.py
```

或修改 `.env` 文件：

```bash
BGP_TOOL_DEMO_MODE=false
BGP_TOOL_NODE_ASN=4242423999
BGP_TOOL_MY_ASN=4242423999
BGP_TOOL_BIRD_SOCKET=/run/bird/bird.ctl
```

### 2.6 部署到 VPS

```bash
# 一键部署
cd bgp-tool
chmod +x deploy/setup.sh
sudo ./deploy/setup.sh

# 或手动部署
pip install -r requirements.txt
sudo cp deploy/bgp-tool.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bgp-tool
sudo systemctl start bgp-tool

# Nginx 反代
sudo cp deploy/nginx.conf /etc/nginx/sites-available/bgp-tool
sudo ln -s /etc/nginx/sites-available/bgp-tool /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 三、系统架构

```
┌─────────────────────────────────────────────┐
│                   用户浏览器                  │
│         bgp.tools 风格 SPA 前端              │
└─────────────────┬───────────────────────────┘
                  │ HTTP
┌─────────────────┴───────────────────────────┐
│              Flask 后端 (app.py)             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│  │Search│ │ AS   │ │Prefix│ │ AS   │       │
│  │      │ │View  │ │View  │ │Path  │       │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘       │
│     │        │        │        │            │
│  ┌──┴────────┴────────┴────────┴──┐        │
│  │     bird.py / demo.py          │        │
│  │  (真实模式 / 演示模式 自动切换)  │        │
│  └──────────────┬─────────────────┘        │
│                 │ birdc                     │
│  ┌──────────────┴─────────────────┐        │
│  │       BIRD2 路由守护进程        │        │
│  │   ROA 校验 / BGP Peering       │        │
│  └──────────────┬─────────────────┘        │
│                 │ WireGuard 隧道            │
└─────────────────┼───────────────────────────┘
                  │
          ┌───────┴───────┐
          │   DN42 网络    │
          │  (BGP Peers)  │
          └───────────────┘
```

## 四、关键资源链接

| 资源 | 地址 |
|------|------|
| DN42 官方文档 | https://www.dn42.dev/howto/Getting-Started |
| Registry 仓库 | https://git.dn42.dev/dn42/registry |
| Bird2 配置指南 | https://wiki.dn42.us/howto/Bird2 |
| ASN/IP 查询 | https://explorer.burble.com/free |
| Peer 查找 | https://peerfinder.dn42.dev/ |
| Route Collector LG | https://lg.collector.dn42/ |
| MRT 数据下载 | https://mrt.collector.dn42/ |
| 本项目仓库 | https://github.com/anncix/bgptools |
