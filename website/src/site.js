const menuButton = document.querySelector('[data-menu-toggle]');
const mobileMenu = document.querySelector('#mobile-menu');
function closeMenu() {
  mobileMenu.hidden = true;
  menuButton.setAttribute('aria-expanded', 'false');
  menuButton.setAttribute('aria-label', 'Open navigation');
}
menuButton?.addEventListener('click', () => {
  const open = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  mobileMenu.hidden = !open;
});
mobileMenu?.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (menuButton?.getAttribute('aria-expanded') === 'true') { closeMenu(); menuButton.focus(); }
    document.querySelectorAll('.nav-dropdown[open]').forEach(details => { details.open = false; details.querySelector('summary').focus(); });
  }
});
document.addEventListener('click', event => {
  document.querySelectorAll('.nav-dropdown[open]').forEach(details => {
    if (!details.contains(event.target)) details.open = false;
  });
});
matchMedia('(min-width: 801px)').addEventListener('change', event => { if (event.matches) closeMenu(); });

document.querySelectorAll('[data-gallery]').forEach(gallery => {
  const tabs = [...gallery.querySelectorAll('[role="tab"]')];
  function select(tab) {
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute('aria-selected', String(active));
      item.tabIndex = active ? 0 : -1;
      gallery.querySelector('#' + item.getAttribute('aria-controls')).hidden = !active;
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); select(tabs[next]); tabs[next].focus(); }
    });
  });
});

document.querySelectorAll('[data-theme]').forEach(button => {
  button.addEventListener('click', () => {
    const theme = button.dataset.theme;
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme]').forEach(item => item.setAttribute('aria-pressed', String(item.dataset.theme === theme)));
    try { localStorage.setItem('wixal-site-theme', theme); } catch { /* Appearance still works without storage. */ }
  });
});
try {
  const saved = localStorage.getItem('wixal-site-theme');
  if (saved === 'dark' || saved === 'light') document.querySelector(`[data-theme="${saved}"]`)?.click();
} catch { /* Use the reference's light palette by default. */ }
