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

// Demos start only from their native controls, including with reduced motion.
document.querySelectorAll('video[data-demo]').forEach(video => {
  let visible = true;
  let resume = false;
  function updatePlayback() {
    if (document.hidden || !visible) {
      if (!video.paused) {
        resume = true;
        video.pause();
      }
    } else if (resume) {
      resume = false;
      video.play().catch(() => {});
    }
  }
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      updatePlayback();
    });
    observer.observe(video);
  }
  document.addEventListener('visibilitychange', updatePlayback);
});
