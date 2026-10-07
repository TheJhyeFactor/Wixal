const fs = require('node:fs/promises'), path = require('node:path');
const { assessWebsite, markdownReport } = require('../app/website-assessment.cjs');
(async () => {
 const options = Object.fromEntries(process.argv.slice(2).map((v,i,a) => v.startsWith('--') ? [v.slice(2), a[i+1]] : []).filter(p => p.length));
 if (!options.url || !options.out) throw new Error('Usage: node scripts/website-assess.cjs --url https://authorised.example/ --out /path/report [--profile baseline|probes] [--protected /api/session,/api/admin]');
 const report = await assessWebsite({ url: options.url, profile: options.profile || 'baseline', max_pages: Number(options.pages || 8), protected_paths: options.protected?.split(',') || [] }, { onCase: c => console.log(c.status + ' ' + c.id + ' ' + c.target) });
 await fs.mkdir(path.dirname(options.out), { recursive: true }); await fs.writeFile(options.out+'.json', JSON.stringify(report,null,2)+'\n', {mode:0o600}); await fs.writeFile(options.out+'.md', markdownReport(report)); console.log(JSON.stringify(report.summary));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
