# bgp.tools for DN42

一个**像素级模仿 [bgp.tools](https://bgp.tools)** 界面风格、专为 **DN42 网络**打造的 BGP 数据可视化与 Looking Glass 工具。后端通过 `birdc` 受限模式与本机 bird2 守护进程交互，前端为无框架单页应用（SPA），可在 **1 核 1G 低配 VPS** 上流畅运行。

## 功能特性

- **bgp.tools 同款 UI**：黑色顶栏、红色主题按钮、`Start here...` 中央搜索框、卡片式标签页布局
- **统一搜索**：输入 ASN / 前缀 / IP / 域名自动识别类型并跳转到对应页面
- **ASN 页**：Overview / Prefixes / Connectivity / Whois 四个标签页，展示前缀列表、上游对等、ROA 状态、registry 对象
- **Prefix 页**：前缀的 AS 路径、下一跳、来源 peer、ROA 校验结果
- **Looking Glass**：从本节点执行 `show route for`、`show protocols`、`traceroute`、`whois` 查询，并展示 BGP Sessions 实时状态表
- **ROA 状态标记**：valid / invalid / unknown 三态徽标
- **Demo 模式**：内置一套完整的虚拟 DN42 拓扑数据，无 bird2 环境也能一键体验
- **安全设计**：birdc 受限模式（`-r`）+ 命令白名单 + 输入校验防注入 + 内存滑动窗口限流 + 可选 API Key 鉴权
- **低资源占用**：Flask 单进程 + TTL 内存缓存，常驻内存约 30–50MB

## 页面预览

| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/` | 中央搜索框，自动识别查询类型 |
| ASN 页 | `/as/4242422601` | 某 AS 的前缀、连接性、whois |
| 前缀页 | `/prefix/172.21.10.0/24` | 路由条目与 AS 路径 |
| Looking Glass | `/lg` | 查询表单 + BGP 会话状态 |

## 快速开始（Demo 模式）

无需 bird2，直接体验完整界面与模拟数据：

```bash
git clone https://github.com/anncix/bgptools.git
cd bgptools
pip install -r requirements.txt
BGP_TOOL_DEMO_MODE=true python backend/app.py
```

打开浏览器访问 <http://127.0.0.1:8421>，试试搜索：

- `4242422601` → ASN 页
- `172.21.10.0/24` → 前缀页
- `172.21.10.1` → 路由查询

## 生产部署（对接真实 bird2）

### 1. 安装依赖

```bash
apt install bird2 traceroute whois python3-pip
pip install -r requirements.txt
```

### 2. 配置 bird2

参考 `deploy/bird.conf.example`，关键是允许 birdc 受限访问：

```bash
# 确保 bird 控制套接字存在
ls /run/bird/bird.ctl
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env：设置节点名、ASN；公网暴露务必设置 BGP_TOOL_API_KEY
```

### 4. systemd 托管

```bash
sudo cp deploy/bgp-tool.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bgp-tool
```

服务默认监听 `127.0.0.1:8421`（单 worker 即可，适配 1C1G）。

### 5. nginx 反向代理（可选）

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/bgp-tool
sudo ln -s /etc/nginx/sites-available/bgp-tool /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

也可以直接运行 `deploy/setup.sh` 一键完成 3–4 步。

## 配置项

所有配置均通过环境变量覆盖（前缀 `BGP_TOOL_`），常用项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BGP_TOOL_HOST` / `PORT` | `127.0.0.1` / `8421` | 监听地址 |
| `BGP_TOOL_API_KEY` | 空 | 设置后请求需带 `X-API-Key` 头或 `?key=` |
| `BGP_TOOL_NODE_NAME` / `NODE_ASN` | `node1` / `4242420000` | 节点名与本机 ASN（页面展示用） |
| `BGP_TOOL_BIRD_SOCKET` | `/run/bird/bird.ctl` | bird 控制套接字 |
| `BGP_TOOL_BIRD_RESTRICT` | `true` | birdc 受限模式，**强烈建议保持开启** |
| `BGP_TOOL_DEMO_MODE` | `false` | birdc 不可用时返回模拟数据 |
| `BGP_TOOL_RATE_LIMIT` | `60` | 单 IP 每分钟请求上限，0 为不限 |
| `BGP_TOOL_CACHE_TTL_*` | 5–15 秒 | 各类 birdc 查询的缓存 TTL |

完整列表见 `.env.example` 与 `config.py`。

## API 接口

### bgp.tools 风格聚合接口

| 接口 | 说明 |
|------|------|
| `GET /api/search?q=<查询>` | 查询分类（asn / prefix / ip / dns） |
| `GET /api/as/<asn>` | ASN 聚合视图（前缀 + 对等 + whois） |
| `GET /api/prefix/<前缀>` | 前缀聚合视图（路由 + ROA） |

### 底层接口

| 接口 | 说明 |
|------|------|
| `GET /api/health` | 健康检查与运行模式 |
| `GET /api/status` | `show status`（Router ID、运行时间） |
| `GET /api/protocols?name=<协议名>` | `show protocols [all]` |
| `GET /api/routes?protocol=&family=&primary=` | `show route` 多维过滤 |
| `GET /api/route/lookup/<IP/前缀>` | `show route for` 最长前缀匹配 |
| `GET /api/roa/<前缀>` | ROA 可达性校验 |
| `GET /api/traceroute/<主机>` | traceroute |
| `GET /api/whois?q=<对象>` | DN42 registry whois |
| `POST /api/cache/clear` | 清空内存缓存 |

返回均为 JSON；错误时返回 `{"error": "..."}` 与相应 HTTP 状态码。

## 目录结构

```
bgp-tool/
├── backend/
│   ├── app.py         # Flask 主应用：API 路由、鉴权、限流、SPA 静态服务
│   ├── bird.py        # birdc 交互层：命令白名单、输出解析、TTL 缓存
│   ├── aggregate.py   # bgp.tools 风格 ASN/Prefix 聚合视图
│   ├── search.py      # 查询分类（ASN/前缀/IP/域名）
│   ├── dn42.py        # whois、traceroute、DN42 常量
│   └── demo.py        # Demo 模式：虚拟 DN42 拓扑模拟数据
├── frontend/static/
│   ├── index.html     # SPA 入口（顶栏 + 搜索框）
│   ├── css/style.css  # bgp.tools 风格样式
│   └── js/app.js      # SPA 路由与页面渲染
├── deploy/
│   ├── bgp-tool.service    # systemd 单元
│   ├── nginx.conf          # 反代示例
│   ├── bird.conf.example   # bird2 配置示例
│   └── setup.sh            # 一键安装脚本
├── config.py          # 配置（环境变量覆盖）
├── requirements.txt
└── .env.example
```

## 安全说明

- **birdc 受限模式**：以 `birdc -r` 运行，bird 侧只接受只读 show 命令
- **命令白名单**：仅允许 `show status/protocols/route/memory` 等前缀；`configure`/`restart`/`disable` 等一律拒绝
- **输入校验**：IP/前缀/协议名/主机名均经格式校验后才拼入命令，杜绝命令注入
- **限流与鉴权**：内存滑动窗口限流；公网部署请务必设置 `BGP_TOOL_API_KEY`

## 致谢

- UI 设计灵感来自 [bgp.tools](https://bgp.tools)
- 面向 [DN42](https://dn42.dev) 实验网络，数据来自本节点 bird2 与 DN42 registry

## 许可证

MIT
