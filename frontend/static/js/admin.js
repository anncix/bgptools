/* ===== bgp.tools DN42 —— 后台管理面板前端逻辑 =====
   基于原生 JS（无框架），hash 路由 SPA。
   路由：
     #dashboard    仪表盘
     #peers        BGP 会话
     #roa          ROA 管理
     #config       配置管理
     #api-keys     API 密钥
     #audit-logs   审计日志
     #monitor      系统监控
     #wireguard    WireGuard
     #users        用户管理
   所有接口挂载在 /admin/api/* 下，使用 session cookie 鉴权。
*/
(function () {
  "use strict";

  // ============================================================
  // 基础工具
  // ============================================================
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const main = () => $("#admin-main");

  // HTML 转义，防注入
  const esc = (s) => String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  // 字节格式化：KB / MB / GB
  function formatBytes(bytes) {
    if (bytes == null || isNaN(bytes)) return "—";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
    return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GB";
  }

  // MB 格式化
  function formatMB(mb) {
    if (mb == null || isNaN(mb)) return "—";
    if (mb < 1024) return mb.toFixed(1) + " MB";
    return (mb / 1024).toFixed(2) + " GB";
  }

  // 数字千分位
  function formatNum(n) {
    if (n == null || isNaN(n)) return "0";
    return Number(n).toLocaleString("en-US");
  }

  // 时间格式化：兼容 ISO 字符串、SQLite datetime('now') 格式（空格分隔）
  function formatTime(t) {
    if (!t) return "—";
    let s = String(t).replace(" ", "T");
    // SQLite 的 datetime('now') 是 UTC，补 Z 让浏览器按本地时区解析
    if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s) && /T\d{2}:\d{2}:\d{2}/.test(s)) {
      s += "Z";
    }
    const d = new Date(s);
    if (isNaN(d.getTime())) return esc(t);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
           `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  // 相对时间（如 "3 分钟前"）
  function timeAgo(t) {
    if (!t) return "—";
    let s = String(t).replace(" ", "T");
    if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s) && /T\d{2}:\d{2}:\d{2}/.test(s)) s += "Z";
    const d = new Date(s);
    if (isNaN(d.getTime())) return esc(t);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return "刚刚";
    if (diff < 3600) return Math.floor(diff / 60) + " 分钟前";
    if (diff < 86400) return Math.floor(diff / 3600) + " 小时前";
    return Math.floor(diff / 86400) + " 天前";
  }

  // 百分比 → 状态等级
  function percentLevel(p) {
    p = Number(p) || 0;
    if (p >= 90) return "fail";
    if (p >= 75) return "warn";
    return "ok";
  }

  // 状态徽章
  function badge(state, label) {
    const map = {
      ok: "badge-ok", established: "badge-established", up: "badge-established",
      success: "badge-ok", active: "badge-ok",
      warn: "badge-warn", warning: "badge-warn", partial: "badge-warn",
      fail: "badge-fail", down: "badge-down", failed: "badge-fail", error: "badge-fail",
      idle: "badge-idle", unknown: "badge-unknown", stopped: "badge-idle",
      revoked: "badge-fail",
    };
    const cls = map[String(state).toLowerCase()] || "badge-unknown";
    return `<span class="badge ${cls}">${esc(label || state)}</span>`;
  }

  // ROA 状态徽章
  function roaBadge(s) {
    const cls = { valid: "roa-valid", invalid: "roa-invalid", unknown: "roa-unknown" };
    return `<span class="roa-badge ${cls[s] || "roa-unknown"}">${esc(s)}</span>`;
  }

  // 通用错误盒子
  const errorBox = (msg) => `<div class="error-box">⚠ ${esc(msg)}</div>`;

  // 空状态
  const emptyState = (msg, icon) =>
    `<div class="empty-state"><div class="empty-icon">${icon || "∅"}</div><div>${esc(msg)}</div></div>`;

  const loading = (msg) => `<div class="loading"><span class="spin"></span> ${esc(msg || "加载中…")}</div>`;

  // ============================================================
  // API 调用封装（自动携带 session cookie）
  // ============================================================
  async function api(path, options) {
    options = options || {};
    const opt = Object.assign(
      {
        method: "GET",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
      },
      options
    );
    if (options.body && typeof options.body !== "string") {
      opt.body = JSON.stringify(options.body);
    }
    let res;
    try {
      res = await fetch(path, opt);
    } catch (e) {
      throw new Error("网络请求失败：" + e.message);
    }
    // 尝试解析 JSON
    let data = null;
    const text = await res.text();
    if (text) {
      try { data = JSON.parse(text); }
      catch (_) { data = { raw: text }; }
    } else {
      data = {};
    }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
      const err = new Error(msg);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    if (data && data.error) throw new Error(data.error);
    return data;
  }

  // 便捷方法
  const GET = (p) => api(p, { method: "GET" });
  const POST = (p, body) => api(p, { method: "POST", body });
  const PUT = (p, body) => api(p, { method: "PUT", body });
  const DEL = (p) => api(p, { method: "DELETE" });

  // ============================================================
  // 全局状态
  // ============================================================
  const STATE = {
    user: null,            // {username, role}
    route: "dashboard",
    dashboardTimer: null,  // 仪表盘自动刷新定时器
    monitorTimer: null,    // 监控实时刷新定时器
    auditPage: 1,
  };

  // 页面标题映射
  const TITLES = {
    dashboard: "仪表盘",
    peers: "BGP 会话",
    roa: "ROA 管理",
    config: "配置管理",
    "api-keys": "API 密钥",
    "audit-logs": "审计日志",
    monitor: "系统监控",
    wireguard: "WireGuard",
    users: "用户管理",
  };

  // ============================================================
  // Toast 通知
  // ============================================================
  const ICONS = {
    success: "✓",
    error: "✕",
    warn: "!",
    info: "i",
  };

  function toast(type, title, msg, duration) {
    const container = $("#toast-container");
    if (!container) return;
    const el = document.createElement("div");
    el.className = "toast " + (type || "info");
    el.innerHTML = `
      <span class="toast-icon">${ICONS[type] || "i"}</span>
      <div class="toast-body">
        <div class="toast-title">${esc(title || "")}</div>
        ${msg ? `<div class="toast-msg">${esc(msg)}</div>` : ""}
      </div>`;
    container.appendChild(el);
    const ms = duration || 3500;
    setTimeout(() => {
      el.classList.add("fade-out");
      setTimeout(() => el.remove(), 300);
    }, ms);
  }

  const toastOk = (title, msg) => toast("success", title, msg);
  const toastErr = (title, msg) => toast("error", title, msg, 5000);
  const toastWarn = (title, msg) => toast("warn", title, msg);
  const toastInfo = (title, msg) => toast("info", title, msg);

  // ============================================================
  // 模态弹窗 / 确认对话框
  // ============================================================
  function openModal(title, bodyHtml, footerHtml, opts) {
    const overlay = $("#modal-overlay");
    $("#modal-title").textContent = title || "提示";
    $("#modal-body").innerHTML = bodyHtml || "";
    $("#modal-footer").innerHTML = footerHtml || "";
    const modal = $("#modal");
    modal.classList.toggle("modal-danger", !!(opts && opts.danger));
    overlay.hidden = false;
  }

  function closeModal() {
    $("#modal-overlay").hidden = true;
    $("#modal-body").innerHTML = "";
    $("#modal-footer").innerHTML = "";
  }

  // 确认对话框，返回 Promise<boolean>
  function confirmDialog(opts) {
    return new Promise((resolve) => {
      opts = opts || {};
      const danger = opts.danger;
      const icon = danger ? "⚠" : "?";
      const body = `
        <div class="${danger ? "modal-danger" : ""}">
          <div class="modal-warn-icon">${icon}</div>
          <p style="font-size:14px;margin:0 0 8px;font-weight:600">${esc(opts.title || "确认执行此操作？")}</p>
          ${opts.message ? `<p style="color:var(--text-dim);font-size:13px;margin:0">${esc(opts.message)}</p>` : ""}
          ${opts.detail ? `<p class="mono" style="font-size:12px;color:var(--yellow);margin-top:10px;background:var(--bg-input);padding:8px 10px;border-radius:4px;border:1px solid var(--border-soft)">${esc(opts.detail)}</p>` : ""}
        </div>`;
      const footer = `
        <button class="btn btn-ghost" id="modal-cancel">取消</button>
        <button class="btn ${danger ? "btn-danger" : "btn-primary"}" id="modal-confirm">${esc(opts.confirmText || "确认")}</button>`;
      openModal(opts.title || "确认操作", body, footer, { danger });
      const cleanup = (val) => {
        closeModal();
        resolve(val);
      };
      $("#modal-confirm").addEventListener("click", () => cleanup(true));
      $("#modal-cancel").addEventListener("click", () => cleanup(false));
      $("#modal-close").addEventListener("click", () => cleanup(false), { once: true });
    });
  }

  // 表单弹窗
  function formDialog(title, formHtml, opts) {
    return new Promise((resolve) => {
      opts = opts || {};
      const footer = `
        <button class="btn btn-ghost" id="modal-cancel">取消</button>
        <button class="btn btn-primary" id="modal-confirm">${esc(opts.confirmText || "提交")}</button>`;
      openModal(title, formHtml, footer, opts);
      const done = (val) => {
        closeModal();
        resolve(val);
      };
      $("#modal-confirm").addEventListener("click", () => {
        // 收集表单内所有 [name] 字段
        const data = {};
        $$("#modal-body [name]").forEach((el) => {
          if (el.type === "checkbox") data[el.name] = el.checked;
          else data[el.name] = el.value;
        });
        if (opts.validate && opts.validate(data) === false) return;
        done(data);
      });
      $("#modal-cancel").addEventListener("click", () => done(null));
      $("#modal-close").addEventListener("click", () => done(null), { once: true });
      // 自动聚焦第一个输入框
      const first = $("#modal-body input, #modal-body select, #modal-body textarea");
      if (first) setTimeout(() => first.focus(), 50);
    });
  }

  // ============================================================
  // 路由系统（基于 hash）
  // ============================================================
  const ROUTES = ["dashboard", "peers", "roa", "config", "api-keys",
    "audit-logs", "monitor", "wireguard", "users"];

  function currentRoute() {
    const hash = location.hash.replace(/^#/, "");
    return ROUTES.includes(hash) ? hash : "dashboard";
  }

  function navigate(route) {
    if (!ROUTES.includes(route)) route = "dashboard";
    location.hash = route;
    // hashchange 会触发 router
    if (currentRoute() === route) router();
  }

  function router() {
    // 停止所有自动刷新
    clearTimers();
    const route = currentRoute();
    STATE.route = route;

    // 更新标题
    $("#topbar-title").textContent = TITLES[route] || "后台管理";

    // 更新侧边栏激活态
    $$(".nav-item").forEach((a) => {
      a.classList.toggle("active", a.dataset.route === route);
    });

    // 移动端关闭侧边栏
    closeSidebar();

    // 渲染对应页面
    const fn = PAGES[route];
    if (fn) {
      fn();
    } else {
      main().innerHTML = emptyState("页面不存在", "404");
    }
  }

  function clearTimers() {
    if (STATE.dashboardTimer) { clearInterval(STATE.dashboardTimer); STATE.dashboardTimer = null; }
    if (STATE.monitorTimer) { clearInterval(STATE.monitorTimer); STATE.monitorTimer = null; }
  }

  // ============================================================
  // 认证：登录状态检查
  // ============================================================
  async function checkSession() {
    try {
      const d = await GET("/admin/api/session");
      if (d && d.logged_in) {
        STATE.user = { username: d.username, role: d.role };
        return true;
      }
    } catch (_) { /* 忽略 */ }
    STATE.user = null;
    return false;
  }

  function showLogin() {
    clearTimers();
    $("#login-view").hidden = false;
    $("#app-view").hidden = true;
    $("#login-username").value = "";
    $("#login-password").value = "";
    $("#login-error").hidden = true;
    setTimeout(() => $("#login-username").focus(), 50);
  }

  function showApp() {
    $("#login-view").hidden = true;
    $("#app-view").hidden = false;
    // 渲染用户信息
    if (STATE.user) {
      $("#sidebar-username").textContent = STATE.user.username;
      $("#sidebar-role").textContent = STATE.user.role;
    }
    router();
  }

  async function doLogin(e) {
    if (e) e.preventDefault();
    const username = $("#login-username").value.trim();
    const password = $("#login-password").value;
    const errBox = $("#login-error");
    const btn = $("#login-submit");

    if (!username || !password) {
      errBox.textContent = "用户名和密码不能为空";
      errBox.hidden = false;
      return;
    }

    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "登录中…";
    btn.querySelector(".spin").hidden = false;

    try {
      const d = await POST("/admin/api/login", { username, password });
      STATE.user = { username: d.username, role: d.role };
      errBox.hidden = true;
      toastOk("登录成功", `欢迎回来，${d.username}`);
      showApp();
    } catch (err) {
      errBox.textContent = err.message || "登录失败";
      errBox.hidden = false;
    } finally {
      btn.disabled = false;
      btn.querySelector(".btn-text").textContent = "登录";
      btn.querySelector(".spin").hidden = true;
    }
  }

  async function doLogout() {
    const ok = await confirmDialog({
      title: "退出登录？",
      message: "将清除当前会话，需要重新登录才能访问后台。",
      confirmText: "退出",
    });
    if (!ok) return;
    try {
      await POST("/admin/api/logout");
    } catch (_) { /* 忽略 */ }
    STATE.user = null;
    toastInfo("已退出登录");
    showLogin();
  }

  // ============================================================
  // 侧边栏（移动端折叠）
  // ============================================================
  function toggleSidebar() {
    const sb = $("#sidebar");
    const ov = $("#sidebar-overlay");
    const open = sb.classList.toggle("open");
    ov.hidden = !open;
  }
  function closeSidebar() {
    const sb = $("#sidebar");
    if (sb.classList.contains("open")) {
      sb.classList.remove("open");
      $("#sidebar-overlay").hidden = true;
    }
  }

  // ============================================================
  // 页面渲染器集合
  // ============================================================
  const PAGES = {};

  // ------------------------------------------------------------
  // 1. 仪表盘
  // ------------------------------------------------------------
  PAGES.dashboard = async function () {
    main().innerHTML = loading("加载仪表盘数据…");
    await renderDashboard();

    // 5 秒自动刷新
    STATE.dashboardTimer = setInterval(async () => {
      // 仅在当前仍是仪表盘时刷新
      if (currentRoute() === "dashboard") {
        try { await renderDashboard(true); } catch (_) { /* 静默 */ }
      }
    }, 5000);
  };

  async function renderDashboard(silent) {
    let d;
    try {
      d = await GET("/admin/api/dashboard");
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      if (!silent) main().innerHTML = errorBox(err.message);
      return;
    }
    const m = d.metrics || {};
    const node = d.node || {};
    const roa = d.roa || {};
    const mem = m.memory || {};
    const disk = m.disk || {};
    const net = m.network || {};
    const bh = (node.bird_health) || {};

    const cpuLevel = percentLevel(m.cpu_percent);
    const memLevel = percentLevel(mem.percent);
    const diskLevel = percentLevel(disk.percent);

    main().innerHTML = `
      <div class="stat-grid">
        <div class="stat-card ${cpuLevel}">
          <div class="stat-label">CPU 使用率</div>
          <div class="stat-value ${cpuLevel}">${esc(m.cpu_percent ?? "0")}<span class="stat-unit">%</span></div>
          <div class="progress"><div class="progress-bar ${cpuLevel}" style="width:${esc(m.cpu_percent || 0)}%"></div></div>
        </div>
        <div class="stat-card ${memLevel}">
          <div class="stat-label">内存使用</div>
          <div class="stat-value ${memLevel}">${esc(mem.percent ?? 0)}<span class="stat-unit">%</span></div>
          <div class="stat-meta">${formatMB(mem.used_mb)} / ${formatMB(mem.total_mb)}</div>
          <div class="progress"><div class="progress-bar ${memLevel}" style="width:${esc(mem.percent || 0)}%"></div></div>
        </div>
        <div class="stat-card ${diskLevel}">
          <div class="stat-label">磁盘使用</div>
          <div class="stat-value ${diskLevel}">${esc(disk.percent ?? 0)}<span class="stat-unit">%</span></div>
          <div class="stat-meta">${esc(disk.used_gb)} / ${esc(disk.total_gb)} GB</div>
          <div class="progress"><div class="progress-bar ${diskLevel}" style="width:${esc(disk.percent || 0)}%"></div></div>
        </div>
        <div class="stat-card ${m.bird_reachable ? 'ok' : 'fail'}">
          <div class="stat-label">BIRD 状态</div>
          <div class="stat-value ${m.bird_reachable ? 'ok' : 'fail'}">${m.bird_reachable ? "在线" : "离线"}</div>
          <div class="stat-meta">${esc(m.bird_version || "—")}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">路由总数</div>
          <div class="stat-value">${formatNum(m.routes_count)}</div>
          <div class="stat-meta">本节点路由表</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">BGP Peer</div>
          <div class="stat-value">${esc(m.peers_established ?? 0)}<span class="stat-unit"> / ${esc(m.peers_count ?? 0)}</span></div>
          <div class="stat-meta">已建立 / 总数</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">网络流量 (RX)</div>
          <div class="stat-value" style="font-size:18px">${formatBytes(net.rx_bytes)}</div>
          <div class="stat-meta">已接收</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">网络流量 (TX)</div>
          <div class="stat-value" style="font-size:18px">${formatBytes(net.tx_bytes)}</div>
          <div class="stat-meta">已发送</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">系统运行时间</div>
          <div class="stat-value" style="font-size:18px">${esc(m.uptime || "—")}</div>
          <div class="stat-meta">活动 API 密钥：${esc(d.api_keys_active ?? 0)}</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">节点信息</h3>
          </div>
          <dl class="deflist">
            <dt>站点名称</dt><dd>${esc(node.site_name || "—")}</dd>
            <dt>节点名称</dt><dd>${esc(node.node_name || "—")}</dd>
            <dt>节点 ASN</dt><dd class="mono">${esc(node.node_asn || "—")}</dd>
            <dt>运行模式</dt><dd>${node.effective_mode === "demo"
              ? badge("warn", "演示模式") : badge("ok", "真实模式")}</dd>
            <dt>BIRD 套接字</dt><dd class="mono">${esc(node.bird_socket || "—")}</dd>
            <dt>BIRD 受限模式</dt><dd>${node.bird_restricted ? badge("ok", "已开启") : badge("warn", "未开启")}</dd>
          </dl>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="card-title">ROA 状态</h3>
            <a href="#roa" class="btn btn-ghost btn-xs">详情 →</a>
          </div>
          ${renderRoaSummary(roa)}
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">最近审计日志</h3>
            <a href="#audit-logs" class="btn btn-ghost btn-xs">全部 →</a>
          </div>
          ${renderRecentLogs(d.recent_logs || [])}
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="card-title">ROA 更新历史</h3>
            <a href="#roa" class="btn btn-ghost btn-xs">详情 →</a>
          </div>
          ${renderRoaHistory(d.recent_roa_updates || [])}
        </div>
      </div>`;
  }

  function renderRoaSummary(roa) {
    const v4 = roa.v4 || {};
    const v6 = roa.v6 || {};
    return `
      <dl class="deflist">
        <dt>IPv4 ROA</dt><dd>${v4.exists
          ? badge("ok", `${formatNum(v4.entries)} 条`)
          : badge("fail", "不存在")}</dd>
        <dt>IPv6 ROA</dt><dd>${v6.exists
          ? badge("ok", `${formatNum(v6.entries)} 条`)
          : badge("fail", "不存在")}</dd>
        <dt>IPv4 更新时间</dt><dd class="mono">${esc(v4.last_updated || "—")}</dd>
        <dt>IPv6 更新时间</dt><dd class="mono">${esc(v6.last_updated || "—")}</dd>
      </dl>`;
  }

  function renderRecentLogs(logs) {
    if (!logs.length) return emptyState("暂无审计日志", "📋");
    return `<div class="table-wrap" style="border:none"><table class="data">
      <thead><tr><th>时间</th><th>用户</th><th>操作</th><th>目标</th></tr></thead>
      <tbody>
        ${logs.map((l) => `<tr>
          <td class="mono" style="font-size:11.5px">${esc(l.timestamp || "—")}</td>
          <td>${esc(l.username || "—")}</td>
          <td><span class="badge badge-info">${esc(l.action || "—")}</span></td>
          <td class="mono" style="font-size:12px">${esc(l.target || "—")}</td>
        </tr>`).join("")}
      </tbody></table></div>`;
  }

  function renderRoaHistory(history) {
    if (!history.length) return emptyState("暂无 ROA 更新记录", "✓");
    return `<div class="table-wrap" style="border:none"><table class="data">
      <thead><tr><th>时间</th><th>状态</th><th>v4</th><th>v6</th><th>触发</th></tr></thead>
      <tbody>
        ${history.map((h) => `<tr>
          <td class="mono" style="font-size:11.5px">${esc(h.timestamp || "—")}</td>
          <td>${badge(h.status, h.status)}</td>
          <td class="mono">${formatNum(h.entries_v4)}</td>
          <td class="mono">${formatNum(h.entries_v6)}</td>
          <td>${esc(h.triggered_by || "—")}</td>
        </tr>`).join("")}
      </tbody></table></div>`;
  }

  // ------------------------------------------------------------
  // 2. BGP 会话管理
  // ------------------------------------------------------------
  PAGES.peers = async function () {
    main().innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">BGP 会话列表</h3>
          <div class="card-actions">
            <button class="btn btn-ghost btn-sm" id="peers-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="peers-table">${loading("加载 BGP 会话…")}</div>
      </div>`;
    $("#peers-refresh").addEventListener("click", () => PAGES.peers());
    await loadPeers();
  };

  async function loadPeers() {
    const box = $("#peers-table");
    if (!box) return;
    try {
      const d = await GET("/admin/api/peers");
      const peers = d.peers || [];
      if (!peers.length) {
        box.innerHTML = emptyState("没有 BGP 会话", "⇄");
        return;
      }
      box.innerHTML = `<div class="table-wrap"><table class="data">
        <thead><tr>
          <th>名称</th><th>状态</th><th>地址</th><th>AS</th>
          <th>接收/发送</th><th>Since</th><th class="col-actions">操作</th>
        </tr></thead>
        <tbody>
          ${peers.map((p) => `<tr>
            <td class="mono">${esc(p.name || "—")}</td>
            <td>${p.established
              ? badge("established", "Established")
              : badge(p.state || "down", p.state || "Down")}</td>
            <td class="mono">${esc(p.neighbor_address || p.neighbor || "—")}</td>
            <td class="mono">${esc(p.asn || p.neighbor_as || "—")}</td>
            <td class="mono" style="font-size:12px">${formatNum(p.rx_routes || p.received)} / ${formatNum(p.tx_routes || p.exported)}</td>
            <td class="mono" style="font-size:11.5px">${esc(p.since || "—")}</td>
            <td class="col-actions">
              <div class="row-actions">
                ${p.established
                  ? `<button class="btn btn-ghost btn-xs" data-action="disable" data-name="${esc(p.name)}">禁用</button>`
                  : `<button class="btn btn-success btn-xs" data-action="enable" data-name="${esc(p.name)}">启用</button>`}
                <button class="btn btn-ghost btn-xs" data-action="restart" data-name="${esc(p.name)}">重启</button>
              </div>
            </td>
          </tr>`).join("")}
        </tbody></table></div>`;

      // 绑定操作按钮
      $$("#peers-table [data-action]").forEach((btn) => {
        btn.addEventListener("click", () => peerAction(btn.dataset.action, btn.dataset.name));
      });
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  async function peerAction(action, name) {
    const labels = {
      enable: "启用", disable: "禁用", restart: "重启",
    };
    const danger = action === "disable" || action === "restart";
    const ok = await confirmDialog({
      title: `${labels[action]} BGP 会话`,
      message: `即将对 peer 执行「${labels[action]}」操作，这会影响 BGP 路由。`,
      detail: name,
      confirmText: labels[action],
      danger,
    });
    if (!ok) return;

    try {
      const res = await POST(`/admin/api/peers/${encodeURIComponent(name)}/${action}`);
      if (res.ok) {
        toastOk(`${labels[action]}成功`, `peer ${name} 已${labels[action]}`);
      } else {
        toastErr(`${labels[action]}失败`, res.error || "未知错误");
      }
      // 刷新列表
      await loadPeers();
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr(`${labels[action]}失败`, err.message);
    }
  }

  // ------------------------------------------------------------
  // 3. ROA 管理
  // ------------------------------------------------------------
  PAGES.roa = async function () {
    main().innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">ROA 表状态</h3>
          <div class="card-actions">
            <button class="btn btn-primary btn-sm" id="roa-update">⬇ 手动更新</button>
            <button class="btn btn-ghost btn-sm" id="roa-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="roa-status">${loading("加载 ROA 状态…")}</div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">更新历史</h3>
        </div>
        <div id="roa-history-box">${loading("加载更新历史…")}</div>
      </div>`;
    $("#roa-refresh").addEventListener("click", () => PAGES.roa());
    $("#roa-update").addEventListener("click", roaUpdate);
    await Promise.all([loadRoaStatus(), loadRoaHistory()]);
  };

  async function loadRoaStatus() {
    const box = $("#roa-status");
    if (!box) return;
    try {
      const roa = await GET("/admin/api/roa");
      const v4 = roa.v4 || {};
      const v6 = roa.v6 || {};
      box.innerHTML = `
        <div class="grid-2">
          <div>
            <h4 class="blk-title" style="margin-top:0">IPv4 ROA</h4>
            <dl class="deflist">
              <dt>状态</dt><dd>${v4.exists ? badge("ok", "存在") : badge("fail", "不存在")}</dd>
              <dt>条目数</dt><dd class="mono">${formatNum(v4.entries)}</dd>
              <dt>文件路径</dt><dd class="mono" style="font-size:11.5px">${esc(v4.path || "—")}</dd>
              <dt>最后更新</dt><dd class="mono">${esc(v4.last_updated || "—")}（${timeAgo(v4.last_updated)}）</dd>
            </dl>
          </div>
          <div>
            <h4 class="blk-title" style="margin-top:0">IPv6 ROA</h4>
            <dl class="deflist">
              <dt>状态</dt><dd>${v6.exists ? badge("ok", "存在") : badge("fail", "不存在")}</dd>
              <dt>条目数</dt><dd class="mono">${formatNum(v6.entries)}</dd>
              <dt>文件路径</dt><dd class="mono" style="font-size:11.5px">${esc(v6.path || "—")}</dd>
              <dt>最后更新</dt><dd class="mono">${esc(v6.last_updated || "—")}（${timeAgo(v6.last_updated)}）</dd>
            </dl>
          </div>
        </div>
        ${roa.update_command ? `
          <h4 class="blk-title">自动更新 Cron 命令</h4>
          <pre class="raw">${esc(roa.update_command)}</pre>` : ""}`;
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  async function loadRoaHistory() {
    const box = $("#roa-history-box");
    if (!box) return;
    try {
      const d = await GET("/admin/api/roa/history?limit=50");
      const history = d.history || [];
      if (!history.length) {
        box.innerHTML = emptyState("暂无 ROA 更新记录", "✓");
        return;
      }
      box.innerHTML = `<div class="table-wrap"><table class="data">
        <thead><tr><th>时间</th><th>状态</th><th>IPv4 条目</th><th>IPv6 条目</th><th>触发方式</th><th>详情</th></tr></thead>
        <tbody>
          ${history.map((h) => `<tr>
            <td class="mono" style="font-size:11.5px">${esc(h.timestamp || "—")}</td>
            <td>${badge(h.status, h.status)}</td>
            <td class="mono">${formatNum(h.entries_v4)}</td>
            <td class="mono">${formatNum(h.entries_v6)}</td>
            <td>${esc(h.triggered_by || "—")}</td>
            <td class="mono" style="font-size:11px;max-width:280px;overflow:hidden;text-overflow:ellipsis">${esc(h.error_msg || "—")}</td>
          </tr>`).join("")}
        </tbody></table></div>`;
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  async function roaUpdate() {
    const ok = await confirmDialog({
      title: "手动更新 ROA 数据",
      message: "将从 dn42.burble.com 下载最新的 ROA 表并触发 BIRD 重新加载配置。这可能需要数秒。",
      confirmText: "开始更新",
    });
    if (!ok) return;
    toastInfo("开始更新", "正在下载 ROA 数据…");
    try {
      const res = await POST("/admin/api/roa/update");
      const v4ok = res.v4 && res.v4.ok;
      const v6ok = res.v6 && res.v6.ok;
      if (v4ok && v6ok) {
        toastOk("更新成功", `IPv4: ${res.v4.entries} 条, IPv6: ${res.v6.entries} 条`);
      } else if (v4ok || v6ok) {
        toastWarn("部分成功", `IPv4: ${v4ok ? res.v4.entries + " 条" : "失败"}, IPv6: ${v6ok ? res.v6.entries + " 条" : "失败"}`);
      } else {
        toastErr("更新失败", (res.v4 && res.v4.error) || (res.v6 && res.v6.error) || "未知错误");
      }
      await Promise.all([loadRoaStatus(), loadRoaHistory()]);
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("更新失败", err.message);
    }
  }

  // ------------------------------------------------------------
  // 4. 配置管理
  // ------------------------------------------------------------
  PAGES.config = async function () {
    main().innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">当前配置</h3>
          <div class="card-actions">
            <button class="btn btn-ghost btn-sm" id="config-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="config-box">${loading("加载配置…")}</div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">配置覆盖</h3>
          <button class="btn btn-primary btn-sm" id="config-add">+ 新增覆盖</button>
        </div>
        <div id="config-overrides-box">${loading("加载覆盖…")}</div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">BIRD 配置 & 缓存</h3>
          <div class="card-actions">
            <button class="btn btn-ghost btn-sm" id="bird-config-btn">查看 bird.conf</button>
            <button class="btn btn-ghost btn-sm" id="bird-reload-btn">重载 BIRD</button>
            <button class="btn btn-ghost btn-sm" id="cache-clear-btn">清空缓存</button>
          </div>
        </div>
        <div id="bird-config-box" hidden><pre class="raw" id="bird-config-pre"></pre></div>
      </div>`;
    $("#config-refresh").addEventListener("click", () => PAGES.config());
    $("#config-add").addEventListener("click", configAddOverride);
    $("#bird-config-btn").addEventListener("click", toggleBirdConfig);
    $("#bird-reload-btn").addEventListener("click", birdReload);
    $("#cache-clear-btn").addEventListener("click", cacheClear);
    await loadConfig();
  };

  async function loadConfig() {
    const box = $("#config-box");
    if (!box) return;
    try {
      const d = await GET("/admin/api/config");
      const cur = d.current || {};
      const ovBox = $("#config-overrides-box");
      const overrides = d.overrides || [];

      // 当前配置表格
      const rows = Object.keys(cur).map((k) => {
        const v = cur[k];
        const display = typeof v === "boolean" ? (v ? "是" : "否") : esc(v ?? "—");
        return `<tr><td class="mono">${esc(k)}</td><td class="mono">${display}</td></tr>`;
      });
      box.innerHTML = `<div class="table-wrap"><table class="data">
        <thead><tr><th>配置项</th><th>当前值</th></tr></thead>
        <tbody>${rows.join("")}</tbody></table></div>`;

      // 覆盖列表
      if (!overrides.length) {
        ovBox.innerHTML = emptyState("暂无配置覆盖", "⚙");
      } else {
        ovBox.innerHTML = `<div class="table-wrap"><table class="data">
          <thead><tr><th>配置项</th><th>覆盖值</th><th>类型</th><th>更新时间</th><th>更新者</th><th class="col-actions">操作</th></tr></thead>
          <tbody>
            ${overrides.map((o) => `<tr>
              <td class="mono">${esc(o.key)}</td>
              <td class="mono">${esc(o.value)}</td>
              <td>${esc(o.value_type || "string")}</td>
              <td class="mono" style="font-size:11.5px">${esc(o.updated_at || "—")}</td>
              <td>${esc(o.updated_by || "—")}</td>
              <td class="col-actions">
                <button class="btn btn-ghost btn-xs" data-edit-key="${esc(o.key)}" data-edit-value="${esc(o.value)}" data-edit-type="${esc(o.value_type || "string")}">编辑</button>
                <button class="btn btn-danger btn-xs" data-del-id="${esc(o.id)}" data-del-key="${esc(o.key)}">删除</button>
              </td>
            </tr>`).join("")}
          </tbody></table></div>`;
        $$("#config-overrides-box [data-edit-key]").forEach((b) => {
          b.addEventListener("click", () => configEditOverride(b.dataset));
        });
        $$("#config-overrides-box [data-del-id]").forEach((b) => {
          b.addEventListener("click", () => configDelOverride(b.dataset.delId, b.dataset.delKey));
        });
      }
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  // 允许覆盖的配置项（与后端 allowed_keys 一致）
  const ALLOWED_CONFIG_KEYS = {
    CACHE_TTL_STATUS: "int", CACHE_TTL_PROTOCOLS: "int", CACHE_TTL_ROUTES: "int",
    CACHE_TTL_LOOKUP: "int", CACHE_TTL_MEMORY: "int", RATE_LIMIT: "int",
    SITE_NAME: "string", NODE_NAME: "string",
  };

  async function configAddOverride() {
    const options = Object.keys(ALLOWED_CONFIG_KEYS)
      .map((k) => `<option value="${esc(k)}">${esc(k)}</option>`).join("");
    const form = `
      <div class="field">
        <span class="field-label">配置项</span>
        <select name="key" required><option value="">请选择…</option>${options}</select>
      </div>
      <div class="field">
        <span class="field-label">值</span>
        <input type="text" name="value" required placeholder="输入覆盖值" />
      </div>
      <p class="dim text-sm">说明：覆盖值会持久化保存，部分缓存/限流配置会即时生效，其余在服务重启后生效。</p>`;
    const data = await formDialog("新增配置覆盖", form, { confirmText: "保存" });
    if (!data) return;
    try {
      const t = ALLOWED_CONFIG_KEYS[data.key] || "string";
      await PUT("/admin/api/config", { key: data.key, value: data.value, type: t });
      toastOk("保存成功", `${data.key} = ${data.value}`);
      await loadConfig();
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("保存失败", err.message);
    }
  }

  async function configEditOverride(ds) {
    const options = Object.keys(ALLOWED_CONFIG_KEYS)
      .map((k) => `<option value="${esc(k)}" ${k === ds.editKey ? "selected" : ""}>${esc(k)}</option>`).join("");
    const form = `
      <div class="field">
        <span class="field-label">配置项</span>
        <select name="key" required><option value="">请选择…</option>${options}</select>
      </div>
      <div class="field">
        <span class="field-label">值</span>
        <input type="text" name="value" required value="${esc(ds.editValue)}" />
      </div>`;
    const data = await formDialog("编辑配置覆盖", form, { confirmText: "保存" });
    if (!data) return;
    try {
      const t = ALLOWED_CONFIG_KEYS[data.key] || "string";
      await PUT("/admin/api/config", { key: data.key, value: data.value, type: t });
      toastOk("更新成功", `${data.key} = ${data.value}`);
      await loadConfig();
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("更新失败", err.message);
    }
  }

  async function configDelOverride(id, key) {
    const ok = await confirmDialog({
      title: "删除配置覆盖？",
      message: `将删除配置项「${key}」的覆盖值，恢复使用默认值。`,
      detail: key,
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    // 后端未提供 DELETE 接口，通过 PUT 设空值近似（实际依赖后端）。
    // 这里尝试调用通用方式：若后端不支持则提示。
    try {
      // 尝试通过覆盖为空实现"删除"语义（后端 value_type 保留）
      await PUT("/admin/api/config", { key, value: "", type: "string" });
      toastOk("已重置", `${key} 已清空`);
      await loadConfig();
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("操作失败", err.message);
    }
  }

  async function toggleBirdConfig() {
    const box = $("#bird-config-box");
    const pre = $("#bird-config-pre");
    if (!box.hidden) { box.hidden = true; return; }
    pre.textContent = "加载中…";
    box.hidden = false;
    try {
      const d = await GET("/admin/api/bird/config");
      pre.textContent = d.content || "(空)";
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      pre.textContent = "加载失败：" + err.message;
    }
  }

  async function birdReload() {
    const ok = await confirmDialog({
      title: "重载 BIRD 配置？",
      message: "将执行 birdc configure，重新加载 BIRD 配置文件。错误的配置可能导致 BIRD 异常。",
      confirmText: "重载",
      danger: true,
    });
    if (!ok) return;
    try {
      const res = await POST("/admin/api/bird/reload");
      if (res.ok) toastOk("重载成功", res.output || "BIRD 配置已重新加载");
      else toastErr("重载失败", res.error || "未知错误");
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("重载失败", err.message);
    }
  }

  async function cacheClear() {
    const ok = await confirmDialog({
      title: "清空缓存？",
      message: "将清空所有 BIRD 查询缓存，下一次请求会重新查询 birdc。",
      confirmText: "清空",
      danger: true,
    });
    if (!ok) return;
    try {
      await POST("/admin/api/cache/clear");
      toastOk("缓存已清空");
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("操作失败", err.message);
    }
  }

  // ------------------------------------------------------------
  // 5. API 密钥管理
  // ------------------------------------------------------------
  PAGES["api-keys"] = async function () {
    main().innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">API 密钥</h3>
          <div class="card-actions">
            <button class="btn btn-primary btn-sm" id="key-create">+ 创建密钥</button>
            <button class="btn btn-ghost btn-sm" id="key-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="keys-box">${loading("加载密钥列表…")}</div>
      </div>`;
    $("#key-refresh").addEventListener("click", () => PAGES["api-keys"]());
    $("#key-create").addEventListener("click", createApiKey);
    await loadApiKeys();
  };

  async function loadApiKeys() {
    const box = $("#keys-box");
    if (!box) return;
    try {
      const d = await GET("/admin/api/api-keys");
      const keys = d.keys || [];
      if (!keys.length) {
        box.innerHTML = emptyState("暂无 API 密钥", "🔑");
        return;
      }
      box.innerHTML = `<div class="table-wrap"><table class="data">
        <thead><tr><th>名称</th><th>密钥</th><th>状态</th><th>创建时间</th><th>最后使用</th><th>创建者</th><th class="col-actions">操作</th></tr></thead>
        <tbody>
          ${keys.map((k) => `<tr>
            <td>${esc(k.name || "未命名")}</td>
            <td>
              <span class="key-masked" id="key-${k.id}">${"•".repeat(16)}</span>
              <button class="btn btn-ghost btn-xs" data-toggle="${k.id}" data-key="${esc(k.key)}">显示</button>
            </td>
            <td>${k.revoked ? badge("revoked", "已吊销") : badge("ok", "有效")}</td>
            <td class="mono" style="font-size:11.5px">${esc(k.created_at || "—")}</td>
            <td class="mono" style="font-size:11.5px">${esc(k.last_used || "—")}</td>
            <td>${esc(k.created_by || "—")}</td>
            <td class="col-actions">
              ${k.revoked ? "" : `<button class="btn btn-danger btn-xs" data-revoke="${k.id}" data-name="${esc(k.name || "")}">吊销</button>`}
            </td>
          </tr>`).join("")}
        </tbody></table></div>`;

      // 切换显示/隐藏密钥
      $$("[data-toggle]").forEach((b) => {
        b.addEventListener("click", () => {
          const span = $(`#key-${b.dataset.toggle}`);
          const shown = b.dataset.shown === "1";
          if (shown) {
            span.textContent = "•".repeat(16);
            b.textContent = "显示";
            b.dataset.shown = "0";
          } else {
            span.textContent = b.dataset.key;
            b.textContent = "隐藏";
            b.dataset.shown = "1";
          }
        });
      });
      // 吊销
      $$("[data-revoke]").forEach((b) => {
        b.addEventListener("click", () => revokeApiKey(b.dataset.revoke, b.dataset.name));
      });
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  async function createApiKey() {
    const form = `
      <div class="field">
        <span class="field-label">密钥名称（可选）</span>
        <input type="text" name="name" placeholder="例如：监控采集" />
      </div>
      <p class="dim text-sm">创建后请立即保存密钥，密钥只显示一次完整的明文。</p>`;
    const data = await formDialog("创建 API 密钥", form, { confirmText: "创建" });
    if (!data) return;
    try {
      const res = await POST("/admin/api/api-keys", { name: data.name });
      // 展示完整密钥（仅一次）
      openModal("密钥已创建", `
        <p style="margin-bottom:10px">请妥善保存以下密钥，关闭后将无法再次查看完整内容：</p>
        <pre class="raw" style="user-select:all">${esc(res.key)}</pre>
        <p class="dim text-sm">名称：${esc(res.name || "未命名")}</p>`,
        `<button class="btn btn-primary" id="modal-copy-key">复制密钥</button>
         <button class="btn btn-ghost" id="modal-close-key">关闭</button>`);
      $("#modal-copy-key").addEventListener("click", () => {
        navigator.clipboard?.writeText(res.key).then(
          () => toastOk("已复制", "密钥已复制到剪贴板"),
          () => toastWarn("复制失败", "请手动选择密钥文本")
        );
      });
      $("#modal-close-key").addEventListener("click", closeModal);
      toastOk("创建成功");
      await loadApiKeys();
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("创建失败", err.message);
    }
  }

  async function revokeApiKey(id, name) {
    const ok = await confirmDialog({
      title: "吊销 API 密钥？",
      message: `吊销后该密钥将立即失效，无法用于 API 调用。此操作不可撤销。`,
      detail: name || `密钥 #${id}`,
      confirmText: "吊销",
      danger: true,
    });
    if (!ok) return;
    try {
      await DEL(`/admin/api/api-keys/${id}`);
      toastOk("已吊销", `密钥「${name || id}」已吊销`);
      await loadApiKeys();
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      toastErr("操作失败", err.message);
    }
  }

  // ------------------------------------------------------------
  // 6. 审计日志
  // ------------------------------------------------------------
  PAGES["audit-logs"] = async function () {
    main().innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">审计日志</h3>
          <div class="card-actions">
            <select id="audit-per-page">
              <option value="20">每页 20 条</option>
              <option value="50" selected>每页 50 条</option>
              <option value="100">每页 100 条</option>
            </select>
            <button class="btn btn-ghost btn-sm" id="audit-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="audit-box">${loading("加载审计日志…")}</div>
      </div>`;
    $("#audit-refresh").addEventListener("click", () => loadAuditLogs());
    $("#audit-per-page").addEventListener("change", (e) => {
      STATE.auditPage = 1;
      loadAuditLogs(parseInt(e.target.value, 10));
    });
    await loadAuditLogs();
  };

  async function loadAuditLogs(perPage) {
    const box = $("#audit-box");
    if (!box) return;
    perPage = perPage || parseInt($("#audit-per-page")?.value, 10) || 50;
    const page = STATE.auditPage;
    box.innerHTML = loading("加载审计日志…");
    try {
      const d = await GET(`/admin/api/audit-logs?page=${page}&per_page=${perPage}`);
      const logs = d.logs || [];
      if (!logs.length) {
        box.innerHTML = emptyState("暂无审计日志", "📋");
        return;
      }
      box.innerHTML = `
        <div class="table-wrap"><table class="data">
          <thead><tr><th>时间</th><th>用户</th><th>操作</th><th>目标</th><th>详情</th><th>IP</th></tr></thead>
          <tbody>
            ${logs.map((l) => `<tr>
              <td class="mono" style="font-size:11.5px;white-space:nowrap">${esc(l.timestamp || "—")}</td>
              <td>${esc(l.username || "—")}</td>
              <td><span class="badge badge-info">${esc(l.action || "—")}</span></td>
              <td class="mono" style="font-size:12px">${esc(l.target || "—")}</td>
              <td class="mono" style="font-size:11px;max-width:300px;overflow:hidden;text-overflow:ellipsis" title="${esc(l.detail || "")}">${esc(l.detail || "—")}</td>
              <td class="mono" style="font-size:11.5px">${esc(l.ip_address || "—")}</td>
            </tr>`).join("")}
          </tbody></table></div>
        ${renderPagination(d, page, perPage)}`;

      // 绑定分页按钮
      $$("#audit-box [data-page]").forEach((b) => {
        b.addEventListener("click", () => {
          STATE.auditPage = parseInt(b.dataset.page, 10);
          loadAuditLogs(perPage);
        });
      });
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  function renderPagination(d, page, perPage) {
    const total = d.total || 0;
    const totalPages = d.total_pages || 1;
    return `
      <div class="pagination">
        <div class="pagination-info">共 ${formatNum(total)} 条 · 第 ${page} / ${totalPages} 页</div>
        <div class="pagination-btns">
          <button class="btn btn-ghost btn-sm" data-page="1" ${page <= 1 ? "disabled" : ""}>首页</button>
          <button class="btn btn-ghost btn-sm" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>上一页</button>
          <button class="btn btn-ghost btn-sm" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""}>下一页</button>
          <button class="btn btn-ghost btn-sm" data-page="${totalPages}" ${page >= totalPages ? "disabled" : ""}>末页</button>
        </div>
      </div>`;
  }

  // ------------------------------------------------------------
  // 7. 系统监控（实时指标 + 历史图表）
  // ------------------------------------------------------------
  PAGES.monitor = async function () {
    main().innerHTML = `
      <div class="stat-grid" id="monitor-stats">${loading("采集实时指标…")}</div>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">历史趋势（最近 24 小时）</h3>
          <div class="card-actions">
            <select id="monitor-hours">
              <option value="6">6 小时</option>
              <option value="24" selected>24 小时</option>
              <option value="48">48 小时</option>
              <option value="168">7 天</option>
            </select>
            <button class="btn btn-ghost btn-sm" id="monitor-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="monitor-charts">${loading("加载历史数据…")}</div>
      </div>`;
    $("#monitor-refresh").addEventListener("click", () => PAGES.monitor());
    $("#monitor-hours").addEventListener("change", (e) => loadMonitorHistory(parseInt(e.target.value, 10)));
    await Promise.all([loadMonitorRealtime(), loadMonitorHistory(24)]);

    // 每 10 秒刷新实时指标
    STATE.monitorTimer = setInterval(async () => {
      if (currentRoute() === "monitor") {
        try { await loadMonitorRealtime(true); } catch (_) {}
      }
    }, 10000);
  };

  async function loadMonitorRealtime(silent) {
    const box = $("#monitor-stats");
    if (!box) return;
    try {
      const m = await GET("/admin/api/metrics");
      const mem = m.memory || {};
      const disk = m.disk || {};
      const net = m.network || {};
      const cpuL = percentLevel(m.cpu_percent);
      const memL = percentLevel(mem.percent);
      const diskL = percentLevel(disk.percent);
      box.innerHTML = `
        <div class="stat-card ${cpuL}">
          <div class="stat-label">CPU</div>
          <div class="stat-value ${cpuL}">${esc(m.cpu_percent ?? 0)}<span class="stat-unit">%</span></div>
          <div class="progress"><div class="progress-bar ${cpuL}" style="width:${esc(m.cpu_percent || 0)}%"></div></div>
        </div>
        <div class="stat-card ${memL}">
          <div class="stat-label">内存</div>
          <div class="stat-value ${memL}">${esc(mem.percent ?? 0)}<span class="stat-unit">%</span></div>
          <div class="stat-meta">${formatMB(mem.used_mb)} / ${formatMB(mem.total_mb)}</div>
          <div class="progress"><div class="progress-bar ${memL}" style="width:${esc(mem.percent || 0)}%"></div></div>
        </div>
        <div class="stat-card ${diskL}">
          <div class="stat-label">磁盘</div>
          <div class="stat-value ${diskL}">${esc(disk.percent ?? 0)}<span class="stat-unit">%</span></div>
          <div class="stat-meta">${esc(disk.used_gb)} / ${esc(disk.total_gb)} GB</div>
          <div class="progress"><div class="progress-bar ${diskL}" style="width:${esc(disk.percent || 0)}%"></div></div>
        </div>
        <div class="stat-card ${m.bird_reachable ? 'ok' : 'fail'}">
          <div class="stat-label">BIRD</div>
          <div class="stat-value ${m.bird_reachable ? 'ok' : 'fail'}">${m.bird_reachable ? "在线" : "离线"}</div>
          <div class="stat-meta">${esc(m.bird_version || "—")}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">路由数</div>
          <div class="stat-value">${formatNum(m.routes_count)}</div>
          <div class="stat-meta">Peers: ${esc(m.peers_established ?? 0)}/${esc(m.peers_count ?? 0)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">网络 RX/TX</div>
          <div class="stat-value" style="font-size:15px">${formatBytes(net.rx_bytes)}<br><span class="muted">${formatBytes(net.tx_bytes)}</span></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">运行时间</div>
          <div class="stat-value" style="font-size:16px">${esc(m.uptime || "—")}</div>
          <div class="stat-meta">更新于 ${esc((m.timestamp || "").slice(11, 19))}</div>
        </div>`;
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      if (!silent) box.innerHTML = errorBox(err.message);
    }
  }

  async function loadMonitorHistory(hours) {
    const box = $("#monitor-charts");
    if (!box) return;
    try {
      const d = await GET(`/admin/api/metrics/history?hours=${hours}`);
      const history = d.history || [];
      if (!history.length) {
        box.innerHTML = emptyState("暂无历史监控数据", "📈");
        return;
      }
      const cpuVals = history.map((h) => Number(h.cpu_percent) || 0);
      const memVals = history.map((h) => Number(h.memory_percent) || 0);
      const diskVals = history.map((h) => Number(h.disk_percent) || 0);
      const peerVals = history.map((h) => Number(h.peers_established) || 0);
      const labels = history.map((h) => (h.timestamp || "").slice(11, 16));

      box.innerHTML = `
        <div class="chart-wrap">
          <div class="chart-title">CPU 使用率 (%)</div>
          ${renderLineChart(cpuVals, labels, "#2f81f7", 100)}
        </div>
        <div class="chart-wrap">
          <div class="chart-title">内存使用率 (%)</div>
          ${renderLineChart(memVals, labels, "#3fb950", 100)}
        </div>
        <div class="chart-wrap">
          <div class="chart-title">磁盘使用率 (%)</div>
          ${renderLineChart(diskVals, labels, "#d29922", 100)}
        </div>
        <div class="grid-2">
          <div class="chart-wrap">
            <div class="chart-title">已建立 Peer 数</div>
            ${renderBarChart(peerVals, labels, "green")}
          </div>
          <div class="chart-wrap">
            <div class="chart-title">CPU 柱状图 (%)</div>
            ${renderBarChart(cpuVals, labels, "")}
          </div>
        </div>`;
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  // SVG 折线图（无需 ECharts）
  function renderLineChart(values, labels, color, maxY) {
    const W = 800, H = 200, PAD = 28;
    if (!values.length) return emptyState("无数据", "—");
    const max = maxY != null ? Math.max(maxY, ...values) : Math.max(...values, 1);
    const min = 0;
    const span = Math.max(max - min, 1);
    const stepX = (W - PAD * 2) / Math.max(values.length - 1, 1);
    const pts = values.map((v, i) => {
      const x = PAD + i * stepX;
      const y = H - PAD - ((v - min) / span) * (H - PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const path = "M" + pts.join(" L");
    const areaPath = `${path} L${PAD + (values.length - 1) * stepX},${H - PAD} L${PAD},${H - PAD} Z`;
    // 网格线
    const gridLines = [0, 25, 50, 75, 100]
      .filter((p) => p <= max)
      .map((p) => {
        const y = H - PAD - (p / span) * (H - PAD);
        return `<line x1="${PAD}" y1="${y}" x2="${W - PAD}" y2="${y}" stroke="#21262d" stroke-width="1"/><text x="4" y="${y + 3}" fill="#6e7681" font-size="9">${p}</text>`;
      }).join("");
    // X 轴标签（最多 8 个）
    const labelStep = Math.ceil(labels.length / 8);
    const xLabels = labels.map((l, i) => {
      if (i % labelStep !== 0 && i !== labels.length - 1) return "";
      const x = PAD + i * stepX;
      return `<text x="${x}" y="${H - 8}" fill="#6e7681" font-size="9" text-anchor="middle">${esc(l)}</text>`;
    }).join("");

    return `<svg class="line-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="lg-${color.replace('#', '')}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${color}" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      ${gridLines}
      <path d="${areaPath}" fill="url(#lg-${color.replace('#', '')})"/>
      <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      ${xLabels}
    </svg>`;
  }

  // CSS 柱状图
  function renderBarChart(values, labels, colorClass) {
    if (!values.length) return emptyState("无数据", "—");
    const max = Math.max(...values, 1);
    const labelStep = Math.ceil(labels.length / 12);
    return `
      <div class="chart-container">
        ${values.map((v, i) => {
          const h = (v / max) * 100;
          const cls = colorClass === "green" ? "green"
            : v >= 90 ? "red" : v >= 75 ? "yellow" : "";
          const tip = `${labels[i] || ""}: ${v}`;
          return `<div class="bar ${cls}" style="height:${h.toFixed(1)}%" data-tip="${esc(tip)}"></div>`;
        }).join("")}
      </div>
      <div class="chart-axis">
        ${labels.filter((_, i) => i % labelStep === 0 || i === labels.length - 1)
          .map((l) => `<span>${esc(l)}</span>`).join("")}
      </div>`;
  }

  // ------------------------------------------------------------
  // 8. WireGuard
  // ------------------------------------------------------------
  PAGES.wireguard = async function () {
    main().innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">WireGuard 隧道状态</h3>
          <div class="card-actions">
            <button class="btn btn-ghost btn-sm" id="wg-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="wg-box">${loading("加载 WireGuard 状态…")}</div>
      </div>`;
    $("#wg-refresh").addEventListener("click", () => PAGES.wireguard());
    await loadWireguard();
  };

  async function loadWireguard() {
    const box = $("#wg-box");
    if (!box) return;
    try {
      const d = await GET("/admin/api/wireguard");
      if (!d.wg_available) {
        box.innerHTML = `
          <div class="notice warn">WireGuard 未安装或未配置</div>
          <dl class="deflist">
            <dt>状态</dt><dd>${badge("warn", "不可用")}</dd>
            <dt>错误信息</dt><dd class="mono">${esc(d.error || "wg 命令未安装")}</dd>
          </dl>`;
        return;
      }
      const interfaces = d.interfaces || [];
      if (!interfaces.length) {
        box.innerHTML = `
          <div class="notice">WireGuard 已安装，但当前没有活动的隧道接口</div>
          <dl class="deflist">
            <dt>状态</dt><dd>${badge("ok", "已安装")}</dd>
            <dt>错误信息</dt><dd class="mono">${esc(d.error || "无")}</dd>
          </dl>`;
        return;
      }
      box.innerHTML = `
        <div class="notice">检测到 ${interfaces.length} 个 WireGuard 接口</div>
        <div class="table-wrap"><table class="data">
          <thead><tr><th>接口名</th><th>公钥</th><th>Peer 数</th><th>接收</th><th>发送</th><th>状态</th></tr></thead>
          <tbody>
            ${interfaces.map((it) => `<tr>
              <td class="mono">${esc(it.name || "—")}</td>
              <td class="mono" style="font-size:11px">${esc(it.public_key || "—")}</td>
              <td>${formatNum(it.peers || 0)}</td>
              <td class="mono">${formatBytes(it.rx || 0)}</td>
              <td class="mono">${formatBytes(it.tx || 0)}</td>
              <td>${badge("ok", "active")}</td>
            </tr>`).join("")}
          </tbody></table></div>`;
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      box.innerHTML = errorBox(err.message);
    }
  }

  // ------------------------------------------------------------
  // 9. 用户管理（仅超级管理员）
  // ------------------------------------------------------------
  PAGES.users = async function () {
    main().innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">管理员用户</h3>
          <div class="card-actions">
            <button class="btn btn-primary btn-sm" id="user-create">+ 创建用户</button>
            <button class="btn btn-ghost btn-sm" id="user-refresh">↻ 刷新</button>
          </div>
        </div>
        <div id="users-box">${loading("加载用户列表…")}</div>
      </div>`;
    $("#user-refresh").addEventListener("click", () => PAGES.users());
    $("#user-create").addEventListener("click", createUser);
    await loadUsers();
  };

  async function loadUsers() {
    const box = $("#users-box");
    if (!box) return;
    try {
      const d = await GET("/admin/api/users");
      const users = d.users || [];
      if (!users.length) {
        box.innerHTML = emptyState("暂无管理员用户", "👤");
        return;
      }
      const isSuper = STATE.user && STATE.user.role === "superadmin";
      box.innerHTML = `<div class="table-wrap"><table class="data">
        <thead><tr><th>用户名</th><th>角色</th><th>创建时间</th><th>最后登录</th><th class="col-actions">操作</th></tr></thead>
        <tbody>
          ${users.map((u) => {
            const isSelf = STATE.user && u.username === STATE.user.username;
            return `<tr>
              <td>${esc(u.username)}${isSelf ? ' <span class="badge badge-info">当前</span>' : ""}</td>
              <td>${u.role === "superadmin"
                ? badge("purple", "超级管理员")
                : badge("info", "管理员")}</td>
              <td class="mono" style="font-size:11.5px">${esc(u.created_at || "—")}</td>
              <td class="mono" style="font-size:11.5px">${esc(u.last_login || "—")}</td>
              <td class="col-actions">
                <div class="row-actions">
                  <button class="btn btn-ghost btn-xs" data-pw="${u.id}" data-name="${esc(u.username)}">改密</button>
                  <button class="btn btn-danger btn-xs" data-del="${u.id}" data-name="${esc(u.username)}"
                    ${isSelf ? "disabled title='不能删除自己'" : ""}>删除</button>
                </div>
              </td>
            </tr>`;
          }).join("")}
        </tbody></table></div>
        ${!isSuper ? `<div class="notice warn">仅超级管理员可执行用户管理操作。</div>` : ""}`;

      $$("#users-box [data-pw]").forEach((b) => {
        b.addEventListener("click", () => changePassword(b.dataset.pw, b.dataset.name));
      });
      $$("#users-box [data-del]").forEach((b) => {
        b.addEventListener("click", () => deleteUser(b.dataset.del, b.dataset.name));
      });
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      if (err.status === 403) {
        box.innerHTML = `<div class="notice warn">需要超级管理员权限才能查看用户列表。</div>`;
        return;
      }
      box.innerHTML = errorBox(err.message);
    }
  }

  async function createUser() {
    const form = `
      <div class="field">
        <span class="field-label">用户名</span>
        <input type="text" name="username" required placeholder="用户名" autocomplete="off" />
      </div>
      <div class="field">
        <span class="field-label">密码</span>
        <input type="password" name="password" required placeholder="至少 6 位" autocomplete="new-password" />
      </div>
      <div class="field">
        <span class="field-label">角色</span>
        <select name="role">
          <option value="admin">管理员</option>
          <option value="superadmin">超级管理员</option>
        </select>
      </div>`;
    const data = await formDialog("创建管理员用户", form, {
      confirmText: "创建",
      validate: (d) => {
        if (!d.username || !d.password) { toastWarn("请填写完整", "用户名和密码不能为空"); return false; }
        if (d.password.length < 6) { toastWarn("密码太短", "密码长度至少 6 位"); return false; }
        return true;
      },
    });
    if (!data) return;
    try {
      const res = await POST("/admin/api/users", { username: data.username, password: data.password, role: data.role });
      if (res.ok) {
        toastOk("创建成功", `用户 ${data.username} 已创建`);
        await loadUsers();
      } else {
        toastErr("创建失败", res.error || "未知错误");
      }
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      if (err.status === 403) { toastErr("无权限", "仅超级管理员可创建用户"); return; }
      toastErr("创建失败", err.message);
    }
  }

  async function changePassword(id, name) {
    const form = `
      <div class="field">
        <span class="field-label">用户名</span>
        <input type="text" value="${esc(name)}" disabled />
      </div>
      <div class="field">
        <span class="field-label">新密码</span>
        <input type="password" name="password" required placeholder="至少 6 位" autocomplete="new-password" />
      </div>`;
    const data = await formDialog("修改密码", form, {
      confirmText: "确认修改",
      danger: true,
      validate: (d) => {
        if (!d.password) { toastWarn("请输入新密码"); return false; }
        if (d.password.length < 6) { toastWarn("密码太短", "密码长度至少 6 位"); return false; }
        return true;
      },
    });
    if (!data) return;
    try {
      const res = await POST(`/admin/api/users/${id}/password`, { password: data.password });
      if (res.ok) {
        toastOk("修改成功", `用户 ${name} 的密码已更新`);
      } else {
        toastErr("修改失败", res.error || "未知错误");
      }
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      if (err.status === 403) { toastErr("无权限", "仅超级管理员可修改密码"); return; }
      toastErr("修改失败", err.message);
    }
  }

  async function deleteUser(id, name) {
    const ok = await confirmDialog({
      title: "删除管理员用户？",
      message: `将永久删除用户「${name}」，此操作不可撤销。`,
      detail: name,
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    try {
      const res = await DEL(`/admin/api/users/${id}`);
      if (res.ok) {
        toastOk("已删除", `用户 ${name} 已删除`);
        await loadUsers();
      } else {
        toastErr("删除失败", res.error || "未知错误");
      }
    } catch (err) {
      if (err.status === 401) { showLogin(); return; }
      if (err.status === 403) { toastErr("无权限", "仅超级管理员可删除用户"); return; }
      toastErr("删除失败", err.message);
    }
  }

  // ============================================================
  // 事件绑定 & 初始化
  // ============================================================
  function bindEvents() {
    // 登录表单
    $("#login-form").addEventListener("submit", doLogin);
    // 退出登录
    $("#logout-btn").addEventListener("click", doLogout);
    // 侧边栏导航（hash 链接，hashchange 自动触发 router）
    $$(".nav-item").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const route = a.dataset.route;
        if (currentRoute() === route) router();
        else navigate(route);
      });
    });
    // 侧边栏折叠（移动端）
    $("#sidebar-toggle").addEventListener("click", toggleSidebar);
    $("#sidebar-overlay").addEventListener("click", closeSidebar);
    // 顶栏刷新按钮
    $("#refresh-btn").addEventListener("click", () => router());
    // 模态弹窗关闭
    $("#modal-close").addEventListener("click", closeModal);
    $("#modal-overlay").addEventListener("click", (e) => {
      if (e.target === $("#modal-overlay")) closeModal();
    });
    // ESC 关闭弹窗
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!$("#modal-overlay").hidden) closeModal();
      }
    });
    // hash 路由变化
    window.addEventListener("hashchange", router);
  }

  async function init() {
    bindEvents();
    const loggedIn = await checkSession();
    if (loggedIn) {
      showApp();
    } else {
      showLogin();
    }
  }

  // 启动
  init();
})();
