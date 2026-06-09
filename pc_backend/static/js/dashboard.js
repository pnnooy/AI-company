// Dashboard.js - 皮皮机器人前端
const API = '/api';

// === State ===
let currentExpr = 'normal';
let currentRgb = [0,0,0];
let ledColor = '#000';
const logLines = [];
const MAX_LOG = 200;

// === Init ===
document.addEventListener('DOMContentLoaded', () => {
  startPolling();
  initChat();
  initDebug();
  initLed();
  fetchCamera();
  setInterval(fetchCamera, 80);    // ~12fps camera
  setInterval(fetchStatus, 500);    // 2Hz status
  setInterval(fetchThoughts, 3000);
});

// === Robot Face (PNG images from actual firmware assets) ===
const faceImages = {};
const exprNames = ['normal','happy','focus','angry','sleep','surprise','sad','love'];
exprNames.forEach(e => {
  faceImages[e] = new Image();
  faceImages[e].src = '/static/img/emo_' + e + '_f0.png';
});

function drawFace(expr) {
  if (expr === currentExpr) return;
  currentExpr = expr;
  const c = document.getElementById('face-canvas');
  const ctx = c.getContext('2d');
  const img = faceImages[expr] || faceImages['normal'];
  if (img.complete) {
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, 0, 0, 80, 80);
  }
  document.getElementById('face-name').textContent = expr;
}

// === LED ===
function initLed() {
  setInterval(() => {
    const el = document.getElementById('led-circle');
    el.style.background = ledColor;
    el.style.boxShadow = `0 0 30px ${ledColor}`;
  }, 200);
}

// === Polling ===
async function fetchStatus() {
  try {
    const r = await fetch(API + '/status');
    const data = await r.json();
    drawFace((data.expression || 'normal').toLowerCase());
    updateEmotion(data.emotion || 0.5);
    document.getElementById('fsm-state').textContent = data.state || 'IDLE';
    // RGB LED
    if (data.rgb) {
      currentRgb = data.rgb;
      ledColor = `rgb(${data.rgb[0]},${data.rgb[1]},${data.rgb[2]})`;
      document.getElementById('led-values').textContent = `(${data.rgb[0]}, ${data.rgb[1]}, ${data.rgb[2]})`;
    }
    document.getElementById('serial-status').className = 'status-dot online';
  } catch(e) {
    document.getElementById('serial-status').className = 'status-dot offline';
  }
}

async function fetchThoughts() {
  try {
    const r = await fetch(API + '/last_thought');
    const data = await r.json();
    if (data.calls > 0) document.getElementById('llm-status').className = 'status-dot online';
    if (data.thought && data.thought !== window._lastThought) {
      window._lastThought = data.thought;
      addChatMsg('thought', data.thought);
    }
  } catch(e) { document.getElementById('llm-status').className = 'status-dot offline'; }
}

async function fetchCamera() {
  try {
    const r = await fetch(API + '/camera_frame');
    if (r.ok) {
      const blob = await r.blob();
      document.getElementById('camera-feed').src = URL.createObjectURL(blob);
      document.getElementById('camera-status').textContent = 'ONLINE';
      document.getElementById('camera-status').className = 'camera-status online';
      document.getElementById('cam-status').className = 'status-dot online';
    }
  } catch(e) {
    document.getElementById('camera-status').textContent = 'OFFLINE';
    document.getElementById('cam-status').className = 'status-dot offline';
  }
}

function updateEmotion(val) {
  const pct = Math.round(val * 100);
  document.getElementById('emotion-value').textContent = val.toFixed(2);
  document.getElementById('emotion-bar').style.width = pct + '%';
  const desc = val > 0.8 ? '非常开心' : val > 0.5 ? '心情不错' : val > 0.3 ? '有点低落' : val > 0.15 ? '不太开心' : '非常难过';
  document.getElementById('emotion-desc').textContent = desc;
}

// === Chat ===
function addChatMsg(type, text, own) {
  const el = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + (type === 'thought' ? 'thought' : own ? 'user' : 'system');
  const now = new Date().toLocaleTimeString();
  div.innerHTML = text + '<span class="time">' + now + '</span>';
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
  // Also log
  addLog(type === 'thought' ? '皮皮' : (own ? '我' : '系统'), text, type === 'thought' ? 'info' : 'info');
}

function initChat() {
  const input = document.getElementById('chat-input');
  const btn = document.getElementById('chat-send');
  function send() {
    const msg = input.value.trim();
    if (!msg) return;
    addChatMsg('user', msg, true);
    input.value = '';
    fetch(API + '/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({message: msg}) })
      .then(r => r.json()).then(d => {
        if (d.ok) addChatMsg('system', '...');
      });
  }
  btn.addEventListener('click', send);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
}

// === Log ===
function addLog(src, msg, level) {
  logLines.push({src, msg, level, ts: new Date().toLocaleTimeString()});
  if (logLines.length > MAX_LOG) logLines.shift();
  const el = document.getElementById('log-container');
  const cls = level || 'info';
  el.innerHTML = logLines.map(l => `<div class="log-entry ${cls}"><span class="ts">${l.ts}</span>[${l.src}] ${l.msg}</div>`).join('');
  el.scrollTop = el.scrollHeight;
}

// === Debug ===
function initDebug() {
  document.getElementById('debug-apply').addEventListener('click', () => {
    const expr = document.getElementById('debug-expr').value;
    const r = document.getElementById('debug-r').value;
    const g = document.getElementById('debug-g').value;
    const b = document.getElementById('debug-b').value;
    fetch(API + '/expression', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({expression: document.getElementById('debug-expr').options[document.getElementById('debug-expr').selectedIndex].text}) });
    fetch(API + '/led', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({r:parseInt(r),g:parseInt(g),b:parseInt(b)}) });
    addLog('调试', `设置表情+LED`, 'info');
  });

  document.getElementById('debug-test-touch').addEventListener('click', () => {
    fetch(API + '/debug/event', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({event:'touch', side:0, type:1}) });
    addLog('调试', '模拟触摸 LEFT TAP', 'warn');
  });

  document.getElementById('debug-test-nfc').addEventListener('click', () => {
    fetch(API + '/debug/event', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({event:'nfc', duration:5, level:1}) });
    addLog('调试', '模拟 NFC SNACK 5s', 'warn');
  });

  const emoRange = document.getElementById('debug-emotion');
  emoRange.addEventListener('input', () => {
    document.getElementById('debug-emotion-val').textContent = (emoRange.value / 100).toFixed(2);
  });
}

// === Initial polling ===
function startPolling() {
  fetchStatus();
  fetchThoughts();
  addLog('系统', '前端已连接', 'info');
}
