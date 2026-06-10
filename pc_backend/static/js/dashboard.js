// Dashboard.js - 皮皮机器人前端
const API = '/api';

// === State ===
let currentExpr = 'normal';
let currentRgb = [30,20,60];
let ledColor = 'rgb(30,20,60)';
const logLines = [];
const MAX_LOG = 200;

// === Init ===
document.addEventListener('DOMContentLoaded', () => {
  startPolling();
  initChat();
  initDebug();
  initLed();
  fetchCamera();
  setInterval(fetchCamera, 80);
  setInterval(fetchStatus, 500);
  setInterval(fetchThoughts, 3000);
  // 动态匹配聊天框高度到左侧
  matchChatHeight();
  window.addEventListener('resize', matchChatHeight);
  setInterval(matchChatHeight, 2000);
});

function matchChatHeight() {
  const left = document.querySelector('.left-col');
  const chatCard = document.querySelector('.right-col .chat-card');
  if (left && chatCard) {
    chatCard.style.maxHeight = left.offsetHeight + 'px';
  }
}

// === Robot Face (img tag, animated 3 frames) ===
const ANIM_RATES = { normal:300, happy:200, focus:500, angry:300, sleep:1000, surprise:200, sad:400, love:300 };
let faceTimer = null;
let faceFrame = 0;

function drawFace(expr) {
  if (!expr || !ANIM_RATES[expr]) expr = 'normal';
  if (expr === currentExpr && faceTimer) return;
  currentExpr = expr;

  if (faceTimer) { clearInterval(faceTimer); faceTimer = null; }
  faceFrame = 0;

  const el = document.getElementById('face-img');
  el.src = '/static/img/emo_' + expr + '_f0.png';
  document.getElementById('face-name').textContent = expr;

  faceTimer = setInterval(() => {
    faceFrame = (faceFrame + 1) % 3;
    document.getElementById('face-img').src = '/static/img/emo_' + expr + '_f' + faceFrame + '.png';
  }, ANIM_RATES[expr] || 300);
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
    // emotion 可能是 0（合法值），不能用 || 0.5
    updateEmotion(data.emotion != null ? data.emotion : 0.5);
    document.getElementById('fsm-state').textContent = data.state || 'IDLE';
    if (data.rgb) {
      currentRgb = data.rgb;
      ledColor = `rgb(${data.rgb[0]},${data.rgb[1]},${data.rgb[2]})`;
    }
    // 用户情绪
    if (data.user_emotion && data.user_emotion !== 'neutral') {
      const el = document.getElementById('user-emotion');
      el.style.display = 'block';
      document.getElementById('user-emotion-label').textContent =
        data.user_emotion + ' (' + Math.round((data.user_emotion_conf||0)*100) + '%)';
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
    // 显示内心独白
    if (data.thought && data.thought !== window._lastThought) {
      window._lastThought = data.thought;
      addChatMsg('thought', data.thought);
    }
    // 显示聊天回复（必须有内容才显示）
    if (data.reply && data.reply.trim() && data.reply !== window._lastReply) {
      window._lastReply = data.reply;
      addChatMsg('system', data.reply);
    }
  } catch(e) { document.getElementById('llm-status').className = 'status-dot offline'; }
}

async function fetchCamera() {
  try {
    const r = await fetch(API + '/camera_frame?t=' + Date.now());
    if (r.ok) {
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const img = document.getElementById('camera-feed');
      const oldUrl = img.src;
      img.src = url;
      if (oldUrl && oldUrl.startsWith('blob:')) URL.revokeObjectURL(oldUrl);
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
    const exprName = document.getElementById('debug-expr').options[document.getElementById('debug-expr').selectedIndex].text;
    const r = document.getElementById('debug-r').value;
    const g = document.getElementById('debug-g').value;
    const b = document.getElementById('debug-b').value;
    const emotion = parseInt(document.getElementById('debug-emotion').value) / 100;
    fetch(API + '/expression', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({expression: exprName}) });
    fetch(API + '/led', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({r:parseInt(r),g:parseInt(g),b:parseInt(b)}) });
    fetch(API + '/debug/emotion', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({emotion: emotion}) });
    addLog('调试', `设置 表情=${exprName} LED=(${r},${g},${b}) 情绪=${emotion.toFixed(2)}`, 'info');
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
    const v = (emoRange.value / 100).toFixed(2);
    document.getElementById('debug-emotion-val').textContent = v;
    // 拖动即时生效
    fetch(API + '/debug/emotion', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({emotion: parseFloat(v)}) });
  });
}

// === Initial polling ===
function startPolling() {
  fetchStatus();
  fetchThoughts();
  addLog('系统', '前端已连接', 'info');
}
