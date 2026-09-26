// ZyVPN Frontend Application Logic

let state = {
  nodes: [],
  subscriptions: [],
  settings: {},
  status: { status: "disconnected", logs: [], uptime_seconds: 0 }
};

// Universal API invoker (supports PyWebView native api or fallback to HTTP REST)
async function callApi(method, ...args) {
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api[method] === "function") {
    return await window.pywebview.api[method](...args);
  }
  // HTTP REST fallback
  try {
    const res = await fetch(`/api/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ args })
    });
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

// Render Selected Node in Dashboard
function renderSelectedNode() {
  const selectedId = state.settings.selected_node_id;
  const node = state.nodes.find(n => n.id === selectedId) || state.nodes[0];

  const nameEl = document.getElementById("selected-node-name");
  const protoEl = document.getElementById("selected-node-badge");
  const transEl = document.getElementById("selected-node-transport");
  const pingEl = document.getElementById("selected-node-ping");

  if (!node) {
    nameEl.textContent = "Нет добавленных серверов";
    protoEl.style.display = "none";
    transEl.style.display = "none";
    pingEl.textContent = "";
    return;
  }

  protoEl.style.display = "inline-block";
  transEl.style.display = "inline-block";

  nameEl.textContent = node.name;
  protoEl.textContent = (node.protocol || "vless").toUpperCase();
  protoEl.className = `badge badge-${node.protocol}`;

  let transText = (node.transport || "tcp").toUpperCase();
  if (node.security === "reality") transText += " (Reality)";
  if (node.transport === "xhttp") {
    transText = "⚡ XHTTP (TCP)";
    transEl.className = "badge badge-xhttp";
  } else {
    transEl.className = "badge";
    transEl.style.background = "#334155";
  }
  transEl.textContent = transText;

  if (node.ping_ms !== null && node.ping_ms !== undefined) {
    pingEl.textContent = `${node.ping_ms} ms`;
    pingEl.className = `ping-tag ${node.ping_ms < 100 ? 'ping-good' : node.ping_ms < 250 ? 'ping-med' : 'ping-bad'}`;
  } else {
    pingEl.textContent = "тест пинга...";
    pingEl.className = "ping-tag";
  }
}

// Render Server List
function renderServers() {
  const container = document.getElementById("servers-container");
  const query = document.getElementById("search-servers").value.toLowerCase();
  container.innerHTML = "";

  document.getElementById("nodes-count-tab").textContent = state.nodes.length;

  const filtered = state.nodes.filter(n => 
    n.name.toLowerCase().includes(query) ||
    n.protocol.toLowerCase().includes(query) ||
    n.transport.toLowerCase().includes(query) ||
    n.server.toLowerCase().includes(query)
  );

  if (filtered.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 40px 0;">Серверы не найдены. Добавьте подписку во вкладке "Подписки".</div>`;
    return;
  }

  filtered.forEach(node => {
    const isSelected = (node.id === state.settings.selected_node_id);
    const card = document.createElement("div");
    card.className = `server-card ${isSelected ? 'selected' : ''}`;
    
    let isXhttp = (node.transport === "xhttp" || node.transport === "splithttp");
    let pingText = (node.ping_ms !== null && node.ping_ms !== undefined) ? `${node.ping_ms} ms` : "- ms";
    let pingClass = (node.ping_ms && node.ping_ms < 100) ? "ping-good" : (node.ping_ms && node.ping_ms < 250) ? "ping-med" : "ping-bad";

    card.innerHTML = `
      <div style="display: flex; align-items: center; gap: 12px;">
        <div style="font-size: 18px;">${isSelected ? '●' : '○'}</div>
        <div>
          <div style="font-weight: 600; font-size: 14px; margin-bottom: 2px;">${escapeHtml(node.name)}</div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <span class="badge badge-${node.protocol}">${node.protocol.toUpperCase()}</span>
            ${isXhttp ? '<span class="badge badge-xhttp">⚡ XHTTP</span>' : `<span class="badge" style="background:#334155;">${node.transport.toUpperCase()}</span>`}
            ${node.security === 'reality' ? '<span class="badge" style="background:#475569;">Reality</span>' : ''}
            <span style="font-size: 11px; color: var(--text-muted);">${node.server}:${node.port}</span>
          </div>
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 10px;">
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
      const res = await callApi("ping_single", node.id);
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
      const res = await callApi("add_subscription", val);
      if (res.success) {
        state.subscriptions.push(res.subscription);
        state.nodes = res.nodes;
        input.value = "";
        renderSubscriptions();
        renderServers();
        renderSelectedNode();
        alert(`Подписка успешно добавлена! Загружено серверов: ${res.nodes_count}`);
      } else {
        alert(`Не удалось загрузить подписку: ${res.error}`);
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

async function toggleConnection() {
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
}

connectBtn.addEventListener("click", toggleConnection);

// Update Status in UI
function updateStatusUI(st) {
  state.status = st;
  const s = st.status;

  if (s === "connected") {
    connectBtn.className = "connect-btn connected";
    connectLabel.textContent = "ОТКЛЮЧИТЬ";
    headerStatus.className = "header-status status-connected";
    statusText.textContent = "Подключено";
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

// Status Poller
async function pollStatus() {
  try {
    const st = await callApi("get_status");
    if (st) updateStatusUI(st);
  } catch (e) {
    // ignore
  }
}

// Initial Data Load
async function init() {
  try {
    const data = await callApi("get_initial_data");
    state.nodes = data.nodes || [];
    state.subscriptions = data.subscriptions || [];
    state.settings = data.settings || {};
    
    // Sync Settings Toggles
    toggleRouting.checked = (state.settings.routing_mode === "bypass_ru_lan");
    selectRoutingMode.value = state.settings.routing_mode || "bypass_ru_lan";
    toggleTun.checked = (state.settings.mode === "tun");
    selectDns.value = state.settings.dns_server || "1.1.1.1";

    renderSelectedNode();
    renderServers();
    renderSubscriptions();
    if (data.status) updateStatusUI(data.status);
  } catch (e) {
    console.error("Init failed:", e);
  }
}

window.addEventListener("pywebviewready", init);
window.addEventListener("DOMContentLoaded", () => {
  init();
  setInterval(pollStatus, 1500);
});
