/* Prism Phase3 GUI enhancements (no dependencies) */

function bySel(root, selector) {
  return root.querySelector(selector);
}

function bySelAll(root, selector) {
  return Array.from(root.querySelectorAll(selector));
}

function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function initTimelineReplay() {
  const timeline = document.querySelector('[data-timeline]');
  if (!timeline) return;

  const events = bySelAll(timeline, 'details.event');
  if (events.length === 0) return;

  for (let i = 0; i < events.length; i += 1) {
    events[i].style.setProperty('--i', String(i));
  }

  const playBtn = document.querySelector('[data-timeline-play]');
  const pauseBtn = document.querySelector('[data-timeline-pause]');
  const speedInput = document.querySelector('[data-timeline-speed]');
  const progressBar = document.querySelector('[data-timeline-progress]');

  const reduced = prefersReducedMotion();

  let timer = null;
  let playing = false;
  let index = 0;

  const setProgress = (i) => {
    if (!progressBar) return;
    const pct = Math.max(0, Math.min(1, (i + 1) / events.length)) * 100;
    progressBar.style.width = `${pct}%`;
  };

  const setActive = (i) => {
    for (const ev of events) ev.classList.remove('is-active');
    const target = events[i];
    if (!target) return;
    target.classList.add('is-active');
    target.open = true;
    target.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'center' });
    setProgress(i);
  };

  const nextDelayMs = () => {
    const speed = speedInput ? Number(speedInput.value || 1) : 1;
    const s = Number.isFinite(speed) && speed > 0 ? speed : 1;
    return Math.floor(800 / s);
  };

  function stop() {
    playing = false;
    if (playBtn) playBtn.disabled = false;
    if (pauseBtn) pauseBtn.disabled = true;
    if (timer) window.clearTimeout(timer);
    timer = null;
  }

  const scheduleNext = () => {
    if (!playing) return;
    timer = window.setTimeout(() => {
      setActive(index);
      index += 1;
      if (index >= events.length) {
        stop();
        return;
      }
      scheduleNext();
    }, nextDelayMs());
  };

  const play = () => {
    if (playing) return;
    playing = true;
    if (playBtn) playBtn.disabled = true;
    if (pauseBtn) pauseBtn.disabled = false;
    scheduleNext();
  };

  // Allow user to click an event summary to set replay cursor.
  for (let i = 0; i < events.length; i += 1) {
    const summary = bySel(events[i], 'summary');
    if (!summary) continue;
    summary.addEventListener('click', () => {
      index = i;
      setProgress(i);
      for (const ev of events) ev.classList.remove('is-active');
      events[i].classList.add('is-active');
    });
  }

  if (playBtn) playBtn.addEventListener('click', play);
  if (pauseBtn) pauseBtn.addEventListener('click', stop);
  if (speedInput)
    speedInput.addEventListener('input', () => {
      if (!playing) return;
      if (timer) window.clearTimeout(timer);
      scheduleNext();
    });

  // Intersection animation (skip if reduced motion).
  if (!reduced && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) entry.target.classList.add('is-in');
        }
      },
      { rootMargin: '60px 0px', threshold: 0.1 },
    );
    for (const ev of events) io.observe(ev);
  } else {
    for (const ev of events) ev.classList.add('is-in');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initTimelineReplay();
});
