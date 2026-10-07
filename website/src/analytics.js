const id = document.querySelector('meta[name="ga-measurement-id"]')?.content;
const key = 'wixal-site-analytics-v1';
const panel = document.querySelector('[data-analytics-choice]');
let choice;
try { choice = localStorage.getItem(key); } catch { /* Choice applies for this page. */ }
let loaded = false;
let active = false;
const cleanReferrer = () => { try { const url = new URL(document.referrer); return url.origin + url.pathname; } catch { return ''; } };
function start() {
  if (['localhost', '127.0.0.1'].includes(location.hostname)) return;
  if (!/^G-[A-Z0-9]+$/.test(id || '') || active) return;
  window['ga-disable-' + id] = false;
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
  if (!loaded) {
    window.gtag('consent', 'default', { analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
    window.gtag('js', new Date());
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + id;
    document.head.append(script);
    loaded = true;
  }
  window.gtag('consent', 'update', { analytics_storage: 'granted' });
  window.gtag('config', id, { send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false, cookie_prefix: 'wixal', cookie_domain: location.hostname, cookie_path: '/Wixal/', page_location: location.origin + location.pathname, page_referrer: cleanReferrer() });
  window.gtag('event', 'page_view', { page_location: location.origin + location.pathname, page_referrer: cleanReferrer(), page_title: document.title });
  active = true;
}
function stop() {
  active = false;
  window['ga-disable-' + id] = true;
  window.gtag?.('consent', 'update', { analytics_storage: 'denied' });
  // Remove this integration's cookies; never remove cookies belonging to other GitHub Pages sites.
  for (const cookie of document.cookie.split(';')) {
    const name = cookie.trim().split('=')[0];
    if (name !== 'wixal_ga' && name !== 'wixal_ga_' + id?.slice(2).replaceAll('-', '_')) continue;
    for (const domain of ['', ';domain=' + location.hostname, ';domain=.' + location.hostname]) {
      document.cookie = name + '=;max-age=0;path=/Wixal/' + domain + ';SameSite=Lax';
    }
  }
}
function save(value) {
  choice = value;
  try { localStorage.setItem(key, value); } catch { /* Storage optional. */ }
  if (value === 'allow') start(); else stop();
  panel.hidden = true;
}
document.querySelector('[data-analytics-allow]')?.addEventListener('click', () => save('allow'));
document.querySelector('[data-analytics-deny]')?.addEventListener('click', () => save('deny'));
document.querySelector('[data-analytics-close]')?.addEventListener('click', () => { panel.hidden = true; });
document.querySelectorAll('[data-privacy-settings]').forEach(button => button.addEventListener('click', () => {
  panel.hidden = false;
  panel.querySelector('[data-analytics-close]').hidden = !choice;
  panel.querySelector('[data-analytics-deny]').focus();
}));
if (choice === 'allow') start();
else if (choice !== 'deny' && panel) panel.hidden = false;
window.addEventListener('storage', event => {
  if (event.key === key) {
    choice = event.newValue;
    if (choice === 'allow') start(); else stop();
    panel.hidden = choice === 'allow' || choice === 'deny';
  }
});
document.addEventListener('click', event => {
  if (!active) return;
  const anchor = event.target.closest?.('a[href]');
  if (!anchor) return;
  const url = new URL(anchor.href);
  const match = url.pathname.match(/^\/TheJhyeFactor\/Wixal\/releases\/download\/([^/]+)\/([^/]+\.(dmg|zip))$/i);
  if (url.hostname !== 'github.com' || !match) return;
  window.gtag('event', 'file_download', { file_name: match[2], file_extension: match[3].toLowerCase(), release_version: match[1], link_url: url.origin + url.pathname, page_location: location.origin + location.pathname, transport_type: 'beacon' });
});
