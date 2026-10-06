const format = count => count.toLocaleString();
const downloadElements = [...document.querySelectorAll('[data-download-total]')];
const usersElements = [...document.querySelectorAll('[data-active-users-total]')];
async function downloads() {
  try {
    let total = 0;
    for (let page = 1; ; page++) {
      const response = await fetch(`https://api.github.com/repos/TheJhyeFactor/Wixal/releases?per_page=100&page=${page}`, { signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error('GitHub unavailable');
      const batch = await response.json();
      for (const release of batch.filter(item => !item.draft)) for (const asset of release.assets) if (/\.(dmg|zip)$/i.test(asset.name)) total += asset.download_count;
      if (batch.length < 100) break;
    }
    downloadElements.forEach(el => { el.textContent = format(total); });
  } catch { downloadElements.forEach(el => { el.textContent = 'Unavailable'; }); }
}
async function users() {
  try {
    const response = await fetch('https://raw.githubusercontent.com/TheJhyeFactor/Wixal/wixal-metrics/website-users.json', { signal: AbortSignal.timeout(15000), cache: 'no-cache' });
    if (!response.ok) throw new Error('Not connected');
    const data = await response.json();
    if (data.status !== 'available' || data.period_days !== 30 || !Number.isSafeInteger(data.active_users) || data.active_users < 0 || !Number.isFinite(Date.parse(data.updated_at))) throw new Error('Invalid data');
    if (Date.now() - Date.parse(data.updated_at) > 48 * 60 * 60 * 1000 || Date.parse(data.updated_at) - Date.now() > 5 * 60 * 1000) throw new Error('Outdated snapshot');
    usersElements.forEach(el => { el.textContent = format(data.active_users); });
  } catch {
    usersElements.forEach(el => { el.textContent = 'Not available'; });
  }
}
await Promise.allSettled([document.querySelector('[data-stats-rows]') ? Promise.resolve() : downloads(), users()]);
