import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
const repo = process.env.GITHUB_REPOSITORY || 'TheJhyeFactor/Wixal';
if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) throw new Error('Invalid repository');
const out = resolve(process.env.METRICS_DIR || 'artifacts/github-metrics');
const useCli = process.argv.includes('--local');
async function api(path, optional = false) {
  if (useCli) {
    try { return JSON.parse(execFileSync('gh', ['api', `repos/${repo}/${path}`], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })); }
    catch (error) { if (optional && /HTTP (403|404)/.test(String(error.stderr))) return null; throw new Error(`GitHub request failed: ${path}`); }
  }
  const response = await fetch(`https://api.github.com/repos/${repo}/${path}`, { signal: AbortSignal.timeout(30000), headers: { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', ...(process.env.GH_TOKEN ? { Authorization: `Bearer ${process.env.GH_TOKEN}` } : {}) } });
  if (optional && [403, 404].includes(response.status)) return null;
  if (!response.ok) throw new Error(`GitHub ${path}: HTTP ${response.status}`);
  return response.json();
}
const releases = [];
for (let page = 1; ; page++) {
  const batch = await api(`releases?per_page=100&page=${page}`);
  releases.push(...batch.filter(release => !release.draft));
  if (batch.length < 100) break;
}
const assets = releases.flatMap(release => release.assets.filter(asset => /\.(dmg|zip)$/i.test(asset.name)).map(asset => ({ release: release.tag_name, prerelease: release.prerelease, asset_id: asset.id, file: asset.name, downloads: asset.download_count })));
const [views, clones] = await Promise.all([api('traffic/views?per=day', true), api('traffic/clones?per=day', true)]);
const snapshot = { collected_at: new Date().toISOString(), repository: repo, total_release_file_downloads: assets.reduce((sum, asset) => sum + asset.downloads, 0), assets, traffic: { views, clones, status: views && clones ? 'available' : 'unavailable: configure METRICS_TRAFFIC_TOKEN with repository Administration read access' } };
const md = value => String(value).replaceAll('|', '\\|').replace(/[\r\n]/g, ' ');
const report = `# Wixal GitHub metrics\n\nCollected ${snapshot.collected_at}.\n\n**Release file downloads: ${snapshot.total_release_file_downloads}**\n\nDMG and ZIP only. Includes repeated and direct downloads; does not measure unique users, installations, or active app users.\n\n| Release | File | Downloads |\n| --- | --- | ---: |\n${assets.map(a => `| ${md(a.release)} | ${md(a.file)} | ${a.downloads} |`).join('\n')}\n\n## Repository traffic (last 14 days)\n\n${views ? `Views: ${views.count}; unique visitors in this window: ${views.uniques}.` : 'Views unavailable: the workflow needs METRICS_TRAFFIC_TOKEN with Administration read permission.'}\n\n${clones ? `Clones: ${clones.count}; unique cloners in this window: ${clones.uniques}.` : 'Clones unavailable: the workflow needs METRICS_TRAFFIC_TOKEN with Administration read permission.'}\n\nRepository traffic is separate from GitHub Pages website traffic. Do not add overlapping 14-day totals or daily unique counts to claim all-time unique users. Google Analytics holds website visitor and file_download click reports.\n`;
await mkdir(out, { recursive: true });
await writeFile(resolve(out, 'latest.json'), JSON.stringify(snapshot, null, 2) + '\n');
await writeFile(resolve(out, 'README.md'), report);
if (process.env.GITHUB_STEP_SUMMARY) await writeFile(process.env.GITHUB_STEP_SUMMARY, report, { flag: 'a' });
console.log(`Saved report: ${out}; ${snapshot.total_release_file_downloads} release file downloads; traffic ${snapshot.traffic.status}.`);
