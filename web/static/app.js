/* ── FRIDAY Dashboard – Frontend App ─────────────────────────────────────── */
(() => {
  "use strict";

  // ── Elements ────────────────────────────────────────────────────────────
  const $ = (s) => document.querySelector(s);
  const messagesEl  = $("#messages");
  const welcomeEl   = $("#welcome");
  const inputEl     = $("#userInput");
  const sendBtn     = $("#sendBtn");
  const modelBadge  = $("#modelBadge");
  const statusDot   = $("#statusDot");

  // Sidebar stat elements
  const els = {
    cpuVal:    $("#cpuVal"),    cpuBar:    $("#cpuBar"),
    ramVal:    $("#ramVal"),    ramBar:    $("#ramBar"),
    diskVal:   $("#diskVal"),   diskBar:   $("#diskBar"),
    providerVal: $("#providerVal"),
    toolsVal:  $("#toolsVal"),
    callsVal:  $("#callsVal"),
    errorsVal: $("#errorsVal"),
    aiTimeVal: $("#aiTimeVal"),
    uptimeVal: $("#uptimeVal"),
    commandsVal: $("#commandsVal"),
    versionVal: $("#versionVal"),
    starkVal:  $("#starkVal"),
    safeVal:   $("#safeVal"),
  };

  // ── State ───────────────────────────────────────────────────────────────
  let ws = null;
  let sending = false;
  let currentAssistantBubble = null;
  let currentText = "";

  // ── Markdown-lite renderer ──────────────────────────────────────────────
  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function renderMarkdown(text) {
    if (!text) return "";
    // Code blocks — extract first to protect content
    const codeBlocks = [];
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      const escaped = escapeHtml(code);
      const idx = codeBlocks.length;
      codeBlocks.push(`<pre><code class="lang-${escapeHtml(lang)}">${escaped}</code></pre>`);
      return `\x00CODEBLOCK_${idx}\x00`;
    });
    // Escape remaining HTML in the text portion
    text = escapeHtml(text);
    // Restore code blocks
    text = text.replace(/\x00CODEBLOCK_(\d+)\x00/g, (_, idx) => codeBlocks[parseInt(idx)]);
    // Inline code
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Bold
    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Italic
    text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");
    return text;
  }

  // ── Messages ────────────────────────────────────────────────────────────
  function addMessage(role, content) {
    if (welcomeEl) welcomeEl.remove();

    const div = document.createElement("div");
    div.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "U" : "F";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = renderMarkdown(content);

    div.appendChild(avatar);
    div.appendChild(bubble);
    messagesEl.appendChild(div);
    scrollToBottom();
    return bubble;
  }

  function addTypingIndicator() {
    if (welcomeEl) welcomeEl.remove();

    const div = document.createElement("div");
    div.className = "message assistant";
    div.id = "typingMsg";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "F";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;

    div.appendChild(avatar);
    div.appendChild(bubble);
    messagesEl.appendChild(div);
    scrollToBottom();
    return bubble;
  }

  function removeTypingIndicator() {
    const el = document.getElementById("typingMsg");
    if (el) el.remove();
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── WebSocket ───────────────────────────────────────────────────────────
  function connectWS() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/chat`);

    ws.onopen = () => {
      statusDot.style.background = "var(--green)";
      statusDot.style.boxShadow = "0 0 6px var(--green)";
      statusDot.title = "Connected";
    };

    ws.onclose = () => {
      statusDot.style.background = "var(--red)";
      statusDot.style.boxShadow = "0 0 6px var(--red)";
      statusDot.title = "Disconnected – retrying...";
      setTimeout(connectWS, 3000);
    };

    ws.onerror = () => {
      statusDot.style.background = "var(--red)";
    };

    ws.onmessage = (evt) => {
      const data = JSON.parse(evt.data);

      if (data.type === "token") {
        if (!currentAssistantBubble) {
          removeTypingIndicator();
          currentAssistantBubble = addMessage("assistant", "");
          currentText = "";
        }
        currentText += data.content;
        currentAssistantBubble.innerHTML = renderMarkdown(currentText);
        scrollToBottom();
      }

      if (data.type === "done") {
        if (currentAssistantBubble) {
          currentAssistantBubble.innerHTML = renderMarkdown(data.content || currentText);
        } else {
          removeTypingIndicator();
          addMessage("assistant", data.content || "(no response)");
        }
        currentAssistantBubble = null;
        currentText = "";
        sending = false;
        sendBtn.disabled = false;
        inputEl.focus();
      }

      if (data.type === "error") {
        removeTypingIndicator();
        addMessage("assistant", `Error: ${data.content}`);
        currentAssistantBubble = null;
        currentText = "";
        sending = false;
        sendBtn.disabled = false;
      }
    };
  }

  // ── Send message ────────────────────────────────────────────────────────
  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || sending) return;

    sending = true;
    sendBtn.disabled = true;
    addMessage("user", text);
    inputEl.value = "";
    inputEl.style.height = "auto";

    if (ws && ws.readyState === WebSocket.OPEN) {
      addTypingIndicator();
      ws.send(JSON.stringify({ message: text }));
    } else {
      // Fallback to REST
      addTypingIndicator();
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        });
        const data = await res.json();
        removeTypingIndicator();
        if (data.ok) {
          addMessage("assistant", data.response);
        } else {
          addMessage("assistant", `Error: ${data.error}`);
        }
      } catch (e) {
        removeTypingIndicator();
        addMessage("assistant", `Network error: ${e.message}`);
      }
      sending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  // ── Stats polling ───────────────────────────────────────────────────────
  function colorForPercent(pct) {
    if (pct < 60) return "green";
    if (pct < 85) return "yellow";
    return "red";
  }

  async function fetchStats() {
    try {
      const res = await fetch("/api/status");
      const s = await res.json();
      if (!s.ok) return;

      // CPU
      const cpuPct = Math.round(s.cpu_percent);
      els.cpuVal.textContent = cpuPct + "%";
      els.cpuBar.style.width = cpuPct + "%";
      els.cpuBar.className = `progress-fill ${colorForPercent(cpuPct)}`;

      // RAM
      const ramPct = Math.round(s.ram_percent);
      els.ramVal.textContent = `${s.ram_used_gb}/${s.ram_total_gb} GB`;
      els.ramBar.style.width = ramPct + "%";
      els.ramBar.className = `progress-fill ${colorForPercent(ramPct)}`;

      // Disk
      const diskPct = Math.round(s.disk_percent);
      els.diskVal.textContent = `${s.disk_used_gb}/${s.disk_total_gb} GB`;
      els.diskBar.style.width = diskPct + "%";
      els.diskBar.className = `progress-fill ${colorForPercent(diskPct)}`;

      // AI
      els.providerVal.textContent = s.provider;
      els.toolsVal.textContent = s.tools_registered;
      els.callsVal.textContent = s.total_calls;
      els.errorsVal.textContent = s.total_errors;
      els.aiTimeVal.textContent = s.total_time + "s";

      // Session
      const upMin = s.uptime_minutes;
      const h = Math.floor(upMin / 60);
      const m = upMin % 60;
      els.uptimeVal.textContent = h > 0 ? `${h}h ${m}m` : `${m}m`;
      els.commandsVal.textContent = s.commands_run;
      els.versionVal.textContent = "v" + s.version;

      // Modes
      els.starkVal.textContent = s.stark_mode ? "ENGAGED" : "STANDBY";
      els.starkVal.className = `stat-value ${s.stark_mode ? "yellow" : ""}`;
      els.safeVal.textContent = s.safe_mode ? "ON" : "OFF";
      els.safeVal.className = `stat-value ${s.safe_mode ? "green" : "red"}`;

      // Model badge
      modelBadge.textContent = s.model;
    } catch (e) {
      // Silent fail for stats
    }
  }

  // ── Model switcher ──────────────────────────────────────────────────────
  function switchModel(btn, model) {
    document.querySelectorAll("#modelSwitcher .toggle-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    fetch("/api/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    }).then(() => { modelBadge.textContent = model; }).catch(() => {});
  }

  // Fallback buttons (hardcoded names shown while API loads)
  document.querySelectorAll("#modelSwitcher .toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchModel(btn, btn.dataset.model));
  });

  // Fetch available models from API and rebuild the switcher
  (async function loadModels() {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      if (data.ok && data.models && data.models.length) {
        const switcher = $("#modelSwitcher");
        switcher.innerHTML = "";
        data.models.slice(0, 8).forEach((model) => {
          const btn = document.createElement("button");
          btn.className = "toggle-btn" + (model === data.current ? " active" : "");
          btn.dataset.model = model;
          btn.textContent = model.length > 22 ? model.slice(0, 20) + "\u2026" : model;
          btn.addEventListener("click", () => switchModel(btn, model));
          switcher.appendChild(btn);
        });
      }
    } catch (e) { /* silent */ }
  })();

  // ── Input handling ──────────────────────────────────────────────────────
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  inputEl.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
  });

  sendBtn.addEventListener("click", sendMessage);

  // ── Init ────────────────────────────────────────────────────────────────
  connectWS();
  fetchStats();
  setInterval(fetchStats, 5000);
  inputEl.focus();
})();
