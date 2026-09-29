/**
 * I.R.O.N. M.A.N. Dashboard Controller
 */

(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // DOM Elements
  const messagesEl = $('#messages');
  const centerHero = $('#centerHero');
  const inputEl = $('#userInput');
  const sendBtn = $('#sendBtn');
  const modelBadge = $('#modelBadge');
  const statusDot = $('#statusDot');

  const els = {
    cpuVal: $('#cpuVal'),
    cpuBar: $('#cpuBar'),
    ramVal: $('#ramVal'),
    ramBar: $('#ramBar'),
    diskVal: $('#diskVal'),
    diskBar: $('#diskBar'),
    providerVal: $('#providerVal'),
    toolsVal: $('#toolsVal'),
    callsVal: $('#callsVal'),
    errorsVal: $('#errorsVal'),
    aiTimeVal: $('#aiTimeVal'),
    uptimeVal: $('#uptimeVal'),
    commandsVal: $('#commandsVal'),
    starkVal: $('#starkVal'),
    safeVal: $('#safeVal'),
  };

  // State
  let ws = null;
  let sending = false;
  let voiceEnabled = true;
  const synth = window.speechSynthesis;

  // ── Stark & Safe Mode Toggles ────────────────────────────────────────────
  if (els.starkVal) {
    els.starkVal.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: 'stark' }),
        });
        const data = await res.json();
        if (data.ok) fetchStats();
      } catch (e) {
        console.error(e);
      }
    });
  }

  if (els.safeVal) {
    els.safeVal.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: 'safe' }),
        });
        const data = await res.json();
        if (data.ok) fetchStats();
      } catch (e) {
        console.error(e);
      }
    });
  }

  // ── Markdown Parser ──────────────────────────────────────────────────────
  function renderMarkdown(md) {
    let out = md
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    out = out.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang, code) => {
      return `<pre style="background:rgba(0,0,0,0.6);padding:8px;border-radius:6px;margin:6px 0;font-family:var(--font-mono);font-size:11px;overflow-x:auto;"><code>${code.trim()}</code></pre>`;
    });

    out = out.replace(/`([^`]+)`/g, '<code style="color:var(--accent-cyan);font-family:var(--font-mono);">$1</code>');
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    out = out.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
    return out;
  }

  function addMessage(role, text) {
    if (messagesEl) messagesEl.style.display = 'flex';

    const msg = document.createElement('div');
    msg.className = `message ${role}`;

    const label = document.createElement('span');
    label.className = 'message-label';
    label.textContent = role === 'user' ? 'Operator' : 'IRON MAN';
    msg.appendChild(label);

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = renderMarkdown(text);
    msg.appendChild(bubble);

    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }

  function speak(text) {
    if (!voiceEnabled || !synth) return;
    synth.cancel();

    const clean = text
      .replace(/```[\s\S]*?```/g, 'Code block omitted.')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/[*#_~>]/g, '')
      .trim();

    if (!clean) return;

    const utter = new SpeechSynthesisUtterance(clean);
    utter.rate = 1.05;
    synth.speak(utter);
  }

  // ── WebSocket & Chat ─────────────────────────────────────────────────────
  function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${location.host}/ws/chat`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (statusDot) {
          statusDot.style.background = 'var(--green)';
          statusDot.style.boxShadow = '0 0 8px var(--green)';
        }
      };

      ws.onclose = () => {
        if (statusDot) {
          statusDot.style.background = 'var(--yellow)';
          statusDot.style.boxShadow = '0 0 8px var(--yellow)';
        }
        setTimeout(connectWS, 3000);
      };

      let streamingBubble = null;
      let streamedContent = '';

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);

          if (data.type === 'token') {
            if (!streamingBubble) {
              streamingBubble = addMessage('assistant', '');
            }
            streamedContent += data.content;
            streamingBubble.innerHTML = renderMarkdown(streamedContent);
            messagesEl.scrollTop = messagesEl.scrollHeight;
          } else if (data.type === 'done') {
            if (streamingBubble) {
              streamingBubble.innerHTML = renderMarkdown(streamedContent || data.content);
            } else {
              addMessage('assistant', data.content);
            }
            speak(streamedContent || data.content);
            streamingBubble = null;
            streamedContent = '';
            resetSend();
          } else if (data.type === 'error') {
            addMessage('assistant', `Diagnostic Notice: ${data.content}`);
            streamingBubble = null;
            streamedContent = '';
            resetSend();
          }
        } catch {
          // ignore
        }
      };
    } catch {
      // ws fallback
    }
  }

  async function sendMessage() {
    const text = (inputEl.value || '').trim();
    if (!text || sending) return;

    sending = true;
    sendBtn.disabled = true;
    addMessage('user', text);
    inputEl.value = '';
    inputEl.style.height = 'auto';

    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ message: text }));
        return;
      } catch {
        // Fallback to REST
      }
    }

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      if (data.ok) {
        addMessage('assistant', data.response);
        speak(data.response);
      } else {
        addMessage('assistant', `Notice: ${data.error}`);
      }
    } catch (e) {
      addMessage('assistant', `Transmission interrupted: ${e.message}`);
    } finally {
      resetSend();
    }
  }

  function resetSend() {
    sending = false;
    sendBtn.disabled = false;
    inputEl.focus();
    fetchStats();
  }

  // ── Telemetry & Stats ────────────────────────────────────────────────────
  function colorForPct(pct) {
    if (pct < 65) return 'green';
    if (pct < 85) return 'yellow';
    return 'red';
  }

  async function fetchStats() {
    try {
      const res = await fetch('/api/status');
      const s = await res.json();
      if (!s.ok) return;

      if (els.cpuVal && els.cpuBar) {
        const c = Math.round(s.cpu_percent);
        els.cpuVal.textContent = c + '%';
        els.cpuBar.style.width = c + '%';
        els.cpuBar.className = `progress-fill blue`;
      }

      if (els.ramVal && els.ramBar) {
        const r = Math.round(s.ram_percent);
        els.ramVal.textContent = `${s.ram_used_gb}/${s.ram_total_gb} GB`;
        els.ramBar.style.width = r + '%';
        els.ramBar.className = `progress-fill ${colorForPct(r)}`;
      }

      if (els.diskVal && els.diskBar) {
        const d = Math.round(s.disk_percent);
        els.diskVal.textContent = `${s.disk_used_gb}/${s.disk_total_gb} GB`;
        els.diskBar.style.width = d + '%';
        els.diskBar.className = `progress-fill ${colorForPct(d)}`;
      }

      if (els.providerVal) els.providerVal.textContent = s.provider;
      if (els.toolsVal) els.toolsVal.textContent = s.tools_registered;
      if (els.callsVal) els.callsVal.textContent = s.total_calls;
      if (els.errorsVal) els.errorsVal.textContent = s.total_errors;

      if (els.uptimeVal) {
        const min = s.uptime_minutes;
        const h = Math.floor(min / 60);
        const m = min % 60;
        els.uptimeVal.textContent = h > 0 ? `${h}h ${m}m` : `${m}m`;
      }

      if (els.starkVal) {
        els.starkVal.textContent = s.stark_mode ? 'ENGAGED' : 'STANDBY';
        els.starkVal.className = `stat-value clickable ${s.stark_mode ? 'yellow' : ''}`;
      }

      if (els.safeVal) {
        els.safeVal.textContent = s.safe_mode ? 'ON' : 'OFF';
        els.safeVal.className = `stat-value clickable ${s.safe_mode ? 'green' : 'red'}`;
      }

      if (modelBadge) modelBadge.textContent = s.model;
    } catch {
      // ignore
    }
  }

  // ── Model Switcher ───────────────────────────────────────────────────────
  $$('#modelSwitcher .model-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      $$('#modelSwitcher .model-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const model = btn.dataset.model;
      fetch('/api/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      })
        .then(() => {
          if (modelBadge) modelBadge.textContent = model;
        })
        .catch(() => {});
    });
  });

  // ── Quick Actions ────────────────────────────────────────────────────────
  $$('.tool-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const prompt = btn.dataset.prompt || '';
      const text = btn.dataset.text || '';
      if (prompt) {
        inputEl.value = prompt;
        inputEl.focus();
      } else if (text) {
        inputEl.value = text;
        sendMessage();
      }
    });
  });

  // ── Keyboard & Input ─────────────────────────────────────────────────────
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
  });

  sendBtn.addEventListener('click', sendMessage);

  // ── Initialize ───────────────────────────────────────────────────────────
  connectWS();
  fetchStats();
  setInterval(fetchStats, 6000);
})();
