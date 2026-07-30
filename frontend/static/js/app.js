/* ===== bgp.tools (DN42) —— 前端 SPA 逻辑 =====
   路由（History API，模仿 bgp.tools 真实路径）：
     /                 首页（大搜索框）
     /as/<asn>         ASN 页（Overview/Prefixes/Connectivity/Whois）
     /prefix/<p>       前缀页（Overview/Connectivity/Whois/Validation）
     /ip/<ip>          单 IP → 跳转所属前缀页
     /dns/<name>       DNS 名 → whois
     /lg               Looking Glass（路由查询 / peers / traceroute）
*/
(function () {
  "use strict";

  // ---------- 基础工具 ----------
  const $ = (s, r) => (r || document).querySelector(s);
  const main = () => $("#main");
  const esc = (s) => String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  let META = { node: { name: "node", asn: "" }, demo: false, site: "bgp.tools" };

  async function api(path) {
    const res = await fetch(path);
    let data = {};
    try { data = await res.json(); } catch (_) { /* 非 JSON */ }
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    if (data && data.error) throw new Error(data.error);
    return data;
  }

  function go(url) {
    history.pushState({}, "", url);
    route();
  }

  // 站内链接拦截（无刷新导航）
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;
    if (a.target === "_blank" || a.hasAttribute("data-no-router")) return;
    const href = a.getAttribute("href") || "";
    if (href.startsWith("/") && !href.startsWith("//")) {
      e.preventDefault();
      go(href);
    }
  });
  window.addEventListener("popstate", route);

  // ---------- 全局搜索 ----------
  async function doSearch(q) {
    q = (q || "").trim();
    if (!q) return;
    try {
      const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
      if (r.redirect) go(r.redirect);
    } catch (e) {
      main().innerHTML = errorBox(`无法识别的查询：${esc(q)}（支持 ASN / 前缀 / IP / DNS）`);
    }
  }

  function bindSearch(inputSel, btnSel) {
    const inp = $(inputSel), btn = $(btnSel);
    if (!inp || !btn) return;
    btn.addEventListener("click", () => doSearch(inp.value));
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(inp.value); });
  }

  // ---------- 通用片段 ----------
  const asLink = (asn, name) =>
    `<a class="asnum" href="/as/${esc(asn)}">AS${esc(asn)}</a>` +
    (name ? ` <span class="asname">${esc(name)}</span>` : "");

  const roaBadge = (s) => `<span class="roa roa-${esc(s)}">${esc(s)}</span>`;

  const errorBox = (msg) => `<div class="error-box">⚠ ${msg}</div>`;

  const liveDot = () => `<span class="live-dot">LIVE</span>`;

  function tabs(items, activeId) {
    const btns = items.map((t) =>
      `<button class="tab${t.id === activeId ? " active" : ""}" data-tab="${t.id}">${esc(t.label)}</button>`
    ).join("");
    return `<div class="tabs" id="pg-tabs">${btns}</div>`;
  }
  function bindTabs(panels) {
    $("#pg-tabs")?.addEventListener("click", (e) => {
      const b = e.target.closest(".tab");
      if (!b) return;
      $$("#pg-tabs .tab").forEach((t) => t.classList.toggle("active", t === b));
      Object.entries(panels).forEach(([id, el]) => {
        el.style.display = id === b.dataset.tab ? "" : "none";
      });
    });
  }
  function $$(s, r) { return Array.from((r || document).querySelectorAll(s)); }

  // ---------- 路由 ----------
  function route() {
    const path = location.pathname;
    $("#top-search").hidden = (path === "/");   // 首页用大搜索框，其余页顶栏显示小搜索框
    window.scrollTo(0, 0);

    let m;
    if (path === "/" ) return renderHome();
    if ((m = path.match(/^\/as\/(\d+)$/))) return renderAs(m[1]);
    if ((m = path.match(/^\/prefix\/(.+)$/))) return renderPrefix(decodeURIComponent(m[1]));
    if ((m = path.match(/^\/ip\/([\d.:a-fA-F]+)$/))) return renderIp(m[1]);
    if ((m = path.match(/^\/dns\/(.+)$/))) return renderDns(decodeURIComponent(m[1]));
    if (path === "/lg") return renderLg();
    if (path === "/api") return renderApiDoc();
    return renderNotFound();
  }

  // ============================================================
  // 首页（模仿 bgp.tools "Browse the Internet ecosystem"）
  // ============================================================
  function renderHome() {
    document.title = "bgp.tools — DN42";
    main().innerHTML = `
      <div class="hero">
        <h1>Browse the DN42 ecosystem</h1>
        <div class="sub">Search by ASN (AS${esc(META.node.asn || "4242422601")}), Prefix (172.20.0.0/24), or DNS (dns.dn42)</div>
        <div class="big-search">
          <input id="home-q" type="search" placeholder="Start here..." autocomplete="off" spellcheck="false" />
          <button id="home-go" title="Search" aria-label="Search"><svg width="20" height="20" viewBox="0 0 16 16" fill="none"><path d="M1 8h12M9 3l5 5-5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
        </div>
        <a class="lg-jump" href="/lg">Jump to Looking Glass</a>
      </div>
      <div class="home-cols">
        <section>
          <h2>Your node</h2>
          <ul>
            <li>节点：<b>${esc(META.node.name)}</b></li>
            <li>ASN：${META.node.asn ? asLink(META.node.asn) : "-"}</li>
            <li class="dim">${META.demo ? "演示模式（内置虚拟拓扑）" : "已连接本节点 bird2"}</li>
          </ul>
        </section>
        <section>
          <h2>Example Pages</h2>
          <ul class="ex-links">
            <li>${asLink("4242422601", "burble")}</li>
            <li>${asLink("4242423914", "Kioubit")}</li>
            <li>${asLink("4242422547", "Lan Tian")}</li>
            <li><a href="/prefix/172.21.10.0/24">172.21.10.0/24</a> <span class="dim">prefix</span></li>
            <li><a href="/ip/172.20.0.53">172.20.0.53</a> <span class="dim">anycast DNS</span></li>
          </ul>
        </section>
        <section>
          <h2>Why use this?</h2>
          <h3>免费提供：</h3>
          <ul>
            <li>近实时 BGP 数据（本节点 bird2）</li>
            <li>ROA 校验与 whois 查询</li>
            <li>Looking Glass / Traceroute</li>
          </ul>
          <h3>轻量自托管：</h3>
          <ul>
            <li>1C1G 低配 VPS 即可运行</li>
            <li><a href="https://github.com/anncix/bgptools" target="_blank" rel="noopener">开源代码</a></li>
          </ul>
        </section>
      </div>`;
    bindSearch("#home-q", "#home-go");
    $("#home-q").focus();
  }

  // ============================================================
  // ASN 页（模仿 bgp.tools /as/13335）
  // ============================================================
  async function renderAs(asn) {
    document.title = `AS${asn} — bgp.tools`;
    main().innerHTML = `<div class="loading"><span class="spin"></span> Loading AS${esc(asn)}…</div>`;
    let d;
    try {
      d = await api(`/api/as/${encodeURIComponent(asn)}`);
    } catch (e) {
      main().innerHTML = errorBox(esc(e.message));
      return;
    }
    const v4 = d.prefixes.filter((p) => p.prefix.indexOf(":") === -1);
    const v6 = d.prefixes.filter((p) => p.prefix.indexOf(":") !== -1);

    main().innerHTML = `
      <div class="page-head">
        <h1>${esc(d.name)} ${d.is_mine ? '<span class="roa roa-valid">本节点</span>' : ""}</h1>
        <div class="crumb"><b>AS Number</b> <span class="mono">${esc(d.asn)}</span> · ${liveDot()}</div>
      </div>
      ${tabs([
        { id: "overview", label: "Overview" },
        { id: "prefixes", label: `Prefixes (${d.prefixes.length})` },
        { id: "connectivity", label: "Connectivity" },
        { id: "whois", label: "Whois" },
      ], "overview")}

      <div id="p-overview">
        <dl class="deflist">
          <dt>Registered on</dt><dd>${esc(d.registered_on || "—")}</dd>
          <dt>Network status</dt><dd>${esc(d.network_status || "Active, allocated under DN42")}</dd>
          <dt>Network type</dt><dd>DN42 (4242420000 – 4242429999)</dd>
          <dt>Prefixes originated</dt><dd>${v4.length} IPv4, ${v6.length} IPv6</dd>
          <dt>Direct peering</dt><dd>${d.peering?.is_direct_peer
            ? (d.peering.established ? `<span class="tag tag-up">Established</span>` : `<span class="tag tag-down">Down</span>`)
            : "无直连"}</dd>
        </dl>
        <h2 class="blk-title">Upstreams</h2>
        ${d.upstreams.length
          ? `<ul class="link-list">${d.upstreams.map((u) => `<li>${asLink(u.asn, u.name)}</li>`).join("")}</ul>`
          : `<p class="dim">无（该 AS 为本节点起源或未见于路由路径）</p>`}
        <h2 class="blk-title">Tags</h2>
        <p><a href="/lg">DN42</a> · <a href="/lg">BGP</a>${d.is_mine ? ' · <a href="/lg">This Node</a>' : ""}</p>
      </div>

      <div id="p-prefixes" style="display:none">
        ${prefixTable(d.prefixes)}
      </div>

      <div id="p-connectivity" style="display:none">
        <h2 class="blk-title" style="margin-top:0">Peers / Upstreams</h2>
        ${d.upstreams.length
          ? `<ul class="link-list">${d.upstreams.map((u) => `<li>${asLink(u.asn, u.name)}</li>`).join("")}</ul>`
          : `<p class="dim">无上游数据</p>`}
        <h2 class="blk-title">Originated Prefixes</h2>
        ${prefixTable(d.prefixes)}
      </div>

      <div id="p-whois" style="display:none">
        <h2 class="blk-title" style="margin-top:0">aut-num (DN42 registry)</h2>
        <pre class="raw">${esc(d.whois || "(no whois data)")}</pre>
      </div>`;

    bindTabs({
      overview: $("#p-overview"), prefixes: $("#p-prefixes"),
      connectivity: $("#p-connectivity"), whois: $("#p-whois"),
    });
  }

  function prefixTable(prefixes) {
    if (!prefixes || !prefixes.length) return `<p class="dim">该 AS 未在本节点路由表中起源任何前缀。</p>`;
    return `<table class="data"><thead><tr>
        <th>Prefix</th><th>ROA</th><th>AS Path</th><th>Next hop</th></tr></thead><tbody>
      ${prefixes.map((p) => `<tr>
        <td class="mono"><a href="/prefix/${encodeURIComponent(p.prefix)}">${esc(p.prefix)}</a></td>
        <td>${roaBadge(p.roa)}</td>
        <td class="mono">${esc((p.path || []).map((a) => "AS" + a).join(" "))}</td>
        <td class="mono">${esc(p.via || "")}</td>
      </tr>`).join("")}</tbody></table>`;
  }

  // ============================================================
  // 前缀页（模仿 bgp.tools /prefix/8.8.8.0/24）
  // ============================================================
  async function renderPrefix(prefix) {
    document.title = `${prefix} — bgp.tools`;
    main().innerHTML = `<div class="loading"><span class="spin"></span> Loading ${esc(prefix)}…</div>`;
    let d;
    try {
      d = await api(`/api/prefix/${encodeURIComponent(prefix)}`);
    } catch (e) {
      main().innerHTML = errorBox(esc(e.message));
      return;
    }
    const roaText = { valid: "RPKI/ROA Valid", invalid: "RPKI/ROA Invalid", unknown: "RPKI/ROA Unknown" };
    const roaDesc = {
      valid: "该前缀的宣告与其 ROA 记录一致（来源 AS 合法）。",
      invalid: "警告：该前缀的宣告与 ROA 记录不一致（可能是劫持或配置错误）。",
      unknown: "DN42 registry 中未找到该前缀的 ROA 记录。",
    };
    const sizeText = d.family === 4
      ? `${d.num_addresses} 个地址（/${d.prefix.split("/")[1]}）`
      : `/${d.prefix.split("/")[1]}（IPv6）`;

    main().innerHTML = `
      <div class="page-head">
        <h1>${esc(d.prefix)}</h1>
        <div class="crumb">
          ${d.origin_as
            ? `Originated by ${asLink(d.origin_as)} · AS Name: <b>${esc(d.as_name || "—")}</b>`
            : `<span class="dim">本节点路由表中未见该前缀的宣告</span>`}
          · ${liveDot()}
        </div>
      </div>
      ${tabs([
        { id: "overview", label: "Overview" },
        { id: "connectivity", label: "Connectivity" },
        { id: "whois", label: "Whois" },
        { id: "validation", label: "Validation" },
      ], "overview")}

      <div id="p-overview">
        <dl class="deflist">
          <dt>Registered on</dt><dd>${esc(d.registered_on || "—")}</dd>
          <dt>Registered to</dt><dd>${esc(d.registered_to || "—")} <span class="dim">(dn42)</span></dd>
          <dt>Prefix status</dt><dd>${d.seen ? "Active, announced in DN42" : "Not seen from this node"}</dd>
          <dt>Size of prefix</dt><dd>${esc(sizeText)}</dd>
          <dt>Address family</dt><dd>IPv${d.family}</dd>
        </dl>
        <h2 class="blk-title">Less Specific Announcements</h2>
        ${d.less_specifics.length
          ? `<table class="data"><thead><tr><th>Prefix</th><th>Description</th></tr></thead><tbody>
              ${d.less_specifics.map((l) => `<tr>
                <td class="mono"><a href="/prefix/${encodeURIComponent(l.prefix)}">${esc(l.prefix)}</a></td>
                <td>${l.origin_as ? asLink(l.origin_as, l.name) : esc(l.name || "")}</td>
              </tr>`).join("")}</tbody></table>`
          : `<p class="dim">无更宽泛的公告前缀。</p>`}
      </div>

      <div id="p-connectivity" style="display:none">
        <h2 class="blk-title" style="margin-top:0">AS Path</h2>
        ${d.as_path && d.as_path.length
          ? `<ul class="link-list">${d.as_path.map((a) => `<li>${asLink(a)}</li>`).join("")}</ul>`
          : `<p class="dim">无路径数据</p>`}
      </div>

      <div id="p-whois" style="display:none">
        <h2 class="blk-title" style="margin-top:0">inet${d.family === 6 ? "6" : ""}num (DN42 registry)</h2>
        <pre class="raw">${esc(d.whois || "(no whois data)")}</pre>
      </div>

      <div id="p-validation" style="display:none">
        <div class="roa-big ${esc(d.roa)}">
          <div class="t">${esc(roaText[d.roa] || d.roa)}</div>
          <div class="d">${esc(roaDesc[d.roa] || "")}</div>
        </div>
        <dl class="deflist" style="margin-top:18px">
          <dt>Origin AS</dt><dd>${d.origin_as ? asLink(d.origin_as, d.as_name) : "—"}</dd>
          <dt>ROA status</dt><dd>${roaBadge(d.roa)}</dd>
        </dl>
      </div>`;

    bindTabs({
      overview: $("#p-overview"), connectivity: $("#p-connectivity"),
      whois: $("#p-whois"), validation: $("#p-validation"),
    });
  }

  // ============================================================
  // 单 IP → 所属前缀页（模仿 bgp.tools 对 IP 的处理）
  // ============================================================
  async function renderIp(ip) {
    document.title = `${ip} — bgp.tools`;
    main().innerHTML = `<div class="loading"><span class="spin"></span> Resolving ${esc(ip)}…</div>`;
    try {
      const d = await api(`/api/route/lookup/${encodeURIComponent(ip)}`);
      const routes = (d.parsed && d.parsed.routes) || [];
      if (routes.length) {
        const best = routes.find((r) => r.preferred) || routes[0];
        go(`/prefix/${encodeURIComponent(best.prefix)}`);
        return;
      }
      main().innerHTML = errorBox(`路由表中找不到 ${esc(ip)} 的匹配前缀`);
    } catch (e) {
      main().innerHTML = errorBox(esc(e.message));
    }
  }

  // ============================================================
  // DNS 名 → whois 查询
  // ============================================================
  async function renderDns(name) {
    document.title = `${name} — bgp.tools`;
    main().innerHTML = `<div class="loading"><span class="spin"></span> Querying ${esc(name)}…</div>`;
    let d;
    try { d = await api(`/api/whois?q=${encodeURIComponent(name)}`); }
    catch (e) { main().innerHTML = errorBox(esc(e.message)); return; }
    main().innerHTML = `
      <div class="page-head"><h1>${esc(name)}</h1>
        <div class="crumb"><b>DNS / Object lookup</b> · ${liveDot()}</div></div>
      <h2 class="blk-title">DN42 registry whois</h2>
      <pre class="raw">${esc(d.raw || "(no data)")}</pre>`;
  }

  // ============================================================
  // Looking Glass（模仿 bgp.tools Looking Glass + Super LG）
  // ============================================================
  async function renderLg() {
    document.title = `Looking Glass — bgp.tools`;
    main().innerHTML = `
      <div class="page-head">
        <h1>Looking Glass</h1>
        <div class="crumb"><b>${esc(META.node.name)}</b> · 从本节点查询路由、对等与会话 · ${liveDot()}</div>
      </div>

      <h2 class="blk-title" style="margin-top:18px">Run a query</h2>
      <div class="lg-form">
        <select id="lg-cmd">
          <option value="route">show route for（路由查询）</option>
          <option value="protocols">show protocols（对等状态）</option>
          <option value="traceroute">traceroute（路径追踪）</option>
          <option value="whois">whois（registry 对象）</option>
        </select>
        <input type="text" id="lg-target" placeholder="目标：IP / 前缀 / 主机 / 对象" />
        <button class="btn" id="lg-run">Run</button>
      </div>
      <div id="lg-result"></div>

      <h2 class="blk-title">BGP Sessions</h2>
      <div id="lg-peers"><div class="loading"><span class="spin"></span> Loading…</div></div>`;

    loadPeers();
    $("#lg-run").addEventListener("click", runLg);
    $("#lg-target").addEventListener("keydown", (e) => { if (e.key === "Enter") runLg(); });
    $("#lg-target").focus();

    async function runLg() {
      const cmd = $("#lg-cmd").value;
      const target = $("#lg-target").value.trim();
      const out = $("#lg-result");
      if (!target && cmd !== "protocols") {
        out.innerHTML = `<div class="notice">请输入查询目标</div>`;
        return;
      }
      out.innerHTML = `<div class="loading"><span class="spin"></span> Running…</div>`;
      try {
        let d;
        if (cmd === "route") d = await api(`/api/route/lookup/${encodeURIComponent(target)}`);
        else if (cmd === "traceroute") d = await api(`/api/traceroute/${encodeURIComponent(target)}`);
        else if (cmd === "whois") d = await api(`/api/whois?q=${encodeURIComponent(target)}`);
        else d = await api(`/api/protocols`);
        out.innerHTML = `
          <div class="crumb" style="margin:6px 0"><b>${esc(cmd)}</b> ${esc(target)}</div>
          <pre class="raw">${esc(d.raw || "(no output)")}</pre>`;
      } catch (e) {
        out.innerHTML = errorBox(esc(e.message));
      }
    }

    async function loadPeers() {
      const box = $("#lg-peers");
      try {
        const d = await api(`/api/protocols`);
        const peers = (d.parsed || []).filter((p) => p.bgp);
        if (!peers.length) { box.innerHTML = `<p class="dim">无 BGP 会话</p>`; return; }
        box.innerHTML = `<table class="data"><thead><tr>
            <th>Name</th><th>State</th><th>Since</th><th>Info</th></tr></thead><tbody>
          ${peers.map((p) => `<tr>
            <td class="mono">${esc(p.name)}</td>
            <td>${p.established
              ? `<span class="tag tag-up">Established</span>`
              : `<span class="tag tag-down">${esc(p.state)}</span>`}</td>
            <td class="mono">${esc(p.since)}</td>
            <td class="mono" style="font-size:12.5px">${esc(p.info)}</td>
          </tr>`).join("")}</tbody></table>`;
      } catch (e) {
        box.innerHTML = errorBox(esc(e.message));
      }
    }
  }

  // ============================================================
  // API 文档页（对应 bgp.tools "Scripting/API"）
  // ============================================================
  function renderApiDoc() {
    document.title = `Scripting/API — bgp.tools`;
    main().innerHTML = `
      <div class="page-head"><h1>Scripting / API</h1>
        <div class="crumb"><b>REST JSON</b> · ${liveDot()}</div></div>
      <p>所有接口返回 JSON，GET 请求，可直接用 curl / 脚本调用。</p>
      <table class="data"><thead><tr><th>Endpoint</th><th>说明</th></tr></thead><tbody>
        <tr><td class="mono">/api/search?q=</td><td>查询类型识别（ASN/前缀/IP/DNS）</td></tr>
        <tr><td class="mono">/api/as/&lt;asn&gt;</td><td>ASN 聚合视图（前缀/上游/whois）</td></tr>
        <tr><td class="mono">/api/prefix/&lt;p&gt;</td><td>前缀聚合视图（origin/ROA/whois）</td></tr>
        <tr><td class="mono">/api/route/lookup/&lt;ip&gt;</td><td>show route for（最长前缀匹配）</td></tr>
        <tr><td class="mono">/api/protocols</td><td>show protocols（对等状态）</td></tr>
        <tr><td class="mono">/api/routes</td><td>show route（路由表，可过滤）</td></tr>
        <tr><td class="mono">/api/traceroute/&lt;host&gt;</td><td>traceroute</td></tr>
        <tr><td class="mono">/api/whois?q=</td><td>DN42 registry whois</td></tr>
        <tr><td class="mono">/api/status · /api/memory</td><td>bird2 状态与内存</td></tr>
      </tbody></table>
      <h2 class="blk-title">示例</h2>
      <pre class="raw">curl -s http://127.0.0.1:8421/api/as/4242422601
curl -s http://127.0.0.1:8421/api/prefix/172.21.10.0/24
curl -s http://127.0.0.1:8421/api/route/lookup/172.20.0.53</pre>`;
  }

  // ============================================================
  // 404
  // ============================================================
  function renderNotFound() {
    document.title = "404 — bgp.tools";
    main().innerHTML = `
      <div class="hero" style="padding-top:80px">
        <h1 style="font-size:26px">The thing you are looking for likely doesn't exist.</h1>
        <div class="sub">Sorry! Check your query for errors</div>
        <a class="lg-jump" href="/">Back to search</a>
      </div>`;
  }

  // ============================================================
  // 初始化
  // ============================================================
  async function init() {
    bindSearch("#top-q", "#top-go");
    try {
      const [h, info] = await Promise.all([api("/api/health"), api("/api/dn42/info")]);
      META = {
        node: info.node || { name: h.node, asn: "" },
        demo: !!h.demo_mode,
        site: h.site || "bgp.tools",
      };
      if (META.demo) $("#demo-flag").hidden = false;
    } catch (_) { /* 元信息失败不阻塞 */ }
    route();
  }

  init();
})();
