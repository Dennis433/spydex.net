function fmt(n) {
  if (n == null || isNaN(n)) return '—';
  const v = parseFloat(n);
  if (!isFinite(v) || v <= 0) return '—';
  if (v >= 1e12) return (v / 1e12).toFixed(2) + 'T';
  if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(2) + 'K';
  if (v >= 1) return v.toFixed(2);
  if (v >= 0.01) return v.toFixed(4);
  if (v >= 0.000001) return v.toFixed(6);
  if (v < 1e-10) return '—';
  return v.toExponential(2);
}

function decodeCurrency(hex) {
  if (!hex || hex.length <= 4) return hex;
  try {
    const clean = hex.replace(/00+$/, '');
    const bytes = clean.match(/.{1,2}/g).map(b => parseInt(b, 16));
    const str = String.fromCharCode(...bytes).replace(/\x00/g, '').trim();
    return /^[\x20-\x7E]+$/.test(str) ? str : hex.slice(0, 10);
  } catch { return hex.slice(0, 10); }
}

function age(ms) {
  if (!ms) return '—';
  const sec = Math.floor((Date.now() - ms) / 1000);
  if (sec < 3600) return Math.floor(sec / 60) + 'm';
  if (sec < 86400) return Math.floor(sec / 3600) + 'h';
  return Math.floor(sec / 86400) + 'd';
}

function tokenIcon(t) {
  if (t.icon) return `/api/image?url=${encodeURIComponent(t.icon)}`;
  return null;
}

function drawSparkline(canvas, prices, isUp) {
  if (!canvas || !prices || prices.length < 2) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const min = Math.min(...prices), max = Math.max(...prices);
  const range = max - min || 1;
  const color = isUp ? '#00c896' : '#e05252';
  ctx.clearRect(0, 0, w, h);
  ctx.beginPath();
  prices.forEach((p, i) => {
    const x = (i / (prices.length - 1)) * w;
    const y = h - ((p - min) / range) * (h - 4) - 2;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

async function fetchSparkline(md5) {
  try {
    const res = await fetch(`/api/sparkline/${md5}`);
    const data = await res.json();
    return Array.isArray(data) ? data : (data.data || data.sparkline || []);
  } catch { return []; }
}

// Ping
let pingStart = Date.now();
setInterval(() => {
  const p = Date.now() - pingStart;
  const el = document.getElementById('pingVal');
  if (el) el.textContent = p;
  pingStart = Date.now();
}, 2000);

// State
let allTokens = [];
let featIndex = 0;
let currentTab = 'latest';
let currentStart = 0;
let totalTokens = 0;
let isLoading = false;
let hasMore = true;
const PAGE_SIZE = 20;

// Search
function filterTokens() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const filtered = q
    ? allTokens.filter(t =>
        (t._symbol || '').toLowerCase().includes(q) ||
        (t.name || '').toLowerCase().includes(q))
    : allTokens;
  renderList(filtered, true);
}

function toggleSearch() {
  const bar = document.getElementById('searchBar');
  const inp = document.getElementById('searchInput');
  if (bar.style.display === 'none') {
    bar.style.display = 'flex';
    inp.focus();
  } else {
    bar.style.display = 'none';
    inp.value = '';
    renderList(allTokens, true);
  }
}

// FEATURED SLIDER
function renderFeatured(tokens) {
  const slider = document.getElementById('featuredSlider');
  const dots = document.getElementById('featDots');
  const items = tokens.slice(0, 6);

  slider.innerHTML = items.map((t, i) => {
    const sym = t._symbol;
    const icon = tokenIcon(t);
    const change = t.pro24h;
    const changeClass = (change >= 0) ? 'up' : 'down';
    const changeStr = change != null
      ? (change >= 0 ? '+' : '') + parseFloat(change).toFixed(2) + '%'
      : '—';
    const ageTxt = age(t.dateon);

    return `
      <div class="feat-slide ${i === 0 ? 'active' : ''}" data-index="${i}">
        <div class="feat-slide-top">
          <div class="feat-slide-icon">
            ${icon
              ? `<img src="${icon}" onerror="this.parentElement.innerHTML='⬡'">`
              : '⬡'}
          </div>
          <div class="feat-slide-info">
            <div class="feat-slide-name">${sym}</div>
            <div class="feat-slide-sub">${t.name || sym}</div>
            <div class="feat-slide-meta">
              ${ageTxt !== '—' ? ageTxt + ' · ' : ''}
              ${t.issuer ? t.issuer.slice(0, 8) + '…' : ''}
              <span class="feat-slide-change ${changeClass}">${changeStr}</span>
            </div>
          </div>
        </div>
        <div class="feat-slide-stats">
          <div class="feat-stat">
            <div class="feat-stat-label">MCAP</div>
            <div class="feat-stat-val">✕ ${fmt(t.marketcap)}</div>
          </div>
          <div class="feat-stat">
            <div class="feat-stat-label">VOL 24H</div>
            <div class="feat-stat-val">✕ ${fmt(t.vol24hxrp)}</div>
          </div>
          <div class="feat-stat">
            <div class="feat-stat-label">HOLDERS</div>
            <div class="feat-stat-val">${fmt(t.holders)}</div>
          </div>
          <div class="feat-stat">
            <div class="feat-stat-label">TXNS</div>
            <div class="feat-stat-val">${t.txns24h || '—'}</div>
          </div>
        </div>
        <div class="feat-slide-chart">
          <canvas id="feat-canvas-${i}" width="400" height="60"></canvas>
        </div>
      </div>
    `;
  }).join('');

  dots.innerHTML = items.map((_, i) =>
    `<div class="feat-dot ${i === 0 ? 'active' : ''}" onclick="goFeat(${i})"></div>`
  ).join('');

  items.forEach(async (t, i) => {
    if (!t.md5) return;
    const prices = await fetchSparkline(t.md5);
    const canvas = document.getElementById(`feat-canvas-${i}`);
    if (canvas) drawSparkline(canvas, prices, (t.pro24h || 0) >= 0);
  });
}

function goFeat(index) {
  const slides = document.querySelectorAll('.feat-slide');
  const dots = document.querySelectorAll('.feat-dot');
  slides.forEach(s => s.classList.remove('active'));
  dots.forEach(d => d.classList.remove('active'));
  featIndex = Math.max(0, Math.min(index, slides.length - 1));
  if (slides[featIndex]) slides[featIndex].classList.add('active');
  if (dots[featIndex]) dots[featIndex].classList.add('active');
}

function slideFeat(dir) { goFeat(featIndex + dir); }

// Build single token row
function buildRow(t, globalIndex) {
  const sym = t._symbol;
  const icon = tokenIcon(t);
  const change = t.pro24h;
  const changeClass = (change >= 0) ? 'up' : 'down';
  const changeStr = change != null
    ? (change >= 0 ? '+' : '') + parseFloat(change).toFixed(2) + '%'
    : '—';

  return `
    <div class="token-row" data-index="${globalIndex}">
      <div class="tok-icon">
        ${icon
          ? `<img src="${icon}" onerror="this.parentElement.innerHTML='⬡'">`
          : '⬡'}
        <div class="tok-icon-badge">⬡</div>
      </div>
      <div class="tok-info">
        <div class="tok-symbol">
          ${sym}
          <span class="tok-symbol-icons">
            <span class="tok-symbol-icon">ℹ</span>
            <span class="tok-symbol-icon">⧉</span>
          </span>
        </div>
        <div class="tok-name">${t.name || ''}</div>
      </div>
      <div class="tok-right">
        <canvas class="tok-spark" id="list-spark-${globalIndex}" width="80" height="32"></canvas>
        <div class="tok-mcap">✕ ${fmt(t.marketcap)}</div>
        <div class="tok-change ${changeClass}">${changeStr}</div>
      </div>
    </div>
  `;
}

// Render list
function renderList(tokens, replace = false) {
  const list = document.getElementById('tokenList');

  const spinner = document.getElementById('scroll-spinner');
  if (spinner) spinner.remove();

  const endMsg = document.getElementById('scroll-end');
  if (endMsg) endMsg.remove();

  if (replace) list.innerHTML = '';

  if (!tokens || tokens.length === 0) {
    if (replace) list.innerHTML = '<div class="list-loading">No tokens found.</div>';
    return;
  }

  const startIndex = replace ? 0 : list.querySelectorAll('.token-row').length;
  list.insertAdjacentHTML('beforeend',
    tokens.map((t, i) => buildRow(t, startIndex + i)).join('')
  );

  tokens.forEach(async (t, i) => {
    if (!t.md5) return;
    const prices = await fetchSparkline(t.md5);
    const canvas = document.getElementById(`list-spark-${startIndex + i}`);
    if (canvas) drawSparkline(canvas, prices, (t.pro24h || 0) >= 0);
  });

  if (hasMore) {
    list.insertAdjacentHTML('beforeend', `
      <div id="scroll-spinner" class="scroll-spinner">
        <div class="spinner-dot"></div>
        <div class="spinner-dot"></div>
        <div class="spinner-dot"></div>
      </div>
    `);
  } else {
    list.insertAdjacentHTML('beforeend',
      `<div id="scroll-end" class="scroll-end">
         — ${totalTokens.toLocaleString()} tokens total —
       </div>`
    );
  }
}

// Load a page
function loadPage(replace = false) {
  if (isLoading || !hasMore) return;
  isLoading = true;

  fetch(`/api/${currentTab}?start=${currentStart}&limit=${PAGE_SIZE}`)
    .then(r => r.json())
    .then(data => {
      const raw = Array.isArray(data) ? data : (data.tokens || []);
      totalTokens = data.total || raw.length;

      const newTokens = raw.map(t => ({
        ...t,
        _symbol: decodeCurrency(t.currency || t.slug || t.symbol || '???')
      }));

      if (replace) {
        allTokens = newTokens;
        renderFeatured(allTokens);
      } else {
        allTokens = [...allTokens, ...newTokens];
      }

      currentStart += newTokens.length;
      hasMore = currentStart < totalTokens && newTokens.length === PAGE_SIZE;

      renderList(newTokens, replace);
      isLoading = false;
    })
    .catch(err => {
      console.error(err);
      isLoading = false;
      if (replace) {
        document.getElementById('tokenList').innerHTML =
          '<div class="list-loading">Failed to load. Check connection.</div>';
      }
    });
}

// Infinite scroll
function setupInfiniteScroll() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !isLoading && hasMore) {
        loadPage(false);
      }
    });
  }, { rootMargin: '300px' });

  const list = document.getElementById('tokenList');
  const mutObs = new MutationObserver(() => {
    const spinner = document.getElementById('scroll-spinner');
    if (spinner) observer.observe(spinner);
  });
  mutObs.observe(list, { childList: true });
}

// Switch tab
function switchTab(endpoint, el) {
  if (currentTab === endpoint && currentStart > 0) return;
  currentTab = endpoint;
  currentStart = 0;
  hasMore = true;
  allTokens = [];
  featIndex = 0;

  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  if (el) el.classList.add('active');

  document.getElementById('tokenList').innerHTML =
    '<div class="list-loading">Loading...</div>';
  document.getElementById('featuredSlider').innerHTML =
    '<div class="feat-loading">Loading...</div>';

  loadPage(true);
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  setupInfiniteScroll();
  loadPage(true);
});