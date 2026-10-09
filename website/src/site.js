function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelectorAll('button[data-theme]').forEach(item => item.setAttribute('aria-pressed', String(item.dataset.theme === theme)));
  document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#191b19' : '#f4f3ef';
}
applyTheme(document.documentElement.dataset.theme || 'light');
document.querySelectorAll('button[data-theme]').forEach(button => {
  button.addEventListener('click', () => {
    applyTheme(button.dataset.theme);
    try { localStorage.setItem('wixal-site-theme', button.dataset.theme); } catch { /* Theme still works without storage. */ }
  });
});
window.addEventListener('storage', event => {
  if (event.key === 'wixal-site-theme') applyTheme(event.newValue === 'dark' ? 'dark' : 'light');
});
const previewDialog = document.querySelector('.preview-dialog');
let previewTrigger;
document.querySelectorAll('[data-preview]').forEach(button => {
  button.addEventListener('click', () => {
    const source = button.closest('figure').querySelector('img');
    const image = previewDialog.querySelector('img');
    image.src = source.src;
    image.alt = source.alt;
    previewDialog.querySelector('.preview-description').textContent = source.alt;
    previewTrigger = button;
    previewDialog.showModal();
  });
});
previewDialog?.querySelector('[data-preview-close]').addEventListener('click', () => previewDialog.close());
previewDialog?.addEventListener('click', event => { if (event.target === previewDialog) previewDialog.close(); });
previewDialog?.addEventListener('close', () => previewTrigger?.focus());

// Keep the demo moving while visible, with an explicit pause and motion preference.
document.querySelectorAll('video[data-demo]').forEach(video => {
  const button = video.closest('figure').querySelector('[data-demo-playback]');
  if (!button) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let visible = !('IntersectionObserver' in window);
  let userPaused = false;
  let manualPlay = false;
  video.controls = false;
  video.muted = true;
  video.loop = true;
  button.hidden = false;
  function syncButton() {
    const label = video.paused ? 'Play' : 'Pause';
    button.textContent = label;
    button.setAttribute('aria-label', `${label} demo`);
  }
  function updatePlayback() {
    const shouldPlay = !document.hidden && visible && !userPaused && (!reducedMotion.matches || manualPlay);
    video.autoplay = shouldPlay;
    if (shouldPlay) {
      if (video.paused) video.play().catch(syncButton);
    } else {
      video.pause();
    }
    syncButton();
  }
  button.addEventListener('click', () => {
    if (video.paused) {
      userPaused = false;
      manualPlay = true;
    } else {
      userPaused = true;
      manualPlay = false;
    }
    updatePlayback();
  });
  video.addEventListener('play', syncButton);
  video.addEventListener('pause', syncButton);
  reducedMotion.addEventListener('change', () => {
    manualPlay = false;
    updatePlayback();
  });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      updatePlayback();
    });
    observer.observe(video);
  }
  document.addEventListener('visibilitychange', updatePlayback);
  updatePlayback();
});
