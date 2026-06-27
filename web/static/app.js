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
    providerVal: $("#providerVal"), toolsVal:  $("#toolsVal"),
    callsVal:  $("#callsVal"),  errorsVal: $("#errorsVal"),
    aiTimeVal: $("#aiTimeVal"), uptimeVal: $("#uptimeVal"),
    commandsVal: $("#commandsVal"), versionVal: $("#versionVal"),
    starkVal:  $("#starkVal"),  safeVal:   $("#safeVal"),
  };

  // Voice elements
  const voiceToggle  = $("#voiceToggle");
  const voiceStopBtn = $("#voiceStopBtn");
  const voiceSel     = $("#voiceSelect");
  const voiceSpeed   = $("#voiceSpeed");
  const voiceSpeedVal = $("#voiceSpeedVal");

  // ── State ───────────────────────────────────────────────────────────────
  let ws = null;
  let sending = false;
  let currentAssistantBubble = null;
  let currentText = "";

  // ── Voice / TTS State ───────────────────────────────────────────────────
  const synth = window.speechSynthesis;
  let voiceEnabled = true;
  let selectedVoice = null;
  let voiceRate = 1.0;

  // ── Markdown-lite renderer ──────────────────────────────────────────────
  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function renderMarkdown(text) {
    if (!text) return "";
    const codeBlocks = [];
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      const escaped = escapeHtml(code);
      const idx = codeBlocks.length;
      codeBlocks.push(`<pre><code class="lang-${escapeHtml(lang)}">${escaped}</code></pre>`);
      return `\x00CODEBLOCK_${idx}\x00`;
    });
    text = escapeHtml(text);
    text = text.replace(/\x00CODEBLOCK_(\d+)\x00/g, (_, idx) => codeBlocks[parseInt(idx)]);
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");
    return text;
  }

  // ── Strip markdown/HTML for clean TTS ───────────────────────────────────
  function stripForSpeech(text) {
    if (!text) return "";
    let t = text;
    // Remove code blocks
    t = t.replace(/```[\s\S]*?```/g, "");
    // Remove inline code
    t = t.replace(/`[^`]+`/g, "");
    // Remove markdown formatting
    t = t.replace(/\*\*(.+?)\*\*/g, "$1");
    t = t.replace(/\*(.+?)\*/g, "$1");
    t = t.replace(/#{1,6}\s*/g, "");
    t = t.replace(/[>\-|]/g, "");      // Remove URLs but keep link text
    t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    // Split on newlines before collapsing whitespace
    t = t.replace(/\n/g, " ");
    // Collapse whitespace
    t = t.replace(/\s+/g, " ").trim();
    // Limit length for TTS
    if (t.length > 2000) t = t.substring(0, 2000) + "... truncated for speech";
    return t;
  }

  // ── Voice / TTS Functions ───────────────────────────────────────────────
  function speak(text) {
    if (!voiceEnabled || !synth || !text) return;
    synth.cancel();
    clearSpeakingIndicator();
    const clean = stripForSpeech(text);
    if (!clean) return;
    // Chrome bug: speech stops after ~15s. Split long text into chunks.
    const MAX_CHUNK = 200;
    const chunks = [];
    if (clean.length <= MAX_CHUNK) {
      chunks.push(clean);
    } else {
      const sentences = clean.replace(/([.!?])\s+/g, "$1|").replace(/\n/g, "|").split("|");
      let buf = "";
      for (const s of sentences) {
        if (buf.length + s.length > MAX_CHUNK && buf) {
          chunks.push(buf);
          buf = "";
        }
        buf += s;
      }
      if (buf) chunks.push(buf);
    }
    // Mark last bubble as speaking
    const lastBubble = messagesEl.querySelector(".message.assistant:last-child .bubble");
    let speakingEl = null;
    let chunkIdx = 0;
    function speakChunk() {
      if (chunkIdx >= chunks.length) {
        clearSpeakingIndicator();
        return;
      }
      const utter = new SpeechSynthesisUtterance(chunks[chunkIdx]);
      if (selectedVoice) utter.voice = selectedVoice;
      utter.rate = voiceRate;
      utter.pitch = 1.0;
      utter.volume = 1.0;
      utter.onstart = () => {
        if (!speakingEl && lastBubble) {
          speakingEl = lastBubble;
          speakingEl.classList.add("speaking");
        }
      };
      utter.onend = () => {
        chunkIdx++;
        speakChunk();
      };
      utter.onerror = () => {
        clearSpeakingIndicator();
      };
      synth.speak(utter);
    }
    speakChunk();
  }

  function clearSpeakingIndicator() {
    const el = messagesEl.querySelector(".bubble.speaking");
    if (el) el.classList.remove("speaking");
  }

  function stopSpeaking() {
    if (synth) synth.cancel();
    clearSpeakingIndicator();
  }

  function loadVoices() {
    if (!voiceSel) return;
    voiceSel.innerHTML = "";
    const voices = synth.getVoices();
    // Prefer English voices, then all
    const english = voices.filter(v => v.lang.startsWith("en"));
    const others = voices.filter(v => !v.lang.startsWith("en"));
    const sorted = [...english, ...others];

    sorted.forEach((v, i) => {
      const opt = document.createElement("option");
      opt.value = i;
      opt.textContent = `${v.name} (${v.lang})`;
      opt.dataset.voiceIndex = voices.indexOf(v);
      voiceSel.appendChild(opt);
    });

    // Default: pick a good English voice
    const defaultIdx = [
      sorted.findIndex(v => v.name.includes("Google") && v.lang.startsWith("en")),
      sorted.findIndex(v => v.name.includes("Zira")),
      sorted.findIndex(v => v.name.includes("Microsoft") && v.lang.startsWith("en")),
      0
    ].find(i => i >= 0) ?? 0;
    if (defaultIdx >= 0 && sorted[defaultIdx]) {
      voiceSel.selectedIndex = defaultIdx;
      selectedVoice = sorted[defaultIdx];
    }
  }

  if (synth) {
    loadVoices();
    // Chrome loads voices async
    if (synth.onvoiceschanged !== undefined) {
      synth.onvoiceschanged = loadVoices;
    }
  }

  // Voice toggle
  if (voiceToggle) {
    voiceToggle.addEventListener("click", () => {
      voiceEnabled = !voiceEnabled;
      voiceToggle.classList.toggle("active", voiceEnabled);
      voiceToggle.innerHTML = voiceEnabled
        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>';
      if (!voiceEnabled) stopSpeaking();
    });
    // Set initial state
    voiceToggle.classList.add("active");
  }

  // Stop button
  if (voiceStopBtn) {
    voiceStopBtn.addEventListener("click", stopSpeaking);
  }

  // Voice selector
  if (voiceSel) {
    voiceSel.addEventListener("change", () => {
      const voices = synth.getVoices();
      const idx = parseInt(voiceSel.selectedOptions[0]?.dataset.voiceIndex);
      if (!isNaN(idx) && voices[idx]) {
        selectedVoice = voices[idx];
      }
    });
  }

  // Speed slider
  if (voiceSpeed) {
    voiceSpeed.addEventListener("input", () => {
      voiceRate = parseFloat(voiceSpeed.value);
      if (voiceSpeedVal) voiceSpeedVal.textContent = voiceRate.toFixed(1) + "x";
    });
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
      try {
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
          return;
        }

        if (data.type === "done") {
          const finalText = data.content || currentText;
          if (currentAssistantBubble) {
            currentAssistantBubble.innerHTML = renderMarkdown(finalText);
          } else {
            removeTypingIndicator();
            addMessage("assistant", finalText || "(no response)");
          }
          if (!finalText.startsWith("Error:")) {
            speak(finalText);
          }
          currentAssistantBubble = null;
          currentText = "";
          resetSend();
          return;
        }

        if (data.type === "error") {
          removeTypingIndicator();
          addMessage("assistant", `Error: ${data.content}`);
          currentAssistantBubble = null;
          currentText = "";
          resetSend();
          return;
        }
      } catch (e) {
        removeTypingIndicator();
        currentAssistantBubble = null;
        currentText = "";
        resetSend();
      }
    };
  }

  // ── Send message ────────────────────────────────────────────────────────
  function resetSend() {
    sending = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }

  const STOP_WORDS = ["stop", "stop speaking", "shut up", "shutup", "be quiet", "silence", "shush"];

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || sending) return;

    const lower = text.toLowerCase();
    const isStop = STOP_WORDS.some(w => lower === w || lower.startsWith(w + " "));
    stopSpeaking();
    if (isStop) {
      addMessage("user", text);
      inputEl.value = "";
      inputEl.style.height = "auto";
      return;
    }

    sending = true;
    sendBtn.disabled = true;
    addMessage("user", text);
    inputEl.value = "";
    inputEl.style.height = "auto";
    addTypingIndicator();

    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ message: text }));
      } catch (e) {
        // WebSocket send failed — fall back to REST
        doRestChat(text);
      }
    } else {
      await doRestChat(text);
    }
  }

  async function doRestChat(text) {
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
        if (!data.response.startsWith("Error:")) speak(data.response);
      } else {
        addMessage("assistant", `Error: ${data.error}`);
      }
    } catch (e) {
      removeTypingIndicator();
      addMessage("assistant", `Network error: ${e.message}`);
    } finally {
      resetSend();
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

      const cpuPct = Math.round(s.cpu_percent);
      els.cpuVal.textContent = cpuPct + "%";
      els.cpuBar.style.width = cpuPct + "%";
      els.cpuBar.className = `progress-fill ${colorForPercent(cpuPct)}`;

      const ramPct = Math.round(s.ram_percent);
      els.ramVal.textContent = `${s.ram_used_gb}/${s.ram_total_gb} GB`;
      els.ramBar.style.width = ramPct + "%";
      els.ramBar.className = `progress-fill ${colorForPercent(ramPct)}`;

      const diskPct = Math.round(s.disk_percent);
      els.diskVal.textContent = `${s.disk_used_gb}/${s.disk_total_gb} GB`;
      els.diskBar.style.width = diskPct + "%";
      els.diskBar.className = `progress-fill ${colorForPercent(diskPct)}`;

      els.providerVal.textContent = s.provider;
      els.toolsVal.textContent = s.tools_registered;
      els.callsVal.textContent = s.total_calls;
      els.errorsVal.textContent = s.total_errors;
      els.aiTimeVal.textContent = s.total_time + "s";

      const upMin = s.uptime_minutes;
      const h = Math.floor(upMin / 60);
      const m = upMin % 60;
      els.uptimeVal.textContent = h > 0 ? `${h}h ${m}m` : `${m}m`;
      els.commandsVal.textContent = s.commands_run;
      els.versionVal.textContent = "v" + s.version;

      els.starkVal.textContent = s.stark_mode ? "ENGAGED" : "STANDBY";
      els.starkVal.className = `stat-value ${s.stark_mode ? "yellow" : ""}`;
      els.safeVal.textContent = s.safe_mode ? "ON" : "OFF";
      els.safeVal.className = `stat-value ${s.safe_mode ? "green" : "red"}`;

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

  document.querySelectorAll("#modelSwitcher .toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchModel(btn, btn.dataset.model));
  });

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

  // Stop speech when navigating away
  window.addEventListener("beforeunload", () => {
    if (synth) synth.cancel();
  });

  // Save/restore voice settings from localStorage
  try {
    const saved = JSON.parse(localStorage.getItem("friday_voice") || "{}");
    if (saved.enabled !== undefined) {
      voiceEnabled = saved.enabled;
      if (voiceToggle) voiceToggle.classList.toggle("active", voiceEnabled);
    }
    if (saved.rate) {
      voiceRate = saved.rate;
      if (voiceSpeed) voiceSpeed.value = voiceRate;
      if (voiceSpeedVal) voiceSpeedVal.textContent = voiceRate.toFixed(1) + "x";
    }
  } catch (e) { /* ignore */ }
  // Persist on change
  const saveVoiceSettings = () => {
    try { localStorage.setItem("friday_voice", JSON.stringify({ enabled: voiceEnabled, rate: voiceRate })); } catch (e) {}
  };
  if (voiceToggle) voiceToggle.addEventListener("click", saveVoiceSettings);
  if (voiceSpeed) voiceSpeed.addEventListener("input", saveVoiceSettings);

  // Hide voice section if speechSynthesis unavailable
  if (!synth) {
    const voiceSection = $("#voiceSection");
    if (voiceSection) voiceSection.style.display = "none";
  }
})();
