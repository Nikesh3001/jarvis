/**
 * FRIDAY 3D Spatial Holographic Controller & Neural Interface
 */

(function () {
  'use strict';

  // Helper
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // DOM Elements
  const messagesEl = $('#messages');
  const inputEl = $('#userInput');
  const sendBtn = $('#sendBtn');
  const welcomeEl = $('#welcome');
  const modelBadge = $('#modelBadge');
  const statusDot = $('#statusDot');
  const audioWaveCanvas = $('#audioWaveCanvas');
  const waveCtx = audioWaveCanvas ? audioWaveCanvas.getContext('2d') : null;

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
    uptimeVal: $('#uptimeVal'),
    starkVal: $('#starkVal'),
    safeVal: $('#safeVal'),
  };

  // State
  let ws = null;
  let wsConnected = false;
  let sending = false;
  let voiceEnabled = true;
  let selectedVoice = null;
  let voiceRate = 1.0;
  let isSpeaking = false;
  const synth = window.speechSynthesis;

  // ── 3D Spatial Hologram Controls ─────────────────────────────────────────

  // Mode Switcher (Arc Core / Global Mesh / Mark L Armor)
  $$('.mode-3d-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      $$('.mode-3d-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.dataset.mode;
      if (window.friday3D) {
        window.friday3D.setMode(mode);
      }
    });
  });

  // Camera Presets
  $$('.cam-preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const preset = btn.dataset.preset;
      if (preset !== 'orbit') {
        $$('.cam-preset-btn').forEach((b) => {
          if (b.dataset.preset !== 'orbit') b.classList.remove('active');
        });
        btn.classList.add('active');
      }

      if (window.friday3D) {
        if (preset === 'orbit') {
          const auto = window.friday3D.toggleAutoRotate();
          btn.classList.toggle('active', auto);
          btn.textContent = auto ? 'Orbit: ON' : 'Orbit: OFF';
        } else {
          window.friday3D.setCameraPreset(preset);
        }
      }
    });
  });

  // Explode Slider for Mark L Armor
  const explodeSlider = $('#explodeSlider');
  const explodeVal = $('#explodeVal');
  if (explodeSlider) {
    explodeSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      if (explodeVal) explodeVal.textContent = Math.round(val * 100) + '%';
      if (window.friday3D) {
        window.friday3D.setExplodeAmount(val);
      }
    });
  }

  // Collapsible HUD Panels
  const toggleLeftBtn = $('#toggleLeftHud');
  const leftHud = $('#leftHud');
  if (toggleLeftBtn && leftHud) {
    toggleLeftBtn.addEventListener('click', () => {
      leftHud.classList.toggle('collapsed');
      toggleLeftBtn.textContent = leftHud.classList.contains('collapsed') ? '▶' : '◀';
    });
  }

  const toggleRightBtn = $('#toggleRightHud');
  const rightHud = $('#rightHud');
  if (toggleRightBtn && rightHud) {
    toggleRightBtn.addEventListener('click', () => {
      rightHud.classList.toggle('collapsed');
      toggleRightBtn.textContent = rightHud.classList.contains('collapsed') ? '◀' : '▶';
    });
  }

  // Close Hotspot Inspection Card
  const closeInspectBtn = $('#closeInspectCard');
  const inspectCard = $('#hotspot-inspect-card');
  if (closeInspectBtn && inspectCard) {
    closeInspectBtn.addEventListener('click', () => {
      inspectCard.classList.remove('visible');
    });
  }

  // Stark Mode Toggle
  if (els.starkVal) {
    els.starkVal.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: 'stark' }),
        });
        const data = await res.json();
        if (data.ok) {
          fetchStats();
        }
      } catch (e) {
        console.error(e);
      }
    });
  }

  // Safe Mode Toggle
  if (els.safeVal) {
    els.safeVal.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: 'safe' }),
        });
        const data = await res.json();
        if (data.ok) {
          fetchStats();
        }
      } catch (e) {
        console.error(e);
      }
    });
  }

  // ── Audio Reactive Waveform ──────────────────────────────────────────────
  let wavePhase = 0;
  function drawAudioWave() {
    requestAnimationFrame(drawAudioWave);
    if (!waveCtx || !audioWaveCanvas) return;

    const w = audioWaveCanvas.width;
    const h = audioWaveCanvas.height;
    waveCtx.clearRect(0, 0, w, h);

    wavePhase += isSpeaking ? 0.25 : 0.04;
    const amp = isSpeaking ? 8 : 2;

    waveCtx.beginPath();
    waveCtx.strokeStyle = isSpeaking ? '#00f0ff' : '#0284c7';
    waveCtx.lineWidth = 1.5;

    for (let x = 0; x < w; x++) {
      const y = h / 2 + Math.sin(x * 0.15 + wavePhase) * amp;
      if (x === 0) waveCtx.moveTo(x, y);
      else waveCtx.lineTo(x, y);
    }
    waveCtx.stroke();
  }
  drawAudioWave();

  // ── Voice / TTS Engine ───────────────────────────────────────────────────
  const voiceToggle = $('#voiceToggle');
  const voiceStopBtn = $('#voiceStopBtn');
  const voiceSel = $('#voiceSelect');
  const voiceSpeed = $('#voiceSpeed');
  const voiceSpeedVal = $('#voiceSpeedVal');

  if (voiceToggle) {
    voiceToggle.addEventListener('click', () => {
      voiceEnabled = !voiceEnabled;
      voiceToggle.classList.toggle('active', voiceEnabled);
      if (!voiceEnabled) stopSpeaking();
    });
  }

  if (voiceStopBtn) {
    voiceStopBtn.addEventListener('click', stopSpeaking);
  }

  if (voiceSpeed) {
    voiceSpeed.addEventListener('input', () => {
      voiceRate = parseFloat(voiceSpeed.value);
      if (voiceSpeedVal) voiceSpeedVal.textContent = voiceRate.toFixed(1) + 'x';
    });
  }

  function loadVoices() {
    if (!synth || !voiceSel) return;
    const voices = synth.getVoices();
    if (!voices.length) return;
    voiceSel.innerHTML = '';

    const englishVoices = voices.filter((v) => v.lang.startsWith('en'));
    const list = englishVoices.length ? englishVoices : voices;

    list.forEach((v, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `${v.name} (${v.lang})`;
      voiceSel.appendChild(opt);
      if (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || i === 0) {
        if (!selectedVoice) {
          selectedVoice = v;
          opt.selected = true;
        }
      }
    });

    voiceSel.addEventListener('change', () => {
      selectedVoice = list[voiceSel.value] || null;
    });
  }

  if (synth) {
    synth.onvoiceschanged = loadVoices;
    loadVoices();
  }

  function speak(text) {
    if (!voiceEnabled || !synth) return;
    stopSpeaking();

    // Clean text of markdown
    const clean = text
      .replace(/```[\s\S]*?```/g, 'Code block omitted.')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/[*#_~>]/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .trim();

    if (!clean) return;

    const utter = new SpeechSynthesisUtterance(clean);
    if (selectedVoice) utter.voice = selectedVoice;
    utter.rate = voiceRate;
    utter.pitch = 1.0;

    utter.onstart = () => {
      isSpeaking = true;
      if (window.friday3D) window.friday3D.setAudioReactive(true, 1.0);
    };

    utter.onend = () => {
      isSpeaking = false;
      if (window.friday3D) window.friday3D.setAudioReactive(false, 0);
    };

    utter.onerror = () => {
      isSpeaking = false;
      if (window.friday3D) window.friday3D.setAudioReactive(false, 0);
    };

    synth.speak(utter);
  }

  function stopSpeaking() {
    if (synth) synth.cancel();
    isSpeaking = false;
    if (window.friday3D) window.friday3D.setAudioReactive(false, 0);
  }

  // ── Markdown Parser ──────────────────────────────────────────────────────
  function renderMarkdown(md) {
    let out = md
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Code blocks
    out = out.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang, code) => {
      return `<pre><code class="lang-${lang}">${code.trim()}</code></pre>`;
    });

    // Inline code
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold / italic
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Headers
    out = out.replace(/^### (.*$)/gim, '<h4 style="color:var(--accent);margin:6px 0;">$1</h4>');
    out = out.replace(/^## (.*$)/gim, '<h3 style="color:var(--accent);margin:8px 0;">$1</h3>');

    // Lists
    out = out.replace(/^\s*-\s+(.*$)/gim, '<li style="margin-left:14px;">$1</li>');

    // Line breaks
    out = out.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
    return out;
  }

  function addMessage(role, text) {
    if (welcomeEl) welcomeEl.style.display = 'none';

    const msg = document.createElement('div');
    msg.className = `message ${role}`;

    const label = document.createElement('span');
    label.className = 'message-label';
    label.textContent = role === 'user' ? 'Operator' : 'FRIDAY';
    msg.appendChild(label);

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = renderMarkdown(text);
    msg.appendChild(bubble);

    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }

  function addTypingIndicator() {
    const el = document.createElement('div');
    el.className = 'message assistant typing';
    el.id = 'typingIndicator';
    el.innerHTML = '<span class="message-label">FRIDAY</span><div class="bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>';
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function removeTypingIndicator() {
    const el = $('#typingIndicator');
    if (el) el.remove();
  }

  // ── WebSocket & Chat Transmit ────────────────────────────────────────────

  function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${location.host}/ws/chat`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        wsConnected = true;
        if (statusDot) {
          statusDot.style.background = 'var(--green)';
          statusDot.style.boxShadow = '0 0 10px var(--green)';
        }
      };

      ws.onclose = () => {
        wsConnected = false;
        if (statusDot) {
          statusDot.style.background = 'var(--yellow)';
          statusDot.style.boxShadow = '0 0 10px var(--yellow)';
        }
        setTimeout(connectWS, 3000);
      };

      let streamingBubble = null;
      let streamedContent = '';

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);

          if (data.type === 'token') {
            removeTypingIndicator();
            if (!streamingBubble) {
              streamingBubble = addMessage('assistant', '');
              if (window.friday3D) window.friday3D.setAudioReactive(true, 0.7);
            }
            streamedContent += data.content;
            streamingBubble.innerHTML = renderMarkdown(streamedContent);
            messagesEl.scrollTop = messagesEl.scrollHeight;
          } else if (data.type === 'done') {
            removeTypingIndicator();
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
            removeTypingIndicator();
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
      wsConnected = false;
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
    addTypingIndicator();

    if (window.friday3D) {
      window.friday3D.setAudioReactive(true, 0.5);
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ message: text }));
        return;
      } catch {
        // Fallback to REST
      }
    }

    // REST Fallback
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      removeTypingIndicator();
      if (data.ok) {
        addMessage('assistant', data.response);
        speak(data.response);
      } else {
        addMessage('assistant', `Notice: ${data.error}`);
      }
    } catch (e) {
      removeTypingIndicator();
      addMessage('assistant', `Connection interrupted: ${e.message}`);
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

  // ── Telemetry & Stats Polling ────────────────────────────────────────────

  function colorForPct(pct) {
    if (pct < 60) return 'green';
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
        els.cpuBar.className = `progress-fill ${colorForPct(c)}`;
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
      if (els.toolsVal) els.toolsVal.textContent = `${s.tools_registered} Modules`;
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
        if (window.friday3D) window.friday3D.setStarkTheme(s.stark_mode);
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
  function switchModel(btn, model) {
    $$('#modelSwitcher .toggle-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    fetch('/api/model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    })
      .then(() => {
        if (modelBadge) modelBadge.textContent = model;
      })
      .catch(() => {});
  }

  $$('#modelSwitcher .toggle-btn').forEach((btn) => {
    btn.addEventListener('click', () => switchModel(btn, btn.dataset.model));
  });

  // ── Quick Actions ────────────────────────────────────────────────────────
  $$('.tool-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const prompt = btn.dataset.prompt || '';
      const text = btn.dataset.text || '';
      if (prompt) {
        inputEl.value = prompt + ' ';
        inputEl.focus();
        inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
      } else if (text) {
        inputEl.value = text;
        sendMessage();
      }
    });
  });

  // ── Keyboard & Input Resizing ────────────────────────────────────────────
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  });

  sendBtn.addEventListener('click', sendMessage);

  // ── Initialize ───────────────────────────────────────────────────────────
  connectWS();
  fetchStats();
  setInterval(fetchStats, 6000);
})();
