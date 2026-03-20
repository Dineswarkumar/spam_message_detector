/* ─────────────────────────────────────────────
   RakshaSutra — app.js
   API layer + dynamic rendering + animations
   ───────────────────────────────────────────── */

const API_BASE = '';   // same origin — FastAPI serves both

/* ────────── State ─────────────────────────── */
let stats = { total: 0, fraud: 0, suspicious: 0, safe: 0 };

/* ────────── DOM helpers ───────────────────── */
const $  = id => document.getElementById(id);
const $$ = sel => document.querySelector(sel);

/* ────────── Toast ─────────────────────────── */
function showToast(msg, duration = 3500) {
  const t = $$('.toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), duration);
}

/* ────────── Health check on load ──────────── */
async function checkHealth() {
  try {
    const r = await fetch(`${API_BASE}/health`);
    const d = await r.json();
    const dot  = $('status-dot-api');
    const lbl  = $('status-label-api');
    if (d.status === 'ok') {
      dot.className  = 'status-dot online';
      lbl.textContent = 'Backend Online';
    } else {
      dot.className  = 'status-dot offline';
      lbl.textContent = 'Backend Error';
    }
  } catch {
    $('status-dot-api').className  = 'status-dot offline';
    $('status-label-api').textContent = 'Backend Offline';
  }
}

/* ────────── Tab switching ─────────────────── */
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  if (tab === 'single') {
    $('single-panel').style.display = 'block';
    $('batch-panel').classList.remove('visible');
    $('batch-panel').style.display = 'none';
  } else {
    $('single-panel').style.display = 'none';
    $('batch-panel').style.display = 'block';
    setTimeout(() => $('batch-panel').classList.add('visible'), 10);
  }
}

/* ────────── Char counter ──────────────────── */
function updateCharCount() {
  const val = $('msg-input').value.length;
  $('char-count').textContent = `${val} / 1000 chars`;
}

/* ────────── Gauge SVG animation ───────────── */
function animateGauge(score) {
  const circ       = 283;      // 2π × 45 (r=45 half-circle)
  // score 0-100 → dashoffset 283 (empty) → 0 (full)
  const offset     = circ - (score / 100) * circ;
  const fill       = $$('.gauge-fill');
  fill.style.strokeDashoffset = offset;

  // Color based on score
  let color = '#22c55e';
  if (score >= 65) color = '#ef4444';
  else if (score >= 35) color = '#f59e0b';
  fill.style.stroke = color;

  // Animate number
  const scoreEl = $('gauge-score');
  let cur = 0;
  const target = score;
  const step = () => {
    cur = Math.min(cur + Math.ceil(target / 40), target);
    scoreEl.textContent = cur;
    if (cur < target) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ────────── Progress bar animation ────────── */
function animateBar(id, pct) {
  const el = $(id);
  setTimeout(() => { el.style.width = pct + '%'; }, 80);
}

/* ────────── Donut chart ────────────────────── */
function animateDonut(mlVal, ruleVal) {
  /* circle r=40 → circumference = 2π×40 ≈ 251 */
  const C   = 251;
  const total = mlVal + ruleVal || 1;
  const mlPct   = mlVal   / total;
  const rulePct = ruleVal / total;

  const mlArc   = C * mlPct;
  const ruleArc = C * rulePct;

  const mlEl   = $$('.donut-ml');
  const ruleEl = $$('.donut-rule');

  // ml arc starts at top, rule arc starts after ml
  mlEl  .style.strokeDasharray  = `${mlArc} ${C}`;
  mlEl  .style.strokeDashoffset = 0;
  ruleEl.style.strokeDasharray  = `${ruleArc} ${C}`;
  // rule starts after ml offset
  ruleEl.style.strokeDashoffset = `-${mlArc}`;

  $('donut-center').textContent   = `${mlVal + ruleVal}`;
  $('legend-ml-val').textContent   = mlVal;
  $('legend-rule-val').textContent = ruleVal;
}

/* ────────── Status helpers ────────────────── */
function statusClass(status) {
  if (status === 'Fraud')      return 'fraud';
  if (status === 'Suspicious') return 'warn';
  return 'safe';
}
function statusIcon(status) {
  if (status === 'Fraud')      return '🚨';
  if (status === 'Suspicious') return '⚠️';
  return '✅';
}
function flagSeverity(flag) {
  const high = ['credential_phishing','suspicious_link','legal_threat','account_threat'];
  const med  = ['prize_bait','urgency','govt_impersonation','kyc_lure','investment_fraud'];
  if (high.includes(flag)) return 'fraud';
  if (med.includes(flag))  return 'warn';
  return 'info';
}
function flagLabel(flag) {
  const map = {
    prize_bait:           '🎰 Prize Bait',
    credential_phishing:  '🔐 Credential Phishing',
    urgency:              '⏱️ Urgency Tactic',
    account_threat:       '🔒 Account Threat',
    kyc_lure:             '📋 KYC Lure',
    suspicious_link:      '🔗 Suspicious Link',
    phone_lure:           '📞 Phone Lure',
    investment_fraud:     '💰 Investment Fraud',
    govt_impersonation:   '🏛️ Govt Impersonation',
    utility_threat:       '⚡ Utility Threat',
    legal_threat:         '⚖️ Legal Threat',
    free_offer:           '🎁 Free Offer',
    loan_fraud:           '🏦 Loan Fraud',
    wfh_fraud:            '🏠 WFH Fraud',
  };
  return map[flag] || flag;
}

/* ────────── Render result ─────────────────── */
function renderResult(data) {
  const sc = statusClass(data.status);

  /* Status badge */
  const badge = $('status-badge');
  badge.className = `status-badge-lg ${sc}`;
  badge.innerHTML = `<span class="badge-pulse"></span>${statusIcon(data.status)} ${data.status}`;

  /* Gauge */
  animateGauge(data.risk_score);

  /* Detail pills */
  $('d-risk').textContent      = `${data.risk_score} / 100`;
  $('d-lang').textContent      = data.language || '—';
  $('d-ml').textContent        = `${(data.ml_confidence * 100).toFixed(1)}%`;
  $('d-rule').textContent      = `${data.rule_score} pts`;

  /* Language badge */
  $('lang-banner').innerHTML = `🌐 Detected language: <strong>${data.language || 'English/Hinglish'}</strong>`;

  /* Progress bars */
  const mlPct   = Math.round(data.ml_confidence * 100);
  const rulePct = Math.min(100, Math.round((data.rule_score / 60) * 100));
  $('bar-ml-pct').textContent   = mlPct + '%';
  $('bar-rule-pct').textContent  = data.rule_score + ' / 60';
  animateBar('bar-ml-fill',   mlPct);
  animateBar('bar-rule-fill', rulePct);

  /* Donut breakdown */
  animateDonut(data.breakdown.ml_component, data.breakdown.rule_component);

  /* Flags */
  const flagsWrap = $('flags-container');
  if (data.flags && data.flags.length > 0) {
    flagsWrap.innerHTML = data.flags.map((f, i) =>
      `<span class="flag-pill ${flagSeverity(f)}" style="animation-delay:${i * 60}ms">${flagLabel(f)}</span>`
    ).join('');
  } else {
    flagsWrap.innerHTML = '<span class="no-flags">No specific threat patterns detected</span>';
  }

  /* Reasons */
  const reasonsEl = $('reasons-list');
  if (data.reasons && data.reasons.length > 0) {
    reasonsEl.innerHTML = data.reasons.map((r, i) =>
      `<li class="reason-item" style="animation-delay:${i * 80}ms"><span class="reason-dot"></span>${r}</li>`
    ).join('');
  } else {
    reasonsEl.innerHTML = '<span class="no-reasons">No specific rules triggered</span>';
  }

  /* Verdict */
  const vEl = $('verdict-card');
  vEl.className = `verdict-card ${sc}`;
  const verdictIcons = { safe:'🛡️', warn:'⚠️', fraud:'🚨' };
  vEl.innerHTML = `<span class="verdict-icon">${verdictIcons[sc]}</span>${data.verdict}`;

  /* Show panel */
  const panel = $('results-panel');
  panel.classList.remove('visible');
  panel.style.display = 'block';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => panel.classList.add('visible'));
  });
}

/* ────────── Analyze single ────────────────── */
async function analyzeMessage() {
  const text = $('msg-input').value.trim();
  if (!text) { showToast('⚠️ Please enter a message to analyze'); return; }

  const btn = $('analyze-btn');
  btn.classList.add('loading');
  btn.disabled = true;

  try {
    const res  = await fetch(`${API_BASE}/api/predict`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ text }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    renderResult(data);
    updateStats(data.status);
  } catch (e) {
    showToast(`❌ Error: ${e.message}`);
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

/* ────────── Stats counter ─────────────────── */
function updateStats(status) {
  stats.total++;
  if      (status === 'Fraud')      stats.fraud++;
  else if (status === 'Suspicious') stats.suspicious++;
  else                              stats.safe++;
  $('stat-total').textContent     = stats.total;
  $('stat-fraud').textContent     = stats.fraud;
  $('stat-safe').textContent      = stats.safe;
}

/* ────────── Batch analyze ─────────────────── */
async function batchAnalyze() {
  const raw = $('batch-input').value.trim();
  if (!raw) { showToast('⚠️ Please enter messages (one per line)'); return; }

  const messages = raw.split('\n').map(m => m.trim()).filter(Boolean);
  if (messages.length > 50) { showToast('⚠️ Maximum 50 messages per batch'); return; }

  const btn = $('batch-btn');
  btn.disabled = true;
  btn.innerHTML = '<span style="animation:spin .7s linear infinite;display:inline-block">⏳</span> Analyzing…';

  try {
    const res  = await fetch(`${API_BASE}/api/batch_predict`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ messages }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    renderBatchResult(data);
  } catch (e) {
    showToast(`❌ Error: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🔍 Analyze Batch';
  }
}

/* ────────── Render batch result ───────────── */
function renderBatchResult(data) {
  const results = data.results;
  const total   = results.length;
  const fraud   = data.fraud_count;
  const susp    = data.suspicious_count;
  const safe    = total - fraud - susp;

  $('b-total').textContent = total;
  $('b-fraud').textContent = fraud;
  $('b-susp') .textContent = susp;
  $('b-safe') .textContent = safe;

  const tbody = $('batch-tbody');
  tbody.innerHTML = results.map((r, i) => {
    const sc = statusClass(r.status);
    const short = r.text.length > 60 ? r.text.substring(0, 60) + '…' : r.text;
    const mlPct  = r.ml_confidence != null ? `${(r.ml_confidence * 100).toFixed(1)}%` : 'N/A';
    return `<tr style="animation:fadeUp .3s ${i * 40}ms ease both">
      <td>${i + 1}</td>
      <td class="tbl-msg" title="${r.text.replace(/"/g,'&quot;')}">${short}</td>
      <td><span class="tbl-badge ${sc}">${statusIcon(r.status)} ${r.status}</span></td>
      <td>${r.risk_score ?? 'N/A'}</td>
      <td>${mlPct}</td>
      <td>${r.language || '–'}</td>
      <td>${r.flags ? r.flags.slice(0,2).map(f => `<span class="tbl-badge ${flagSeverity(f)}" style="margin-right:4px;font-size:.68rem">${f}</span>`).join('') : '–'}</td>
    </tr>`;
  }).join('');

  $('batch-results').style.display = 'block';
}

/* ────────── Keyboard shortcut ─────────────── */
document.addEventListener('keydown', e => {
  if (e.ctrlKey && e.key === 'Enter') analyzeMessage();
});

/* ────────── Init ───────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  setInterval(checkHealth, 30000);

  // Example message (fade in slowly)
  setTimeout(() => {
    const ta = $('msg-input');
    if (!ta.value) {
      ta.placeholder = 'Paste a suspicious message here…\n\nExample: "You have won a Rs 10,00,000 prize! Click http://bit.ly/claim to collect your reward immediately."';
    }
  }, 500);
});
