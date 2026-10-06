import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
export function parseCount(report) {
  if (report.metadata?.subjectToThresholding || report.metadata?.dataLossFromOtherRow) throw new Error('Report is thresholded or incomplete');
  const value = report.rows?.[0]?.metricValues?.[0]?.value ?? (report.rowCount === 0 ? '0' : undefined);
  if (!/^\d+$/.test(value ?? '')) throw new Error('Analytics returned no valid active-user total');
  const count = Number(value);
  if (!Number.isSafeInteger(count)) throw new Error('Invalid active-user count');
  return count;
}
export async function collect() {
  const property = process.env.GA_PROPERTY_ID || '557599207';
  if (!/^\d+$/.test(property)) throw new Error('Invalid property ID');
  const accessToken = process.env.GA_ACCESS_TOKEN;
  if (!accessToken) throw new Error('GA_ACCESS_TOKEN is required');
  const response = await fetch(`https://analyticsdata.googleapis.com/v1beta/properties/${property}:runReport`, { method: 'POST', headers: { Authorization: 'Bearer ' + accessToken, 'Content-Type': 'application/json' }, body: JSON.stringify({ metrics: [{ name: 'activeUsers' }], dateRanges: [{ startDate: '29daysAgo', endDate: 'today' }] }), signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`Analytics report unavailable (${response.status}); previous snapshot retained`);
  const report = await response.json();
  const snapshot = { active_users: parseCount(report), period_days: 30, includes_today: true, updated_at: new Date().toISOString(), timezone: report.metadata?.timeZone || 'Australia/Sydney', source: 'Google Analytics 4', status: 'available' };
  const dir = resolve(process.env.USERS_DIR || 'artifacts/website-users');
  await mkdir(dir, { recursive: true });
  await writeFile(resolve(dir, 'website-users.json'), JSON.stringify(snapshot, null, 2) + '\n');
  console.log(`Published aggregate: ${snapshot.active_users} active website users over 30 days.`);
}
if (process.argv[1] && resolve(process.argv[1]) === import.meta.filename) await collect();
