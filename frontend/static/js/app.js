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
    // 浏览器代理可能拦截 URL 编码的空格 (%20)，将空格替换为逗号
    const qSafe = q.replace(/\s+/g, ",");
    try {
      const r = await api(`/api/search?q=${encodeURIComponent(qSafe)}`);
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

  // 从 BIRD 的 as_info 字段解析 AS Path 数组
  // 格式如 "AS4242423914 4242422688 i" → ["4242423914", "4242422688"]
  const parseAsPath = (route) => {
    if (Array.isArray(route.path) && route.path.length) return route.path;
    const raw = route.as_info || route.as_path || "";
    if (!raw) return [];
    // 去掉末尾的 BGP origin code (i/e/?) 并提取所有 AS 号
    return (raw.replace(/\s+[ie?]\s*$/, "").match(/(?:AS)?(\d{4,10})/g) || [])
      .map((s) => s.replace(/^AS/i, ""));
  };

  // 从解析后的路由条目提取 next hop
  const extractVia = (route) => {
    if (route.via) return route.via;
    if (route.nexthop) return route.nexthop;
    if (Array.isArray(route.nexthops) && route.nexthops.length)
      return route.nexthops[0].replace(/^via\s+/, "");
    return "—";
  };

  // 从解析后的路由条目提取 source/peer（去掉时间戳）
  const extractSource = (route) => {
    let s = route.source || route.peer || "";
    // 去掉末尾时间戳 "2026-07-28 10:10:01"
    return s.replace(/\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}.*$/, "").trim();
  };

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
    if (path === "/lg") return renderLg();
    if (path === "/api") return renderApiDoc();
    if (path === "/as-path" || path.startsWith("/as-path/")) return renderAsPath();
    if (path === "/ix" || path.startsWith("/ix/")) return renderIxPage();
    if (path === "/dns" || path.startsWith("/dns/")) return renderDnsPage();
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
            <li><a href="/as-path">AS Path</a> <span class="dim">全网路径搜索</span></li>
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
        { id: "ix", label: "IX" },
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

      <div id="p-ix" style="display:none">
        <div id="ix-content"><div class="loading"><span class="spin"></span> Loading IX data…</div></div>
      </div>

      <div id="p-whois" style="display:none">
        <h2 class="blk-title" style="margin-top:0">aut-num (DN42 registry)</h2>
        <pre class="raw">${esc(d.whois || "(no whois data)")}</pre>
      </div>`;

    bindTabs({
      overview: $("#p-overview"), prefixes: $("#p-prefixes"),
      connectivity: $("#p-connectivity"), ix: $("#p-ix"), whois: $("#p-whois"),
    });

    // 异步加载 IX 数据
    loadIxForAsn(d.asn);
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
        { id: "dns", label: "DNS" },
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
          ? `<div class="aspath-flow">
              ${d.as_path.map((a, i) =>
                `${i > 0 ? '<span class="flow-arrow">→</span>' : ''}<a class="flow-node" href="/as/${esc(a)}">AS${esc(a)}</a>`
              ).join("")}
            </div>
            <p style="margin-top:12px">
              <a href="/as-path?q=${encodeURIComponent(d.as_path.join(","))}" class="btn" style="font-size:13px">查看完整 AS Path 拓扑图</a>
            </p>`
          : `<p class="dim">无路径数据</p>`}

        ${d.all_paths && d.all_paths.length > 1 ? `
        <h2 class="blk-title">All Paths (${d.all_paths.length})</h2>
        <table class="data">
          <thead><tr><th>#</th><th>AS Path</th><th>Source</th><th>ROA</th><th>Preferred</th></tr></thead>
          <tbody>
            ${d.all_paths.map((p, i) => `<tr>
              <td>${i + 1}</td>
              <td class="mono">${(p.path || []).map((a) => asLink(a)).join(" → ")}</td>
              <td class="mono">${esc(p.peer || p.source || "—")}</td>
              <td>${roaBadge(p.roa || "unknown")}</td>
              <td>${p.preferred ? '<span class="tag tag-up">★</span>' : ""}</td>
            </tr>`).join("")}
          </tbody>
        </table>` : ""}

        <h2 class="blk-title">Origin AS</h2>
        ${d.origin_as
          ? `<p>${asLink(d.origin_as, d.as_name)} <a href="/as-path?q=${encodeURIComponent(d.origin_as)}" class="btn" style="font-size:12px;margin-left:8px">AS Path 拓扑</a></p>`
          : `<p class="dim">无起源 AS 信息</p>`}
      </div>

      <div id="p-whois" style="display:none">
        <h2 class="blk-title" style="margin-top:0">inet${d.family === 6 ? "6" : ""}num (DN42 registry)</h2>
        <pre class="raw">${esc(d.whois || "(no whois data)")}</pre>
      </div>

      <div id="p-dns" style="display:none">
        <div id="dns-content"><div class="loading"><span class="spin"></span> Loading DNS data…</div></div>
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
      whois: $("#p-whois"), dns: $("#p-dns"), validation: $("#p-validation"),
    });

    // 异步加载 DNS 数据
    loadDnsForPrefix(d.prefix);
  }

  // ============================================================
  // 单 IP 页（模仿 bgp.tools /ip/8.8.8.8）
  // ============================================================
  async function renderIp(ip) {
    document.title = `${ip} — bgp.tools`;
    main().innerHTML = `<div class="loading"><span class="spin"></span> Resolving ${esc(ip)}…</div>`;
    let d;
    try {
      d = await api(`/api/route/lookup/${encodeURIComponent(ip)}`);
    } catch (e) {
      main().innerHTML = errorBox(esc(e.message));
      return;
    }
    const routes = (d.parsed && d.parsed.routes) || [];
    if (!routes.length) {
      main().innerHTML = `
        <div class="page-head"><h1>${esc(ip)}</h1>
          <div class="crumb"><b>IP Lookup</b> · ${liveDot()}</div></div>
        ${errorBox(`路由表中找不到 ${esc(ip)} 的匹配前缀`)}`;
      return;
    }

    // 取最佳路由（preferred 优先），从 as_info 解析 AS Path
    const best = routes.find((r) => r.preferred) || routes[0];
    const prefix = best.prefix;
    const asPath = parseAsPath(best);
    const origin = asPath.length ? asPath[asPath.length - 1] : null;
    const viaText = extractVia(best);
    const srcText = extractSource(best);

    // 收集所有唯一 AS 路径（用解析后的 path 去重）
    const seenPaths = new Set();
    const allPaths = [];
    routes.forEach((r) => {
      const p = parseAsPath(r);
      const key = p.join(",");
      if (!seenPaths.has(key)) {
        seenPaths.add(key);
        allPaths.push({ route: r, path: p });
      }
    });

    main().innerHTML = `
      <div class="page-head">
        <h1>${esc(ip)}</h1>
        <div class="crumb">
          <b>IP Address</b>
          · belongs to <a href="/prefix/${encodeURIComponent(prefix)}">${esc(prefix)}</a>
          ${origin ? `· originated by ${asLink(origin)}` : ""}
          · ${liveDot()}
        </div>
      </div>

      <div id="p-overview">
        <dl class="deflist">
          <dt>IP Address</dt><dd class="mono">${esc(ip)}</dd>
          <dt>Matching prefix</dt><dd><a href="/prefix/${encodeURIComponent(prefix)}">${esc(prefix)}</a></dd>
          <dt>Origin AS</dt><dd>${origin ? asLink(origin) : '<span class="dim">—</span>'}</dd>
          <dt>Next hop</dt><dd class="mono">${esc(viaText)}</dd>
          <dt>Route source</dt><dd class="mono">${esc(srcText)}</dd>
          <dt>Paths seen</dt><dd>${allPaths.length} 条唯一路径</dd>
        </dl>

        <h2 class="blk-title">AS Path (Best Route)</h2>
        ${asPath.length ? `
          <div class="aspath-flow">
            ${asPath.map((a, i) =>
              `${i > 0 ? '<span class="flow-arrow">→</span>' : ''}<a class="flow-node" href="/as/${esc(a)}">AS${esc(a)}</a>`
            ).join("")}
          </div>
          <p style="margin-top:12px">
            <a href="/as-path?q=${encodeURIComponent(asPath.join(","))}" class="btn" style="font-size:13px">查看完整 AS Path 拓扑图</a>
          </p>` : `<p class="dim">无 AS Path 数据</p>`}

        ${allPaths.length > 1 ? `
        <h2 class="blk-title">All Paths (${allPaths.length})</h2>
        <table class="data">
          <thead><tr><th>#</th><th>AS Path</th><th>Source</th><th>ROA</th></tr></thead>
          <tbody>
            ${allPaths.map((rp, i) => `<tr>
              <td>${i + 1}</td>
              <td class="mono">${rp.path.map((a) => asLink(a)).join(" → ")}</td>
              <td class="mono">${esc(extractSource(rp.route))}</td>
              <td>${roaBadge(rp.route.roa || "unknown")}</td>
            </tr>`).join("")}
          </tbody>
        </table>` : ""}

        <h2 class="blk-title">Raw Route Output</h2>
        <pre class="raw">${esc(d.raw || "(no output)")}</pre>
      </div>`;
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
        <tr><td class="mono">/api/as-path/search?q=</td><td>全网 AS Path 搜索（单 ASN 拓扑 / 双 ASN 路径）</td></tr>
        <tr><td class="mono">/api/as-path/graph/&lt;asn&gt;</td><td>单个 ASN 的 AS Path 图（上游/下游/策略）</td></tr>
        <tr><td class="mono">/api/status · /api/memory</td><td>bird2 状态与内存</td></tr>
      </tbody></table>
      <h2 class="blk-title">示例</h2>
      <pre class="raw">curl -s http://127.0.0.1:8421/api/as/4242422601
curl -s http://127.0.0.1:8421/api/prefix/172.21.10.0/24
curl -s http://127.0.0.1:8421/api/route/lookup/172.20.0.53</pre>`;
  }

  // ============================================================
  // AS Path 全网搜索与可视化（模仿 bgp.tools 的 AS Path 功能）
  // ============================================================
  async function renderAsPath() {
    const params = new URLSearchParams(location.search);
    const query = params.get("q") || "";
    document.title = `AS Path — bgp.tools`;

    // 无查询参数：展示搜索入口 + 示例
    if (!query) {
      main().innerHTML = `
        <div class="page-head">
          <h1>AS Path</h1>
          <div class="crumb"><b>全网路径搜索</b> · 输入 ASN 查看可达路径拓扑 · ${liveDot()}</div>
        </div>
        <div class="aspath-intro">
          <p>在 DN42 全网拓扑中搜索两个 ASN 之间的 AS Path，或查看单个 ASN 的完整上下游关系。</p>
          <div class="aspath-search">
            <input type="search" id="aspath-q" placeholder="例如：4242421234 4242422601  或  4242427777" autocomplete="off" spellcheck="false" />
            <button class="btn" id="aspath-go">Search</button>
          </div>
          <div class="aspath-examples">
            <span class="dim">快速示例：</span>
            <a href="/as-path?q=4242427777">单 ASN 查询 (4242427777)</a>
            <a href="/as-path?q=4242421234,4242424100">两 ASN 路径 (本机→CLOUD-NET)</a>
            <a href="/as-path?q=4242422601,4242424900">跨多层路径</a>
            <a href="/as-path?q=4242423914,4242424800">Tier1→OMEGA</a>
          </div>
        </div>`;
      const inp = $("#aspath-q"), btn = $("#aspath-go");
      btn.addEventListener("click", () => {
        const v = inp.value.trim();
        if (v) go(`/as-path?q=${encodeURIComponent(v.replace(/\s+/g, ","))}`);
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { const v = inp.value.trim(); if (v) go(`/as-path?q=${encodeURIComponent(v.replace(/\s+/g, ","))}`); }
      });
      inp.focus();
      return;
    }

    // 有查询参数：加载并可视化
    main().innerHTML = `<div class="loading"><span class="spin"></span> 正在搜索 AS Path: ${esc(query)}…</div>`;
    let d;
    try {
      d = await api(`/api/as-path/search?q=${encodeURIComponent(query.replace(/\s+/g, ","))}`);
    } catch (e) {
      main().innerHTML = errorBox(esc(e.message));
      return;
    }
    if (d.error) {
      main().innerHTML = `
        <div class="page-head"><h1>AS Path</h1>
          <div class="crumb"><b>搜索失败</b> · ${liveDot()}</div></div>
        ${errorBox(esc(d.error))}
        <div class="aspath-search" style="margin-top:18px">
          <input type="search" id="aspath-q2" placeholder="重新输入 ASN..." value="${esc(query)}" autocomplete="off" spellcheck="false" />
          <button class="btn" id="aspath-go2">Search</button>
        </div>`;
      const inp = $("#aspath-q2"), btn = $("#aspath-go2");
      btn.addEventListener("click", () => { const v = inp.value.trim(); if (v) go(`/as-path?q=${encodeURIComponent(v.replace(/\s+/g, ","))}`); });
      inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { const v = inp.value.trim(); if (v) go(`/as-path?q=${encodeURIComponent(v.replace(/\s+/g, ","))}`); } });
      return;
    }

    // 成功：渲染可视化
    const isSingle = d.query_type === "single";
    const titleText = isSingle
      ? `AS${esc(d.origin)} (${esc(d.origin_name)})`
      : `AS${esc(d.src)} → AS${esc(d.dst)}`;

    main().innerHTML = `
      <div class="page-head">
        <h1>${titleText}</h1>
        <div class="crumb">
          <b>AS Path ${isSingle ? "Topology" : "Search"}</b>
          ${isSingle ? "" : ` · ${d.found ? "找到 " + d.total_paths + " 条路径" : "未找到直达路径"}`}
          · ${liveDot()}
        </div>
      </div>

      <div class="aspath-search aspath-bar">
        <input type="search" id="aspath-q3" placeholder="搜索 AS Path (如 4242421234 4242422601)" value="${esc(query)}" autocomplete="off" spellcheck="false" />
        <button class="btn" id="aspath-go3">Search</button>
      </div>

      ${isSingle ? `
      <div class="aspath-metrics">
        <div class="metric-card"><div class="num">${d.total_paths}</div><div class="label">AS Paths</div></div>
        <div class="metric-card"><div class="num">${d.upstreams.length}</div><div class="label">Upstreams</div></div>
        <div class="metric-card"><div class="num">${d.downstreams.length}</div><div class="label">Downstreams</div></div>
        <div class="metric-card"><div class="num">${d.total_prefixes}</div><div class="label">Originated Prefixes</div></div>
        <div class="metric-card"><div class="num">${d.nodes.length}</div><div class="label">Connected ASes</div></div>
      </div>` : ""}

      <div class="aspath-layout">
        <div class="aspath-chart-wrap">
          <h2 class="blk-title" style="margin-top:18px">Network Topology</h2>
          <div class="aspath-legend">
            <span class="lg-item"><span class="lg-dot" style="background:#1890ff"></span>Tier1 (核心中转)</span>
            <span class="lg-item"><span class="lg-dot" style="background:#fa8c16"></span>Transit (二级中转)</span>
            <span class="lg-item"><span class="lg-dot" style="background:#52c41a"></span>Edge (边缘网络)</span>
            <span class="lg-item"><span class="lg-dot lg-origin"></span>Origin/Endpoint</span>
          </div>
          <div id="aspath-chart" class="aspath-chart"></div>
        </div>
        <div class="aspath-side">
          ${isSingle ? renderAsPathSideSingle(d) : renderAsPathSidePair(d)}
        </div>
      </div>

      ${isSingle && d.policies && d.policies.length ? `
      <h2 class="blk-title">Network Policies (Truncated at Tier1)</h2>
      <table class="data">
        <thead><tr><th>Policy Name</th><th>Truncated AS Path</th><th>Prefixes</th><th>Count</th></tr></thead>
        <tbody>
          ${d.policies.map((p) => `<tr>
            <td class="mono">${esc(p.name)}</td>
            <td class="mono">${p.path.map((a) => asLink(a)).join(" → ")}</td>
            <td class="mono" style="font-size:12px">${p.prefixes.map((pf) => `<a href="/prefix/${encodeURIComponent(pf)}">${esc(pf)}</a>`).join(" ")}</td>
            <td>${p.prefix_count}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : ""}

      ${!isSingle && d.paths && d.paths.length ? `
      <h2 class="blk-title">Path Details</h2>
      <table class="data">
        <thead><tr><th>#</th><th>Direction</th><th>AS Path</th><th>Prefix</th></tr></thead>
        <tbody>
          ${d.paths.map((p, i) => `<tr>
            <td>${i + 1}</td>
            <td><span class="tag ${p.direction === "src→dst" ? "tag-up" : "tag-idle"}">${esc(p.direction)}</span></td>
            <td class="mono">${p.path.map((a) => asLink(a)).join(" → ")}</td>
            <td class="mono"><a href="/prefix/${encodeURIComponent(p.prefix)}">${esc(p.prefix)}</a></td>
          </tr>`).join("")}
        </tbody>
      </table>` : ""}
    `;

    // 绑定搜索
    const inp3 = $("#aspath-q3"), btn3 = $("#aspath-go3");
    btn3.addEventListener("click", () => { const v = inp3.value.trim(); if (v) go(`/as-path?q=${encodeURIComponent(v.replace(/\s+/g, ","))}`); });
    inp3.addEventListener("keydown", (e) => { if (e.key === "Enter") { const v = inp3.value.trim(); if (v) go(`/as-path?q=${encodeURIComponent(v.replace(/\s+/g, ","))}`); } });

    // 渲染 ECharts 图
    renderAsPathChart(d);
  }

  function renderAsPathSideSingle(d) {
    let html = "";
    if (d.upstreams.length) {
      html += `<h3 class="side-title">Upstreams</h3><ul class="link-list">`;
      d.upstreams.forEach((u) => { html += `<li>${asLink(u.asn, u.name)}</li>`; });
      html += `</ul>`;
    }
    if (d.downstreams.length) {
      html += `<h3 class="side-title">Downstreams</h3><ul class="link-list">`;
      d.downstreams.forEach((dd) => { html += `<li>${asLink(dd.asn, dd.name)}</li>`; });
      html += `</ul>`;
    }
    if (d.peers && d.peers.length) {
      html += `<h3 class="side-title">Peers (same path)</h3><ul class="link-list">`;
      d.peers.forEach((p) => { html += `<li>${asLink(p.asn, p.name)}</li>`; });
      html += `</ul>`;
    }
    if (!html) html = `<p class="dim">无上下游关系数据</p>`;
    return html;
  }

  function renderAsPathSidePair(d) {
    if (!d.found) {
      return `<div class="notice">未找到 AS${esc(d.src)} 与 AS${esc(d.dst)} 之间的可达路径。<br>它们可能不在同一 AS Path 上，或拓扑中缺少中转连接。</div>`;
    }
    let html = `<h3 class="side-title">Search Result</h3>
      <dl class="deflist">
        <dt>Source</dt><dd>${asLink(d.src, d.src_name)}</dd>
        <dt>Destination</dt><dd>${asLink(d.dst, d.dst_name)}</dd>
        <dt>Paths found</dt><dd>${d.total_paths}</dd>
        <dt>Hop range</dt><dd>${Math.min(...d.paths.map((p) => p.path.length))}–${Math.max(...d.paths.map((p) => p.path.length))} hops</dd>
      </dl>`;
    // 显示最短路径
    const shortest = [...d.paths].sort((a, b) => a.path.length - b.path.length)[0];
    html += `<h3 class="side-title">Shortest Path (${shortest.path.length} hops)</h3>
      <div class="aspath-flow">${shortest.path.map((a, i) =>
        `${i > 0 ? '<span class="flow-arrow">→</span>' : ''}<a class="flow-node" href="/as/${a}">AS${esc(a)}</a>`
      ).join("")}</div>`;
    return html;
  }

  function renderAsPathChart(data) {
    const el = $("#aspath-chart");
    if (!el) return;

    if (!data.nodes || data.nodes.length === 0) {
      el.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:200px;color:#999;font-size:14px">无拓扑数据可展示</div>`;
      return;
    }

    el.style.height = "500px";
    // Ensure echarts is loaded
    if (typeof echarts === "undefined") {
      el.innerHTML = `<div class="error-box">ECharts library failed to load.</div>`;
      return;
    }

    const chart = echarts.init(el);
    const pairIds = data.query_type === "pair" ? new Set([data.src, data.dst].filter(Boolean)) : null;
    const isOriginFn = (n) => {
      if (!n) return false;
      if (data.query_type === "single") return !!n.is_origin || n.id === data.origin;
      if (data.query_type === "pair") return !!(pairIds && pairIds.has(n.id));
      return !!n.is_origin;
    };

    const nodes = data.nodes.map((n) => {
      const isOrigin = isOriginFn(n);
      const isTier1 = n.type === "tier1" || n.is_tier1;

      let category = 1; // Transit
      let symbolSize = 40;
      let color = "#5470c6";

      if (isOrigin) {
        category = 0; // Origin
        symbolSize = 60;
        color = "#ff4d4f"; // bgp.tools uses red-ish for targets
      } else if (isTier1) {
        category = 2; // Tier1
        symbolSize = 50;
        color = "#73d13d";
      }

      return {
        id: n.id,
        name: "AS" + n.id,
        category: category,
        symbolSize: symbolSize,
        itemStyle: {
          color: color,
          borderColor: "#fff",
          borderWidth: 2,
          shadowBlur: 10,
          shadowColor: "rgba(0,0,0,0.2)",
        },
        label: {
          show: true,
          position: "inside",
          formatter: "{b}",
          color: "#fff",
          fontSize: isOrigin ? 12 : 10,
          fontWeight: "bold",
        },
        tooltip: {
          formatter: `<b>AS${n.id}</b><br/>${n.name || "Unknown"}<br/>Type: ${isOrigin ? "Origin/Target" : (isTier1 ? "Tier 1" : "Transit")}`,
        },
      };
    });

    const links = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      lineStyle: {
        color: "#999",
        width: 1.5,
        curveness: 0.15,
      },
    }));

    const option = {
      tooltip: {
        trigger: "item",
      },
      legend: {
        data: ["Origin/Target", "Transit", "Tier 1"],
        top: 10,
        left: "center",
        textStyle: { color: "#333" },
      },
      animationDurationUpdate: 1500,
      animationEasingUpdate: "quinticInOut",
      series: [
        {
          name: "AS Path Topology",
          type: "graph",
          layout: "force",
          force: {
            repulsion: 400,
            edgeLength: [50, 120],
            gravity: 0.1,
            layoutAnimation: true,
          },
          roam: true, // Allow pan and zoom
          label: {
            position: "right",
            formatter: "{b}",
          },
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: [4, 8],
          categories: [
            { name: "Origin/Target" },
            { name: "Transit" },
            { name: "Tier 1" },
          ],
          data: nodes,
          links: links,
          lineStyle: {
            color: "source",
            curveness: 0.2,
          },
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 4,
            },
          },
        },
      ],
    };

    chart.setOption(option);
    window.addEventListener("resize", () => {
      chart.resize();
    });
  }

  // ============================================================
  // IX / IXP 页面
  // ============================================================
  async function loadIxForAsn(asn) {
    const el = $("#ix-content");
    if (!el) return;
    try {
      const d = await api(`/api/ix/asn/${encodeURIComponent(asn)}`);
      const ixs = d.ix_list || [];
      if (!ixs.length) {
        el.innerHTML = `<p class="dim">该 AS 未参与任何互联网交换点（IXP）</p>`;
        return;
      }
      el.innerHTML = `
        <h2 class="blk-title" style="margin-top:0">Internet Exchange Points (${ixs.length})</h2>
        <table class="data">
          <thead><tr><th>IX Name</th><th>City</th><th>Country</th><th>Role</th><th>IPv4 Prefix</th><th>Traffic</th></tr></thead>
          <tbody>
            ${ixs.map((ix) => `<tr>
              <td><a href="/ix/${esc(ix.id)}">${esc(ix.name)}</a></td>
              <td>${esc(ix.city)}</td>
              <td class="mono">${esc(ix.country)}</td>
              <td>${ix.is_route_server ? '<span class="tag tag-up">Route Server</span>' : '<span class="dim">Member</span>'}</td>
              <td class="mono">${esc(ix.ipv4_prefix)}</td>
              <td class="mono">${esc(ix.traffic || "—")}</td>
            </tr>`).join("")}
          </tbody>
        </table>`;
    } catch (e) {
      el.innerHTML = errorBox(esc(e.message));
    }
  }

  async function renderIxPage() {
    const params = new URLSearchParams(location.search);
    const ixId = location.pathname.replace("/ix/", "").replace("/ix", "");

    if (!ixId) {
      // IX 列表页
      document.title = "Internet Exchange Points — bgp.tools";
      main().innerHTML = `<div class="loading"><span class="spin"></span> Loading IX list…</div>`;
      try {
        const d = await api("/api/ix");
        const ixs = d.ix_list || [];
        main().innerHTML = `
          <div class="page-head">
            <h1>Internet Exchange Points</h1>
            <div class="crumb"><b>IXP Directory</b> · ${ixs.length} exchanges · ${liveDot()}</div>
          </div>
          <table class="data">
            <thead><tr><th>IX Name</th><th>City</th><th>Country</th><th>Members</th><th>Route Server</th><th>Traffic</th><th>Established</th></tr></thead>
            <tbody>
              ${ixs.map((ix) => `<tr>
                <td><a href="/ix/${esc(ix.id)}">${esc(ix.name)}</a></td>
                <td>${esc(ix.city)}</td>
                <td class="mono">${esc(ix.country)}</td>
                <td>${ix.member_count}</td>
                <td>${asLink(ix.route_server, ix.route_server_name)}</td>
                <td class="mono">${esc(ix.traffic || "—")}</td>
                <td class="mono">${esc(ix.established || "—")}</td>
              </tr>`).join("")}
            </tbody>
          </table>`;
      } catch (e) {
        main().innerHTML = errorBox(esc(e.message));
      }
      return;
    }

    // 单个 IX 详情页
    document.title = `${ixId} — bgp.tools`;
    main().innerHTML = `<div class="loading"><span class="spin"></span> Loading ${esc(ixId)}…</div>`;
    try {
      const d = await api(`/api/ix/${encodeURIComponent(ixId)}`);
      main().innerHTML = `
        <div class="page-head">
          <h1>${esc(d.name)}</h1>
          <div class="crumb">
            <b>Internet Exchange Point</b>
            · ${esc(d.city)}, ${esc(d.country)}
            · ${liveDot()}
          </div>
        </div>
        <dl class="deflist">
          <dt>IX ID</dt><dd class="mono">${esc(d.id)}</dd>
          <dt>Location</dt><dd>${esc(d.city)}, ${esc(d.country)}</dd>
          <dt>IPv4 Prefix</dt><dd class="mono"><a href="/prefix/${encodeURIComponent(d.ipv4_prefix)}">${esc(d.ipv4_prefix)}</a></dd>
          <dt>IPv6 Prefix</dt><dd class="mono"><a href="/prefix/${encodeURIComponent(d.ipv6_prefix)}">${esc(d.ipv6_prefix)}</a></dd>
          <dt>Route Server</dt><dd>${asLink(d.route_server, d.route_server_name)}</dd>
          <dt>Peering Policy</dt><dd>${esc(d.peering_policy)}</dd>
          <dt>Traffic</dt><dd class="mono">${esc(d.traffic)}</dd>
          <dt>Established</dt><dd>${esc(d.established)}</dd>
          <dt>Members</dt><dd>${d.members.length} 个自治系统</dd>
        </dl>

        <h2 class="blk-title">Members (${d.members.length})</h2>
        <table class="data">
          <thead><tr><th>ASN</th><th>Name</th><th>Type</th><th>Role</th><th>Prefixes Originated</th></tr></thead>
          <tbody>
            ${d.members.map((m) => `<tr>
              <td>${asLink(m.asn)}</td>
              <td>${esc(m.name)}</td>
              <td><span class="tag ${m.type === "tier1" ? "tag-up" : ""}">${esc(m.type)}</span></td>
              <td>${m.is_route_server ? '<span class="tag tag-up">Route Server</span>' : '<span class="dim">Member</span>'}</td>
              <td>${m.originated_prefix_count !== undefined ? m.originated_prefix_count : m.prefix_count || 0}</td>
            </tr>`).join("")}
          </tbody>
        </table>`;
    } catch (e) {
      main().innerHTML = errorBox(esc(e.message));
    }
  }

  // ============================================================
  // DNS 页面
  // ============================================================
  async function loadDnsForPrefix(prefix) {
    const el = $("#dns-content");
    if (!el) return;
    try {
      const d = await api(`/api/dns/prefix/${encodeURIComponent(prefix)}`);
      const records = d.records || {};
      const keys = Object.keys(records);
      if (!keys.length) {
        el.innerHTML = `<p class="dim">该前缀范围内无 DNS 记录</p>`;
        return;
      }
      el.innerHTML = `
        <h2 class="blk-title" style="margin-top:0">DNS Records (${keys.length})</h2>
        <table class="data">
          <thead><tr><th>IP Address</th><th>PTR</th><th>A</th><th>AAAA</th><th>Description</th></tr></thead>
          <tbody>
            ${keys.map((ip) => {
              const r = records[ip];
              return `<tr>
                <td class="mono"><a href="/ip/${encodeURIComponent(ip)}">${esc(ip)}</a></td>
                <td class="mono">${esc((r.PTR || []).join(", ") || "—")}</td>
                <td class="mono">${esc((r.A || []).join(", ") || "—")}</td>
                <td class="mono">${esc((r.AAAA || []).join(", ") || "—")}</td>
                <td>${esc(r.description || "—")}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>`;
    } catch (e) {
      el.innerHTML = errorBox(esc(e.message));
    }
  }

  async function renderDnsPage() {
    const query = location.pathname.replace("/dns/", "").replace("/dns", "");
    if (!query) {
      document.title = "DNS Lookup — bgp.tools";
      main().innerHTML = `
        <div class="hero" style="padding-top:40px">
          <h1>DNS Lookup</h1>
          <div class="sub">查询 IP 反向解析(PTR) 或域名正向解析(A/AAAA)</div>
          <div class="big-search">
            <input id="dns-q" type="search" placeholder="IP or domain (e.g. 172.20.0.53 or dns.dn42)" autocomplete="off" spellcheck="false" />
            <button id="dns-go" title="Search"><svg width="20" height="20" viewBox="0 0 16 16" fill="none"><path d="M1 8h12M9 3l5 5-5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
          </div>
        </div>`;
      const inp = $("#dns-q"), btn = $("#dns-go");
      const doQuery = () => { const v = inp.value.trim(); if (v) go(`/dns/${encodeURIComponent(v)}`); };
      btn.addEventListener("click", doQuery);
      inp.addEventListener("keydown", (e) => { if (e.key === "Enter") doQuery(); });
      inp.focus();
      return;
    }

    const target = decodeURIComponent(query);
    document.title = `DNS: ${target} — bgp.tools`;
    main().innerHTML = `<div class="loading"><span class="spin"></span> Resolving ${esc(target)}…</div>`;
    try {
      const d = await api(`/api/dns/lookup/${encodeURIComponent(target)}`);
      const records = d.records || {};
      const types = Object.keys(records);
      main().innerHTML = `
        <div class="page-head">
          <h1>${esc(target)}</h1>
          <div class="crumb"><b>DNS Lookup</b> · ${esc(d.query_type || "query")} · ${liveDot()}</div>
        </div>
        ${types.length ? `
          <table class="data">
            <thead><tr><th>Type</th><th>Value</th></tr></thead>
            <tbody>
              ${types.map((t) => {
                const vals = Array.isArray(records[t]) ? records[t] : [records[t]];
                return vals.map((v) => `<tr><td class="mono"><b>${esc(t)}</b></td><td class="mono">${esc(v)}</td></tr>`).join("");
              }).join("")}
            </tbody>
          </table>
          ${d.description ? `<p style="margin-top:12px;color:#666">${esc(d.description)}</p>` : ""}` 
          : `<p class="dim">未找到 DNS 记录</p>`}
      `;
    } catch (e) {
      main().innerHTML = errorBox(esc(e.message));
    }
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
