const status = document.querySelector('[data-stats-status]');
const repo = 'TheJhyeFactor/Wixal';
try {
  const releases = [];
  for (let page = 1; ; page++) {
    const response = await fetch(`https://api.github.com/repos/${repo}/releases?per_page=100&page=${page}`, { signal: AbortSignal.timeout(15000), headers: { Accept: 'application/vnd.github+json' } });
    if (!response.ok) throw new Error('GitHub unavailable');
    const batch = await response.json();
    releases.push(...batch.filter(item => !item.draft));
    if (batch.length < 100) break;
  }
  const rows = releases.map(release => {
    const count = ext => release.assets.filter(asset => asset.name.toLowerCase().endsWith('.' + ext)).reduce((sum, asset) => sum + asset.download_count, 0);
    return { release, dmg: count('dmg'), zip: count('zip') };
  });
  document.querySelectorAll('[data-download-total]').forEach(el => { el.textContent = rows.reduce((sum, row) => sum + row.dmg + row.zip, 0).toLocaleString(); });
  const latest = rows.find(row => row.release.tag_name === 'v0.7.10-alpha.1');
  document.querySelector('[data-stats-latest]').textContent = latest ? `${latest.release.tag_name}: ${(latest.dmg + latest.zip).toLocaleString()}` : 'No releases';
  const tbody = document.querySelector('[data-stats-rows]');
  for (const row of rows) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    const a = document.createElement('a');
    a.href = `https://github.com/${repo}/releases/tag/${encodeURIComponent(row.release.tag_name)}`;
    a.textContent = row.release.tag_name + (row.release.prerelease ? ' (prerelease)' : '');
    td.append(a); tr.append(td);
    for (const value of [row.dmg, row.zip, row.dmg + row.zip]) { const cell = document.createElement('td'); cell.textContent = value.toLocaleString(); tr.append(cell); }
    tbody.append(tr);
  }
  status.textContent = 'Retrieved from GitHub ' + new Date().toLocaleString() + '.';
} catch {
  document.querySelectorAll('[data-download-total]').forEach(el => { el.textContent = 'Unavailable'; });
  status.textContent = 'GitHub counts are temporarily unavailable. Use the release links below or try again later.';
}
