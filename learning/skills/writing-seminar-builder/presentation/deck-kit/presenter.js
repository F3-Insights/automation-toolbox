/* ============================================================
   F3 Insights - Seminar presenter runtime
   Handles slide navigation, fullscreen, view toggle, scaling,
   scroll-reveal, and the presenter notes window.

   Keyboard:
     ← / ↑ / Page Up        previous slide
     → / ↓ / Page Down / Space   next slide
     Home / End             first / last
     F                      toggle fullscreen
     S                      open presenter window
     V                      toggle slide ↔ scroll view
     Esc                    exit fullscreen

   URL params:
     ?view=scroll | ?view=slides
   URL hash:
     #N    jump to slide N (1-based) in slide mode
   ============================================================ */
(function () {
  'use strict';

  // ----------------------------------------------------------------
  // State
  // ----------------------------------------------------------------
  const body = document.body;
  const slides = Array.from(document.querySelectorAll('.slide'));
  if (!slides.length) return;

  const total = slides.length;
  slides.forEach((s, i) => {
    s.dataset.idx = String(i + 1);
    s.dataset.sectionNum = String(i + 1).padStart(2, '0');
    s.dataset.sectionTotal = String(total).padStart(2, '0');
    // Count distinct build steps inside this slide
    const buildEls = s.querySelectorAll('[data-build]');
    const maxBuild = Array.from(buildEls).reduce((m, el) => {
      const n = parseInt(el.dataset.build, 10);
      return Number.isFinite(n) && n > m ? n : m;
    }, 0);
    s.dataset.maxBuild = String(maxBuild);
  });

  let current = 0;          // 0-based slide index
  let buildStep = 0;        // current build step within the slide
  let presenterWin = null;

  // ----------------------------------------------------------------
  // Mode (slide vs scroll)
  // ----------------------------------------------------------------
  function getInitialMode() {
    const params = new URLSearchParams(location.search);
    const view = params.get('view');
    if (view === 'scroll') return 'scroll';
    if (view === 'slides') return 'slides';
    return 'slides'; // default
  }
  function setMode(mode) {
    body.classList.remove('mode-slides', 'mode-scroll');
    body.classList.add(mode === 'scroll' ? 'mode-scroll' : 'mode-slides');
    const params = new URLSearchParams(location.search);
    params.set('view', mode);
    const newSearch = '?' + params.toString();
    const hash = location.hash;
    history.replaceState(null, '', location.pathname + newSearch + hash);
    if (mode === 'slides') {
      enterSlideMode();
    } else {
      enterScrollMode();
    }
    updateToggleLabel();
  }
  function updateToggleLabel() {
    const btn = document.querySelector('.view-toggle');
    if (!btn) return;
    const inScroll = body.classList.contains('mode-scroll');
    btn.textContent = inScroll ? 'Slide view' : 'Scroll view';
    btn.setAttribute('aria-label', inScroll ? 'Switch to slide view' : 'Switch to scroll view');
  }

  // ----------------------------------------------------------------
  // Slide mode
  // ----------------------------------------------------------------
  function enterSlideMode() {
    // Hash takes precedence; otherwise start at slide 1
    const hashIdx = parseInt(location.hash.replace('#', ''), 10);
    const start = Number.isFinite(hashIdx) && hashIdx >= 1 && hashIdx <= total ? hashIdx - 1 : current;
    showSlide(start);
    fitSlide();
    updateProgress();
    updateCounter();
  }
  function showSlide(idx, opts) {
    if (idx < 0) idx = 0;
    if (idx >= total) idx = total - 1;
    current = idx;
    slides.forEach((s, i) => s.classList.toggle('is-active', i === idx));
    // Reset build state on slide entry. If opts.atEnd, jump to last build
    // (used when stepping backward from the next slide).
    const maxBuild = parseInt(slides[idx].dataset.maxBuild || '0', 10);
    buildStep = opts && opts.atEnd ? maxBuild : 0;
    applyBuildState();
    if (location.hash !== '#' + (idx + 1)) {
      const params = location.search;
      history.replaceState(null, '', location.pathname + params + '#' + (idx + 1));
    }
    updateProgress();
    updateCounter();
    pushToPresenter();
  }

  function applyBuildState() {
    const slide = slides[current];
    if (!slide) return;
    const els = slide.querySelectorAll('[data-build]');
    els.forEach(el => {
      const n = parseInt(el.dataset.build, 10);
      el.classList.toggle('in', Number.isFinite(n) && n <= buildStep);
    });
  }
  function fitSlide() {
    if (!body.classList.contains('mode-slides')) return;
    const w = window.innerWidth;
    const h = window.innerHeight;
    const cs = getComputedStyle(document.documentElement);
    const slideW = parseFloat(cs.getPropertyValue('--slide-w')) || 1280;
    const slideH = parseFloat(cs.getPropertyValue('--slide-h')) || 720;
    // Leave a little breathing room (3%) around the slide
    const pad = 0.96;
    const scale = Math.min((w * pad) / slideW, (h * pad) / slideH);
    document.documentElement.style.setProperty('--scale', scale.toString());
  }
  function next() {
    const maxBuild = parseInt(slides[current].dataset.maxBuild || '0', 10);
    if (buildStep < maxBuild) {
      buildStep++;
      applyBuildState();
      updateProgress();
      pushToPresenter();
      return;
    }
    if (current < total - 1) showSlide(current + 1);
  }
  function prev() {
    if (buildStep > 0) {
      buildStep--;
      applyBuildState();
      updateProgress();
      pushToPresenter();
      return;
    }
    if (current > 0) showSlide(current - 1, { atEnd: true });
  }

  // ----------------------------------------------------------------
  // Scroll mode
  // ----------------------------------------------------------------
  function enterScrollMode() {
    document.documentElement.style.removeProperty('--scale');
    // Scroll to hashed section if any
    const hashIdx = parseInt(location.hash.replace('#', ''), 10);
    if (Number.isFinite(hashIdx) && hashIdx >= 1 && hashIdx <= total) {
      setTimeout(() => slides[hashIdx - 1].scrollIntoView({ behavior: 'instant', block: 'start' }), 0);
    } else {
      window.scrollTo(0, 0);
    }
    setupRevealObserver();
    setupScrollProgress();
  }
  let revealObserver = null;
  function setupRevealObserver() {
    if (revealObserver) revealObserver.disconnect();
    revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -80px 0px' });
    slides.forEach(s => revealObserver.observe(s));
  }
  let scrollListener = null;
  function setupScrollProgress() {
    if (scrollListener) window.removeEventListener('scroll', scrollListener);
    const bar = document.querySelector('.deck-progress');
    if (!bar) return;
    scrollListener = () => {
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      const pct = max > 0 ? (window.scrollY / max) * 100 : 0;
      bar.style.width = pct + '%';
    };
    window.addEventListener('scroll', scrollListener, { passive: true });
    scrollListener();
  }

  // ----------------------------------------------------------------
  // Progress bar (slide mode) + counter
  // ----------------------------------------------------------------
  function updateProgress() {
    const bar = document.querySelector('.deck-progress');
    if (!bar) return;
    if (!body.classList.contains('mode-slides')) return;
    // Smooth progress that accounts for builds within a slide.
    const maxBuild = parseInt(slides[current].dataset.maxBuild || '0', 10);
    const within = maxBuild > 0 ? (buildStep / (maxBuild + 1)) : 0;
    const pct = ((current + within) / total) * 100;
    bar.style.width = pct + '%';
  }
  function updateCounter() {
    const el = document.querySelector('.deck-counter');
    if (!el) return;
    el.textContent = String(current + 1).padStart(2, '0') + ' / ' + String(total).padStart(2, '0');
  }

  // ----------------------------------------------------------------
  // Fullscreen
  // ----------------------------------------------------------------
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  }

  // ----------------------------------------------------------------
  // Presenter window
  // ----------------------------------------------------------------
  function openPresenter() {
    if (presenterWin && !presenterWin.closed) {
      presenterWin.focus();
      return;
    }
    const w = window.open('', 'f3-presenter', 'width=1080,height=640,popup=yes');
    if (!w) {
      alert('Presenter window blocked - allow popups for this page.');
      return;
    }
    w.document.write(presenterHTML());
    w.document.close();
    presenterWin = w;
    // Wire keyboard nav from presenter window back to the main one
    w.addEventListener('keydown', handleKey);
    // Timer
    const start = Date.now();
    w.__timerInterval = w.setInterval(() => {
      const el = w.document.getElementById('timer');
      if (!el) return;
      const elapsed = Math.floor((Date.now() - start) / 1000);
      const m = Math.floor(elapsed / 60);
      const s = elapsed % 60;
      el.textContent = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }, 1000);
    pushToPresenter();
  }
  function pushToPresenter() {
    if (!presenterWin || presenterWin.closed) return;
    const cur = slides[current];
    const nxt = slides[current + 1];
    const doc = presenterWin.document;
    const titleEl = cur.querySelector('.slide-head h2');
    const subEl = cur.querySelector('.slide-head .sub');
    const notesEl = cur.querySelector('.notes');
    doc.getElementById('cur-title').textContent = titleEl ? titleEl.textContent.trim() : (cur.dataset.layout || 'Slide ' + (current + 1));
    doc.getElementById('cur-sub').textContent = subEl ? subEl.textContent.trim() : '';
    doc.getElementById('cur-num').textContent = (current + 1) + ' / ' + total;
    doc.getElementById('cur-notes').innerHTML = notesEl ? notesEl.innerHTML : '<em>(no notes for this slide)</em>';
    if (nxt) {
      const nxtTitleEl = nxt.querySelector('.slide-head h2');
      doc.getElementById('next-title').textContent = nxtTitleEl ? nxtTitleEl.textContent.trim() : 'Slide ' + (current + 2);
    } else {
      doc.getElementById('next-title').textContent = '- end of deck -';
    }
  }
  function presenterHTML() {
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>F3 Presenter</title>
<style>
  :root { --navy:#1E3A6E; --gold:#8F6B2E; --gold-foil:#C9A24B; --ink:#0F172A; --muted:#5A6473; --paper:#F6F7F9; --line:rgba(15,23,42,.12); }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:"Inter",-apple-system,sans-serif; background:#0b1426; color:#fff; padding:24px; min-height:100vh; }
  .hd { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:18px; }
  .hd .left { font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.3em; text-transform:uppercase; color:var(--gold-foil); }
  .hd .right { font-family:"IBM Plex Mono",monospace; font-size:22px; color:var(--gold-foil); font-weight:600; }
  .grid { display:grid; grid-template-columns:1.4fr 1fr; gap:22px; }
  .pane { background:#11203a; border:1px solid rgba(255,255,255,.08); padding:24px 28px; }
  .pane h2 { font-size:30px; line-height:1.1; margin-bottom:10px; font-weight:800; letter-spacing:-.02em; }
  .pane .sub { font-style:italic; color:#a7c1e6; font-size:17px; margin-bottom:18px; }
  .pane .label { font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.3em; text-transform:uppercase; color:var(--gold-foil); margin-bottom:14px; display:block; }
  .notes { font-size:16px; line-height:1.6; color:#dce6f5; }
  .notes p + p { margin-top:12px; }
  .next h3 { font-size:20px; font-weight:700; margin-top:8px; color:#fff; }
  .controls { margin-top:16px; padding-top:14px; border-top:1px solid rgba(255,255,255,.08); font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.18em; text-transform:uppercase; color:rgba(255,255,255,.55); line-height:1.8; }
  .controls span { display:inline-block; padding:3px 8px; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12); margin-right:6px; }
  .timer-pane { display:flex; flex-direction:column; }
  #timer { font-family:"IBM Plex Mono",monospace; font-size:54px; font-weight:600; color:var(--gold-foil); letter-spacing:.05em; margin:auto 0; }
</style>
</head>
<body>
  <div class="hd">
    <span class="left">F3 Insights · Presenter</span>
    <span id="cur-num" class="right">- / -</span>
  </div>
  <div class="grid">
    <div class="pane">
      <span class="label">Current slide</span>
      <h2 id="cur-title">-</h2>
      <p class="sub" id="cur-sub"></p>
      <div class="notes" id="cur-notes"></div>
    </div>
    <div>
      <div class="pane next">
        <span class="label">Next up</span>
        <h3 id="next-title">-</h3>
      </div>
      <div class="pane timer-pane" style="margin-top:22px;">
        <span class="label">Time elapsed</span>
        <div id="timer">00:00</div>
      </div>
      <div class="controls">
        <div><span>←</span><span>→</span> navigate</div>
        <div><span>F</span> fullscreen <span>S</span> presenter <span>V</span> toggle view</div>
      </div>
    </div>
  </div>
</body></html>`;
  }

  // ----------------------------------------------------------------
  // Keyboard
  // ----------------------------------------------------------------
  function handleKey(e) {
    // In scroll mode, only react to V / S / F (not arrows - let the user scroll)
    const inSlides = body.classList.contains('mode-slides');
    const k = e.key;
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;

    if (k === 'v' || k === 'V') {
      e.preventDefault();
      setMode(inSlides ? 'scroll' : 'slides');
      return;
    }
    if (k === 'f' || k === 'F') {
      e.preventDefault();
      toggleFullscreen();
      return;
    }
    if (k === 's' || k === 'S') {
      e.preventDefault();
      openPresenter();
      return;
    }
    if (!inSlides) return;

    if (k === 'ArrowRight' || k === 'ArrowDown' || k === 'PageDown' || k === ' ') {
      e.preventDefault();
      next();
    } else if (k === 'ArrowLeft' || k === 'ArrowUp' || k === 'PageUp') {
      e.preventDefault();
      prev();
    } else if (k === 'Home') {
      e.preventDefault();
      showSlide(0);
    } else if (k === 'End') {
      e.preventDefault();
      showSlide(total - 1);
    }
  }

  // ----------------------------------------------------------------
  // Hash → slide sync (manual navigation via URL)
  // ----------------------------------------------------------------
  window.addEventListener('hashchange', () => {
    if (!body.classList.contains('mode-slides')) return;
    const idx = parseInt(location.hash.replace('#', ''), 10);
    if (Number.isFinite(idx) && idx >= 1 && idx <= total) {
      showSlide(idx - 1);
    }
  });

  // ----------------------------------------------------------------
  // Resize handling
  // ----------------------------------------------------------------
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(fitSlide, 80);
  });

  // ----------------------------------------------------------------
  // View toggle button
  // ----------------------------------------------------------------
  function installToggleButton() {
    if (document.querySelector('.view-toggle')) return;
    const btn = document.createElement('button');
    btn.className = 'view-toggle';
    btn.type = 'button';
    btn.textContent = 'Scroll view';
    btn.addEventListener('click', () => {
      const inSlides = body.classList.contains('mode-slides');
      setMode(inSlides ? 'scroll' : 'slides');
    });
    document.body.appendChild(btn);
  }
  function installProgressAndCounter() {
    if (!document.querySelector('.deck-progress')) {
      const bar = document.createElement('div');
      bar.className = 'deck-progress';
      document.body.appendChild(bar);
    }
    if (!document.querySelector('.deck-counter')) {
      const c = document.createElement('div');
      c.className = 'deck-counter';
      document.body.appendChild(c);
    }
  }

  // ----------------------------------------------------------------
  // Click navigation in slide mode - click right half to advance,
  // click left half to go back. Excludes interactive elements.
  // ----------------------------------------------------------------
  function installClickNav() {
    document.addEventListener('click', (e) => {
      if (!body.classList.contains('mode-slides')) return;
      // ignore clicks on buttons / links / the view toggle
      if (e.target.closest('button, a, .view-toggle')) return;
      const x = e.clientX;
      const w = window.innerWidth;
      if (x > w / 2) next();
      else prev();
    });
  }

  // ----------------------------------------------------------------
  // Boot
  // ----------------------------------------------------------------
  function boot() {
    installToggleButton();
    installProgressAndCounter();
    installClickNav();
    document.addEventListener('keydown', handleKey);
    setMode(getInitialMode());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
