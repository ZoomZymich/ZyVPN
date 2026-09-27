// ZyVPN Frontend Application Logic

let state = {
  nodes: [],
  subscriptions: [],
  settings: {},
  status: { status: "disconnected", logs: [], uptime_seconds: 0 }
};

// Universal API invoker (waits for PyWebView native bridge or falls back to HTTP REST)
function waitForNativeApi(maxMs = 1200) {
  if (window.pywebview && window.pywebview.api) {
    return Promise.resolve(window.pywebview.api);
  }
  return new Promise((resolve) => {
    let settled = false;
    const cleanup = () => {
      window.removeEventListener("pywebviewready", onReady);
      clearInterval(interval);
      clearTimeout(timer);
    };
    const onReady = () => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(window.pywebview ? window.pywebview.api : null);
    };
    window.addEventListener("pywebviewready", onReady);

    // Poll every 35ms in case pywebviewready fired before this listener was added
    const interval = setInterval(() => {
      if (window.pywebview && window.pywebview.api) {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(window.pywebview.api);
      }
    }, 35);

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(window.pywebview ? window.pywebview.api : null);
    }, maxMs);
  });
}

async function callApi(method, ...args) {
  // 1. Direct check: is native API already present?
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api[method] === "function") {
    try {
      return await window.pywebview.api[method](...args);
    } catch (e) {
      console.warn(`Native call ${method} failed, trying HTTP:`, e);
    }
  }

  // 2. Short wait for native bridge if not yet ready
  const nativeApi = await waitForNativeApi(600);
  if (nativeApi && typeof nativeApi[method] === "function") {
    try {
      return await nativeApi[method](...args);
    } catch (e) {
      console.warn(`Native call ${method} failed after wait, trying HTTP:`, e);
    }
  }

  // 3. HTTP REST fallback with full CORS support
  try {
    const res = await fetch(`http://127.0.0.1:18080/api/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ args })
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (e) {
    console.error(`API call ${method} failed:`, e);
    throw e;
  }
}

// Navigation Tabs
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    const target = document.getElementById(`tab-${btn.dataset.tab}`);
    if (target) target.classList.add("active");
    if (btn.dataset.tab === "servers") {
      renderServers();
    } else if (btn.dataset.tab === "checker") {
      renderCheckerServices();
    }
  });
});

document.getElementById("selected-node-trigger").addEventListener("click", () => {
  const serversBtn = document.querySelector('[data-tab="servers"]');
  if (serversBtn) serversBtn.click();
});

// Format Uptime Seconds to HH:MM:SS
function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

// Country Flag and Subtitle Helpers
function getFlagHtml(node) {
  const code = (node.country_code || "").toLowerCase();
  if (code && code !== "un") {
    return `<img src="flags/${code}.png" class="flag-icon" onerror="this.outerHTML='<span class=\\'flag-emoji\\'>${node.flag || '🌐'}</span>'" alt="${code}">`;
  }
  return `<span class="flag-emoji">${node.flag || '🌐'}</span>`;
}

function getNodeSubtitle(node) {
  const trans = (node.transport || "tcp").toLowerCase();
  const sec = (node.security || "none").toLowerCase();
  let protoName = "Vless";
  if (node.protocol === "vmess") protoName = "VMess";
  else if (node.protocol === "trojan") protoName = "Trojan";
  else if (node.protocol === "shadowsocks") protoName = "Shadowsocks";
  else if (node.protocol === "hysteria2") return "Hysteria 2";
  else if (node.protocol === "tuic") return "TUIC";

  let transName = trans.toUpperCase();
  if (trans === "xhttp" || trans === "splithttp") transName = "XHTTP";
  else if (trans === "grpc") transName = "gRPC";
  else if (trans === "ws") transName = "WebSocket";
  else if (trans === "tcp") {
    if (sec === "reality") transName = "TCP Reality";
    else if (sec === "tls") transName = "TCP TLS";
    else transName = "TCP";
  }

  return `${protoName} · ${transName}`;
}

// Render Selected Node in Dashboard
function renderSelectedNode() {
  const selectedId = state.settings.selected_node_id;
  const node = state.nodes.find(n => n.id === selectedId) || state.nodes[0];

  const flagEl = document.getElementById("selected-node-flag");
  const nameEl = document.getElementById("selected-node-name");
  const subEl = document.getElementById("selected-node-subtitle");
  const pingEl = document.getElementById("selected-node-ping");

  if (!node) {
    if (flagEl) flagEl.innerHTML = `<span class="flag-emoji">🌐</span>`;
    nameEl.textContent = "Сервер не выбран";
    if (subEl) subEl.textContent = "Добавьте подписку или сервер";
    pingEl.textContent = "- ms";
    pingEl.className = "ping-tag";
    return;
  }

  if (flagEl) flagEl.innerHTML = getFlagHtml(node);
  nameEl.textContent = node.name || node.country || "VPN Server";
  if (subEl) {
    const subtitle = getNodeSubtitle(node);
    const isXhttp = (node.transport === "xhttp" || node.transport === "splithttp");
    subEl.innerHTML = `<span class="${isXhttp ? 'sub-highlight' : ''}">${escapeHtml(subtitle)}</span>`;
  }

  if (node.ping_ms !== null && node.ping_ms !== undefined) {
    pingEl.innerHTML = `<span style="font-size: 8px;">●</span> ${node.ping_ms} ms`;
    pingEl.className = `ping-tag ${node.ping_ms < 100 ? 'ping-good' : node.ping_ms < 250 ? 'ping-med' : 'ping-bad'}`;
  } else {
    pingEl.textContent = "- ms";
    pingEl.className = "ping-tag";
  }
}

// Setup Filter Pills
function setupFilterPills() {
  const container = document.getElementById("server-filters");
  if (!container || container.dataset.bound) return;
  container.dataset.bound = "1";
  container.querySelectorAll(".filter-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      container.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      state.currentFilter = pill.dataset.filter;
      renderServers();
    });
  });
}

// Render Server List
function renderServers() {
  const container = document.getElementById("servers-container");
  const query = (document.getElementById("search-servers").value || "").toLowerCase().trim();
  container.innerHTML = "";

  document.getElementById("nodes-count-tab").textContent = state.nodes.length;
  
  const countAllEl = document.getElementById("count-all");
  const countXhttpEl = document.getElementById("count-xhttp");
  if (countAllEl) countAllEl.textContent = state.nodes.length;
  if (countXhttpEl) {
    const xhttpTotal = state.nodes.filter(n => n.transport === "xhttp" || n.transport === "splithttp").length;
    countXhttpEl.textContent = xhttpTotal;
  }

  const filter = state.currentFilter || "all";
  const filtered = state.nodes.filter(n => {
    // 1. Text Query Filter
    const matchQuery = !query || (
      (n.name || "").toLowerCase().includes(query) ||
      (n.country || "").toLowerCase().includes(query) ||
      (n.protocol || "").toLowerCase().includes(query) ||
      (n.transport || "").toLowerCase().includes(query) ||
      (n.server || "").toLowerCase().includes(query)
    );
    if (!matchQuery) return false;

    // 2. Category Pill Filter
    if (filter === "xhttp") return (n.transport === "xhttp" || n.transport === "splithttp");
    if (filter === "vless") return (n.protocol === "vless");
    if (filter === "reality") return (n.security === "reality");
    if (filter === "grpc") return (n.transport === "grpc");
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 40px 0;">Серверы не найдены. ${filter === 'xhttp' ? 'В подписке нет XHTTP серверов.' : 'Добавьте подписку во вкладке "Подписки".'}</div>`;
    return;
  }

  filtered.forEach(node => {
    const isSelected = (node.id === state.settings.selected_node_id);
    const card = document.createElement("div");
    card.className = `server-card ${isSelected ? 'selected' : ''}`;
    
    const isXhttp = (node.transport === "xhttp" || node.transport === "splithttp");
    const subtitle = getNodeSubtitle(node);
    const pingText = (node.ping_ms !== null && node.ping_ms !== undefined) ? `<span style="font-size: 8px;">●</span> ${node.ping_ms} ms` : "—";
    const pingClass = (node.ping_ms && node.ping_ms < 100) ? "ping-good" : (node.ping_ms && node.ping_ms < 250) ? "ping-med" : (node.ping_ms ? "ping-bad" : "");

    card.innerHTML = `
      <div class="server-card-left">
        <div class="server-radio"></div>
        <div class="node-flag-box">
          ${getFlagHtml(node)}
        </div>
        <div class="server-card-info">
          <div class="server-name">${escapeHtml(node.name || node.country)}</div>
          <div class="server-subtitle">
            <span class="${isXhttp ? 'sub-highlight' : ''}">${escapeHtml(subtitle)}</span>
          </div>
        </div>
      </div>
      <div class="server-card-right">
        <span class="ping-tag ${pingClass}">${pingText}</span>
        <button class="btn-icon btn-ping-node" data-id="${node.id}" title="Проверить пинг">⚡</button>
        <button class="btn-icon danger btn-del-node" data-id="${node.id}" title="Удалить">✕</button>
      </div>
    `;

    // Click to select
    card.addEventListener("click", async (e) => {
      if (e.target.closest("button")) return;
      await callApi("select_node", node.id);
      state.settings.selected_node_id = node.id;
      renderSelectedNode();
      renderServers();
    });

    // Ping single
    card.querySelector(".btn-ping-node").addEventListener("click", async (e) => {
      e.stopPropagation();
      const btn = card.querySelector(".btn-ping-node");
      btn.style.opacity = "0.5";
      const res = await callApi("ping_single", node.id);
      btn.style.opacity = "1";
      if (res && res.success) {
        node.ping_ms = res.ping_ms;
        renderServers();
        renderSelectedNode();
      }
    });

    // Delete node
    card.querySelector(".btn-del-node").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (confirm(`Удалить сервер "${node.name}"?`)) {
        const res = await callApi("delete_node", node.id);
        if (res && res.success) {
          state.nodes = res.nodes;
          renderServers();
          renderSelectedNode();
        }
      }
    });

    container.appendChild(card);
  });
}

// Render Subscriptions List
function renderSubscriptions() {
  const container = document.getElementById("subs-container");
  container.innerHTML = "";

  if (state.subscriptions.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 13px;">У вас пока нет активных подписок. Вставьте URL выше для загрузки серверов.</div>`;
    return;
  }

  state.subscriptions.forEach(sub => {
    const card = document.createElement("div");
    card.className = "sub-card";
    card.innerHTML = `
      <div>
        <div style="font-weight: 600; font-size: 15px;">${escapeHtml(sub.name)}</div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 3px;">
          ${sub.nodes_count} серверов • Обновлено: ${sub.last_updated || "Недавно"}
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 2px; word-break: break-all;">${escapeHtml(sub.url)}</div>
      </div>
      <div style="display: flex; gap: 8px;">
        <button class="btn-action btn-refresh-sub" data-id="${sub.id}">🔄 Обновить</button>
        <button class="btn-icon danger btn-del-sub" data-id="${sub.id}">Удалить</button>
      </div>
    `;

    card.querySelector(".btn-refresh-sub").addEventListener("click", async () => {
      const btn = card.querySelector(".btn-refresh-sub");
      btn.textContent = "Обновление...";
      btn.disabled = true;
      try {
        const res = await callApi("refresh_subscription", sub.id);
        if (res.success) {
          state.subscriptions = res.subscriptions;
          state.nodes = res.nodes;
          renderSubscriptions();
          renderServers();
          renderSelectedNode();
        } else {
          alert(`Ошибка обновления: ${res.error}`);
        }
      } catch (err) {
        alert(`Ошибка сети: ${err}`);
      } finally {
        btn.textContent = "🔄 Обновить";
        btn.disabled = false;
      }
    });

    card.querySelector(".btn-del-sub").addEventListener("click", async () => {
      if (confirm(`Удалить подписку "${sub.name}" и все её серверы?`)) {
        const res = await callApi("delete_subscription", sub.id);
        if (res.success) {
          state.subscriptions = res.subscriptions;
          state.nodes = res.nodes;
          renderSubscriptions();
          renderServers();
          renderSelectedNode();
        }
      }
    });

    container.appendChild(card);
  });
}

// Add Subscription / Import Single Link
document.getElementById("btn-add-sub").addEventListener("click", async () => {
  const input = document.getElementById("sub-url-input");
  const val = input.value.trim();
  if (!val) return;

  const btn = document.getElementById("btn-add-sub");
  btn.textContent = "Загрузка...";
  btn.disabled = true;

  try {
    if (val.startsWith("http://") || val.startsWith("https://")) {
      const cleanVal = val.trim().replace(/\/+$/, "");
      const isDuplicate = state.subscriptions.some(s => (s.url || "").trim().replace(/\/+$/, "") === cleanVal);
      if (isDuplicate) {
        alert("Эта подписка уже добавлена в ваш список!");
        btn.textContent = "Добавить";
        btn.disabled = false;
        return;
      }

      const res = await callApi("add_subscription", val);
      if (res.success) {
        state.subscriptions = res.subscriptions || [...state.subscriptions, res.subscription];
        state.nodes = res.nodes || state.nodes;
        input.value = "";
        renderSubscriptions();
        renderServers();
        renderSelectedNode();
        alert(`Подписка сохранена! Загружено серверов: ${res.nodes_count || 0}`);
      } else {
        alert(`Не удалось добавить подписку: ${res.error}`);
      }
    } else {
      // Single key or base64 raw text
      const res = await callApi("import_text", val);
      if (res.success) {
        state.nodes = res.nodes;
        input.value = "";
        renderServers();
        renderSelectedNode();
        alert(`Импортировано серверов: ${res.nodes_added}`);
      } else {
        alert(`Ошибка импорта: ${res.error}`);
      }
    }
  } catch (e) {
    alert(`Ошибка: ${e}`);
  } finally {
    btn.textContent = "Добавить";
    btn.disabled = false;
  }
});

// Ping All
document.getElementById("btn-ping-all").addEventListener("click", async () => {
  const btn = document.getElementById("btn-ping-all");
  btn.textContent = "Замер...";
  btn.disabled = true;
  try {
    const res = await callApi("ping_all");
    if (res && res.success) {
      for (const [id, ms] of Object.entries(res.results)) {
        const n = state.nodes.find(node => node.id === id);
        if (n) n.ping_ms = ms;
      }
      renderServers();
      renderSelectedNode();
    }
  } finally {
    btn.textContent = "Пинг всех";
    btn.disabled = false;
  }
});

document.getElementById("btn-quick-ping").addEventListener("click", async () => {
  const selNode = state.nodes.find(n => n.id === state.settings.selected_node_id) || state.nodes[0];
  if (!selNode) return;
  const res = await callApi("ping_single", selNode.id);
  if (res && res.success) {
    selNode.ping_ms = res.ping_ms;
    renderSelectedNode();
    renderServers();
  }
});

// Connect / Disconnect Action
const connectBtn = document.getElementById("main-connect-btn");
const connectLabel = document.getElementById("connect-btn-label");
const headerStatus = document.getElementById("header-status");
const statusText = document.getElementById("status-text");

let isTogglingConnection = false;
async function toggleConnection() {
  if (isTogglingConnection) return;
  isTogglingConnection = true;
  connectBtn.disabled = true;

  try {
    if (state.status.status === "connected") {
      connectBtn.className = "connect-btn";
      connectLabel.textContent = "ОТКЛЮЧЕНИЕ...";
      await callApi("disconnect");
    } else {
      connectBtn.className = "connect-btn connecting";
      connectLabel.textContent = "ПОДКЛЮЧЕНИЕ...";
      const selId = state.settings.selected_node_id;
      const res = await callApi("connect", selId);
      if (!res.success) {
        alert(`Ошибка подключения: ${res.error}`);
      }
    }
    await pollStatus();
  } finally {
    isTogglingConnection = false;
    connectBtn.disabled = false;
  }
}

connectBtn.addEventListener("click", toggleConnection);

// Update Status in UI
function updateStatusUI(st) {
  const prevStatus = state.status ? state.status.status : "";
  state.status = st;
  const s = st.status;

  if (s === "connected") {
    connectBtn.className = "connect-btn connected";
    connectLabel.textContent = "ОТКЛЮЧИТЬ";
    headerStatus.className = "header-status status-connected";
    if (state.ipInfo && state.ipInfo.country_name) {
      statusText.textContent = `${state.ipInfo.flag_emoji || ''} ${state.ipInfo.country_name}`;
    } else {
      statusText.textContent = "Подключено";
    }
  } else if (s === "connecting") {
    connectBtn.className = "connect-btn connecting";
    connectLabel.textContent = "ПОДКЛЮЧЕНИЕ...";
    headerStatus.className = "header-status status-connecting";
    statusText.textContent = "Подключение...";
  } else {
    connectBtn.className = "connect-btn";
    connectLabel.textContent = "ПОДКЛЮЧИТЬ";
    headerStatus.className = "header-status";
    statusText.textContent = "Отключено";
  }

  // Trigger IP refresh when status changes
  if (prevStatus !== s) {
    fetchAndRenderIpInfo();
  }

  // Uptime
  document.getElementById("uptime-display").textContent = formatUptime(st.uptime_seconds || 0);

  // Logs
  if (st.logs && st.logs.length > 0) {
    const logsEl = document.getElementById("logs-container");
    logsEl.textContent = st.logs.join("\n");
    logsEl.scrollTop = logsEl.scrollHeight;
  }
}

// Clear Logs
document.getElementById("btn-clear-logs").addEventListener("click", () => {
  document.getElementById("logs-container").textContent = "";
});

// Search input debounce
document.getElementById("search-servers").addEventListener("input", renderServers);

// Toggles for Routing & TUN
const toggleRouting = document.getElementById("toggle-routing");
const selectRoutingMode = document.getElementById("select-routing-mode");
const toggleTun = document.getElementById("toggle-tun");
const selectDns = document.getElementById("select-dns");

toggleRouting.addEventListener("change", async () => {
  const mode = toggleRouting.checked ? "bypass_ru_lan" : "global";
  selectRoutingMode.value = mode;
  state.settings.routing_mode = mode;
  await callApi("update_settings", { routing_mode: mode });
});

selectRoutingMode.addEventListener("change", async () => {
  const mode = selectRoutingMode.value;
  toggleRouting.checked = (mode === "bypass_ru_lan");
  state.settings.routing_mode = mode;
  await callApi("update_settings", { routing_mode: mode });
});

toggleTun.addEventListener("change", async () => {
  const mode = toggleTun.checked ? "tun" : "proxy";
  state.settings.mode = mode;
  await callApi("update_settings", { mode: mode });
});

selectDns.addEventListener("change", async () => {
  const dns = selectDns.value;
  state.settings.dns_server = dns;
  await callApi("update_settings", { dns_server: dns });
});

// Helpers
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ==========================================
// IP & Country Location Lookup & Display
// ==========================================
let ipFetchInProgress = false;

async function fetchAndRenderIpInfo() {
  if (ipFetchInProgress) return;
  const refreshBtn = document.getElementById("btn-refresh-ip");
  if (refreshBtn) refreshBtn.classList.add("spinning");
  ipFetchInProgress = true;

  try {
    const res = await callApi("get_connection_ip_info");
    if (res) {
      state.ipInfo = res;
      renderIpInfo();
    }
  } catch (e) {
    console.error("IP lookup failed:", e);
  } finally {
    ipFetchInProgress = false;
    if (refreshBtn) refreshBtn.classList.remove("spinning");
  }
}

function renderIpInfo() {
  const flagBox = document.getElementById("ip-flag-box");
  const badgeEl = document.getElementById("ip-badge-status");
  const countryEl = document.getElementById("ip-country-text");
  const ipEl = document.getElementById("ip-address-val");
  const cityEl = document.getElementById("ip-city-val");

  if (!flagBox || !countryEl || !ipEl) return;

  const info = state.ipInfo;
  const isConnected = state.status && state.status.status === "connected";

  if (isConnected && info && info.success) {
    const code = (info.country_code || "").toLowerCase();
    if (code && code !== "un") {
      flagBox.innerHTML = `<img src="flags/${code}.png" class="flag-icon" onerror="this.outerHTML='<span class=\\'flag-emoji\\'>${info.flag_emoji || '🌐'}</span>'" alt="${code}">`;
    } else {
      flagBox.innerHTML = `<span class="flag-emoji">${info.flag_emoji || '🌐'}</span>`;
    }
    badgeEl.textContent = "VPN IP";
    badgeEl.className = "ip-badge-status connected";
    countryEl.textContent = `${info.flag_emoji || ''} ${info.country_name || 'Швеция'}`;
    ipEl.textContent = info.ip || "—";
    cityEl.textContent = info.city ? `(${info.city})` : "";

    // Update Header Status as well
    if (headerStatus && statusText) {
      headerStatus.className = "header-status status-connected";
      statusText.textContent = `${info.flag_emoji || '●'} ${info.country_name || 'Подключено'}`;
    }
  } else if (isConnected) {
    badgeEl.textContent = "Подключение";
    badgeEl.className = "ip-badge-status";
    countryEl.textContent = "Определение IP...";
    ipEl.textContent = "—";
    cityEl.textContent = "";
    flagBox.innerHTML = `<span class="flag-emoji">🌐</span>`;
  } else {
    badgeEl.textContent = "Реальный IP";
    badgeEl.className = "ip-badge-status";
    if (info && info.ip && info.ip !== "—") {
      const code = (info.country_code || "").toLowerCase();
      if (code && code !== "un") {
        flagBox.innerHTML = `<img src="flags/${code}.png" class="flag-icon" onerror="this.outerHTML='<span class=\\'flag-emoji\\'>${info.flag_emoji || '🌐'}</span>'" alt="${code}">`;
      } else {
        flagBox.innerHTML = `<span class="flag-emoji">${info.flag_emoji || '🌐'}</span>`;
      }
      countryEl.textContent = info.country_name || "Без VPN";
      ipEl.textContent = info.ip;
      cityEl.textContent = info.city ? `(${info.city})` : "";
    } else {
      flagBox.innerHTML = `<span class="flag-emoji">🌐</span>`;
      countryEl.textContent = "Защита отключена";
      ipEl.textContent = "—";
      cityEl.textContent = "";
    }
  }
}

const refreshIpBtn = document.getElementById("btn-refresh-ip");
if (refreshIpBtn) {
  refreshIpBtn.addEventListener("click", () => fetchAndRenderIpInfo());
}

// ==========================================
// Service Availability Checker Logic
// ==========================================
const SERVICE_ICONS = {
  discord: `<svg width="22" height="22" viewBox="0 0 24 24" fill="#5865F2"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>`,
  telegram: `<svg width="22" height="22" viewBox="0 0 24 24" fill="#229ED9"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 0 0-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>`,
  youtube: `<svg width="22" height="22" viewBox="0 0 24 24" fill="#FF0000"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`,
  instagram: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E1306C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>`,
  x: `<svg width="22" height="22" viewBox="0 0 24 24" fill="#FFFFFF"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`,
  chatgpt: `<svg width="22" height="22" viewBox="0 0 24 24" fill="#10A37F"><path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 8.795a4.469 4.469 0 0 1 2.34-1.974V12.6a.784.784 0 0 0 .392.68l5.82 3.36-2.02 1.168a.08.08 0 0 1-.073 0l-4.834-2.793A4.504 4.504 0 0 1 2.34 8.795zm16.597 3.855l-5.833-3.387L15.124 8.1a.076.076 0 0 1 .073 0l4.833 2.79a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.417-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 10.13V7.797a.08.08 0 0 1 .033-.061l4.838-2.796a4.5 4.5 0 0 1 6.67 4.737zM8.308 12.84l2.455-1.417 2.455 1.417v2.834l-2.455 1.417-2.455-1.417z"/></svg>`,
  gemini: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 2C12 7.523 7.523 12 2 12C7.523 12 12 16.477 12 22C12 16.477 16.477 12 22 12C16.477 12 12 7.523 12 2Z" fill="url(#gemini-icon-grad)"/><defs><linearGradient id="gemini-icon-grad" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse"><stop stop-color="#4E82EE"/><stop offset="0.5" stop-color="#9B72CB"/><stop offset="1" stop-color="#D96570"/></linearGradient></defs></svg>`,
  spotify: `<svg width="22" height="22" viewBox="0 0 24 24" fill="#1DB954"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>`,
  wikipedia: `<svg width="22" height="22" viewBox="0 0 24 24" fill="#FFFFFF"><path d="M12.09 13.124l2.62-6.862h2.008l-3.666 9.298h-1.895L8.41 8.85l-2.748 6.71H3.766L.1 6.262h2.096l2.58 6.862 2.457-6.862h1.895l-2.73 7.03 2.656-7.03h2.036zm8.144 2.436h3.766v.83h-3.766zm-5.044.83v-.83h2.036v.83z"/></svg>`
};

const DEFAULT_SERVICES = [
  { id: "discord", name: "Discord", desc: "Голосовые каналы и чаты", display_url: "discord.com" },
  { id: "telegram", name: "Telegram", desc: "Мессенджер и каналы", display_url: "web.telegram.org" },
  { id: "youtube", name: "YouTube", desc: "Видеохостинг и стримы", display_url: "youtube.com" },
  { id: "instagram", name: "Instagram", desc: "Фото, Reels, Stories (Meta)", display_url: "instagram.com" },
  { id: "x", name: "Twitter / X", desc: "Социальная сеть X", display_url: "x.com" },
  { id: "chatgpt", name: "ChatGPT", desc: "Нейросеть OpenAI", display_url: "chatgpt.com" },
  { id: "gemini", name: "Google Gemini", desc: "ИИ-чат и генерация (deep check)", display_url: "gemini.google.com" },
  { id: "spotify", name: "Spotify", desc: "Музыкальный стриминг", display_url: "spotify.com" },
  { id: "wikipedia", name: "Wikipedia", desc: "Свободная энциклопедия", display_url: "wikipedia.org" }
];

state.servicesResults = {};

function renderCheckerServices() {
  const container = document.getElementById("services-container");
  if (!container) return;

  container.innerHTML = DEFAULT_SERVICES.map(svc => {
    const res = state.servicesResults[svc.id];
    const icon = SERVICE_ICONS[svc.id] || `<span style="font-size: 18px;">🌐</span>`;

    let statusTag = `<span class="check-tag check-pending">Не проверено</span>`;
    let geminiExtra = "";

    if (res) {
      if (res.running) {
        statusTag = `<span class="check-tag check-running"><span class="spin-dot"></span> ${svc.id === 'gemini' ? 'Проверка диалога...' : 'Проверка...'}</span>`;
      } else if (svc.id === "gemini") {
        if (res.can_chat) {
          statusTag = `<span class="check-tag check-ok">🟢 Чат и AI работают (${res.latency_ms} ms)</span>`;
          geminiExtra = `
            <div class="gemini-badge-row">
              <span class="gemini-sub-badge ok">✓ Веб OK</span>
              <span class="gemini-sub-badge ok">✓ Генерация разрешена</span>
              <span class="gemini-sub-badge ok">✓ Шлюз OK</span>
              <button class="btn-open-gemini-test" title="Проверить отправку сообщений в Gemini">💬 Тест диалога</button>
            </div>
          `;
        } else if (res.web_ok && !res.region_eligible) {
          statusTag = `<span class="check-tag check-warn">🟡 Только сайт (регион заблокирован)</span>`;
          geminiExtra = `
            <div class="gemini-badge-row">
              <span class="gemini-sub-badge ok">✓ Веб OK</span>
              <span class="gemini-sub-badge fail">✕ Регион заблокирован Google</span>
              <button class="btn-open-gemini-test" title="Подробнее">💬 Подробнее</button>
            </div>
          `;
        } else {
          statusTag = `<span class="check-tag check-fail">🔴 Чат недоступен</span>`;
          geminiExtra = `
            <div class="gemini-badge-row">
              <span class="gemini-sub-badge fail">✕ Ошибка связи</span>
              <button class="btn-open-gemini-test" title="Диагностика">💬 Диагностика</button>
            </div>
          `;
        }
      } else if (res.ok) {
        statusTag = `<span class="check-tag check-ok">🟢 Доступен (${res.latency_ms} ms)</span>`;
      } else {
        statusTag = `<span class="check-tag check-fail">🔴 Недоступен</span>`;
      }
    } else if (svc.id === "gemini") {
      geminiExtra = `
        <div class="gemini-badge-row">
          <button class="btn-open-gemini-test" title="Тестирование диалога">💬 Проверить диалог с ИИ</button>
        </div>
      `;
    }

    return `
      <div class="service-card ${svc.id === 'gemini' ? 'service-card-gemini' : ''}" id="svc-card-${svc.id}">
        <div class="service-card-top">
          <div class="service-card-brand">
            <div class="service-icon ${svc.id === 'gemini' ? 'service-icon-gemini' : ''}">${icon}</div>
            <div class="service-info">
              <span class="service-title">${escapeHtml(svc.name)}</span>
              <span class="service-desc">${escapeHtml(svc.desc)}</span>
            </div>
          </div>
          <button class="btn-svc-retest" data-id="${svc.id}" title="Проверить ${escapeHtml(svc.name)}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          </button>
        </div>
        ${geminiExtra}
        <div class="service-card-status">
          <span style="font-size: 11px; color: var(--text-muted); font-family: monospace;">${escapeHtml(svc.display_url)}</span>
          <div id="svc-tag-${svc.id}">${statusTag}</div>
        </div>
      </div>
    `;
  }).join("");

  // Attach individual test buttons
  container.querySelectorAll(".btn-svc-retest").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const svcId = btn.dataset.id;
      await checkSingleService(svcId);
    });
  });

  // Attach gemini modal triggers
  container.querySelectorAll(".btn-open-gemini-test").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openGeminiModal();
    });
  });
}

async function checkSingleService(svcId) {
  state.servicesResults[svcId] = { running: true };
  renderCheckerServices();

  try {
    const res = await callApi("check_single_service", svcId);
    if (res) {
      state.servicesResults[svcId] = res;
    }
  } catch (e) {
    console.error("Single check error:", e);
    state.servicesResults[svcId] = { ok: false, error: String(e), latency_ms: 0 };
  }
  renderCheckerServices();
  updateCheckerSummary();
}

async function checkAllServices() {
  const btn = document.getElementById("btn-check-services");
  const label = document.getElementById("btn-check-services-label");
  if (btn) btn.disabled = true;
  if (label) label.textContent = "Проверка сервисов...";

  DEFAULT_SERVICES.forEach(s => {
    state.servicesResults[s.id] = { running: true };
  });
  renderCheckerServices();

  try {
    const res = await callApi("check_blocked_services");
    if (res && res.results) {
      res.results.forEach(r => {
        state.servicesResults[r.id] = r;
      });
    }
  } catch (e) {
    console.error("Check all services error:", e);
  } finally {
    if (btn) btn.disabled = false;
    if (label) label.textContent = "Проверить все сервисы";
    renderCheckerServices();
    updateCheckerSummary();
  }
}

function updateCheckerSummary() {
  const summaryBox = document.getElementById("checker-summary");
  const summaryIcon = document.getElementById("checker-summary-icon");
  const summaryText = document.getElementById("checker-summary-text");
  const summaryStats = document.getElementById("checker-summary-stats");

  if (!summaryBox) return;

  const total = DEFAULT_SERVICES.length;
  let passed = 0;
  let finished = 0;

  DEFAULT_SERVICES.forEach(s => {
    const r = state.servicesResults[s.id];
    if (r && !r.running) {
      finished++;
      if (r.ok) passed++;
    }
  });

  if (finished === 0) {
    summaryBox.style.display = "none";
    return;
  }

  summaryBox.style.display = "flex";
  summaryStats.textContent = `${passed}/${total} доступно`;

  if (passed === total) {
    summaryBox.className = "checker-summary all-ok";
    summaryIcon.textContent = "🟢";
    summaryText.textContent = "Все популярные сервисы успешно открываются через VPN!";
  } else if (passed > 0) {
    summaryBox.className = "checker-summary has-fails";
    summaryIcon.textContent = "🟡";
    summaryText.textContent = `Доступно ${passed} из ${total} сервисов. Часть ресурсов может требовать другой сервер.`;
  } else {
    summaryBox.className = "checker-summary has-fails";
    summaryIcon.textContent = "🔴";
    summaryText.textContent = "Ни один сервис не ответил. Проверьте подключение к серверу.";
  }
}

const checkAllBtn = document.getElementById("btn-check-services");
if (checkAllBtn) {
  checkAllBtn.addEventListener("click", checkAllServices);
}

// ==========================================
// Gemini Test Modal Logic
// ==========================================
function openGeminiModal() {
  const modal = document.getElementById("modal-gemini-test");
  if (!modal) return;
  modal.style.display = "flex";

  const diagBox = document.getElementById("gemini-modal-diag");
  const selectedNode = state.nodes.find(n => n.id === state.settings.selected_node_id);
  const isConnected = state.status === "connected";
  const nodeName = selectedNode ? (selectedNode.name || selectedNode.country || "VPN Сервер") : "Сервер не выбран";
  const geminiRes = state.servicesResults["gemini"];

  let diagHtml = `
    <div class="gemini-diag-item">
      <span class="diag-label">Активный сервер:</span>
      <span class="diag-val">${escapeHtml(nodeName)} (${isConnected ? '🟢 Подключен' : '⚪ Отключен'})</span>
    </div>
  `;
  if (geminiRes && !geminiRes.running) {
    diagHtml += `
      <div class="gemini-diag-item">
        <span class="diag-label">Статус диалогов:</span>
        <span class="diag-val ${geminiRes.can_chat ? 'text-good' : 'text-fail'}">
          ${geminiRes.can_chat ? '✓ Доступен для генерации' : '✕ Ограничен в регионе'}
        </span>
      </div>
      <div class="gemini-diag-item">
        <span class="diag-label">Региональный фильтр:</span>
        <span class="diag-val ${geminiRes.region_eligible ? 'text-good' : 'text-fail'}">
          ${geminiRes.region_eligible ? '✓ Разрешен Google' : '✕ Блокировка по IP'}
        </span>
      </div>
      <div class="gemini-diag-item">
        <span class="diag-label">Шлюз чата:</span>
        <span class="diag-val ${geminiRes.gw_ok ? 'text-good' : 'text-fail'}">
          ${geminiRes.gw_ok ? '✓ 204 OK' : '✕ Не отвечает'}
        </span>
      </div>
    `;
  }
  if (diagBox) diagBox.innerHTML = diagHtml;
}

function closeGeminiModal() {
  const modal = document.getElementById("modal-gemini-test");
  if (modal) modal.style.display = "none";
}

async function runGeminiTest() {
  const promptInput = document.getElementById("gemini-test-prompt");
  const keyInput = document.getElementById("gemini-test-key");
  const resultBox = document.getElementById("gemini-test-result-box");
  const resultContent = document.getElementById("gemini-result-content");
  const resultTime = document.getElementById("gemini-result-time");
  const resultTitle = document.getElementById("gemini-result-status-title");
  const runBtn = document.getElementById("btn-run-gemini-test");
  const runLabel = document.getElementById("btn-run-gemini-label");

  const prompt = promptInput ? promptInput.value.trim() : "Привет!";
  const apiKey = keyInput ? keyInput.value.trim() : "";

  if (runBtn) runBtn.disabled = true;
  if (runLabel) runLabel.textContent = "Отправка...";

  if (resultBox) {
    resultBox.style.display = "block";
    resultBox.className = "gemini-result-box loading";
    resultContent.innerHTML = `<span class="spin-dot"></span> Выполняется запрос к Gemini через текущий VPN сервер...`;
    resultTitle.textContent = "Проверка...";
    resultTime.textContent = "";
  }

  try {
    const res = await callApi("test_gemini_dialog", prompt, apiKey);
    if (res && res.success) {
      resultBox.className = "gemini-result-box success";
      resultTitle.textContent = res.type === "live_chat" ? "Ответ модели Gemini (1.5 Flash):" : "Результат диагностики:";
      resultTime.textContent = `${res.latency_ms} ms`;
      resultTime.className = "ping-tag ping-good";
      resultContent.textContent = res.reply || "Диалог подтвержден!";
    } else {
      resultBox.className = "gemini-result-box fail";
      resultTitle.textContent = "Ошибка проверки диалога:";
      resultTime.textContent = `${res ? res.latency_ms : 0} ms`;
      resultTime.className = "ping-tag ping-bad";
      resultContent.textContent = (res && res.error) ? res.error : "Сервер не ответил.";
    }
  } catch (err) {
    resultBox.className = "gemini-result-box fail";
    resultTitle.textContent = "Ошибка вызова:";
    resultContent.textContent = String(err);
  } finally {
    if (runBtn) runBtn.disabled = false;
    if (runLabel) runLabel.textContent = "Отправить / Проверить";
  }
}

const btnCloseGeminiModal = document.getElementById("btn-close-gemini-modal");
if (btnCloseGeminiModal) {
  btnCloseGeminiModal.addEventListener("click", closeGeminiModal);
}
const btnCloseGeminiFooter = document.getElementById("btn-close-gemini-footer");
if (btnCloseGeminiFooter) {
  btnCloseGeminiFooter.addEventListener("click", closeGeminiModal);
}
const modalGemini = document.getElementById("modal-gemini-test");
if (modalGemini) {
  modalGemini.addEventListener("click", (e) => {
    if (e.target === modalGemini) closeGeminiModal();
  });
}
const btnRunGemini = document.getElementById("btn-run-gemini-test");
if (btnRunGemini) {
  btnRunGemini.addEventListener("click", runGeminiTest);
}
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeGeminiModal();
});

// Status Poller with concurrency guard
let isPolling = false;
async function pollStatus() {
  if (isPolling || !isInitialized) return;
  isPolling = true;
  try {
    const st = await callApi("get_status");
    if (st) updateStatusUI(st);
  } catch (e) {
    // ignore
  } finally {
    isPolling = false;
  }
}

// Initial Data Load
let isInitialized = false;
let initRetries = 0;

async function init() {
  if (isInitialized) return;
  try {
    const data = await callApi("get_initial_data");
    if (!data || !data.settings) {
      throw new Error("Invalid initial data payload");
    }
    state.nodes = data.nodes || [];
    state.subscriptions = data.subscriptions || [];
    state.settings = data.settings || {};
    
    // Sync Settings Toggles (with null checks)
    if (typeof toggleRouting !== "undefined" && toggleRouting) {
      toggleRouting.checked = (state.settings.routing_mode === "bypass_ru_lan");
    }
    if (typeof selectRoutingMode !== "undefined" && selectRoutingMode) {
      selectRoutingMode.value = state.settings.routing_mode || "bypass_ru_lan";
    }
    if (typeof toggleTun !== "undefined" && toggleTun) {
      toggleTun.checked = (state.settings.mode === "tun");
    }
    if (typeof selectDns !== "undefined" && selectDns) {
      selectDns.value = state.settings.dns_server || "1.1.1.1";
    }

    setupFilterPills();
    renderSelectedNode();
    renderServers();
    renderSubscriptions();
    renderCheckerServices();
    if (data.status) updateStatusUI(data.status);
    
    isInitialized = true;
    console.log(`ZyVPN initialized successfully. Nodes: ${state.nodes.length}, Subscriptions: ${state.subscriptions.length}`);

    // Deferred non-blocking IP information lookup
    setTimeout(fetchAndRenderIpInfo, 1000);
  } catch (e) {
    console.error("Init failed:", e);
    isInitialized = false;
    if (initRetries < 15) {
      initRetries++;
      setTimeout(init, 400);
    }
  }
}

// Guaranteed init triggers across all webview lifecycle events
window.addEventListener("pywebviewready", init);
window.addEventListener("DOMContentLoaded", () => {
  init();
  // Start background status polling
  setInterval(pollStatus, 2000);

  // Window Controls for Frameless Window
  const btnMin = document.getElementById("win-btn-minimize");
  const btnMax = document.getElementById("win-btn-maximize");
  const btnClose = document.getElementById("win-btn-close");
  const iconMax = document.getElementById("icon-win-max");
  const iconRestore = document.getElementById("icon-win-restore");

  if (btnMin) {
    btnMin.addEventListener("click", (e) => {
      e.stopPropagation();
      callApi("window_minimize");
    });
  }

  if (btnMax) {
    btnMax.addEventListener("click", async (e) => {
      e.stopPropagation();
      const res = await callApi("window_toggle_maximize");
      if (res && res.success) {
        if (res.maximized) {
          if (iconMax) iconMax.style.display = "none";
          if (iconRestore) iconRestore.style.display = "block";
        } else {
          if (iconMax) iconMax.style.display = "block";
          if (iconRestore) iconRestore.style.display = "none";
        }
      }
    });
  }

  if (btnClose) {
    btnClose.addEventListener("click", (e) => {
      e.stopPropagation();
      callApi("window_close");
    });
  }
});

// Immediate and delayed fallback triggers so nothing can ever prevent init
setTimeout(init, 80);
setTimeout(init, 400);
setTimeout(init, 1200);

