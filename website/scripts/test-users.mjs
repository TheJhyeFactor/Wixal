import assert from 'node:assert/strict';
import { parseCount } from './collect-users.mjs';
assert.equal(parseCount({ rows: [{ metricValues: [{ value: '12' }] }] }), 12);
assert.equal(parseCount({ rowCount: 0 }), 0);
assert.equal(parseCount({ metricHeaders: [{ name: 'activeUsers', type: 'TYPE_INTEGER' }], metadata: { timeZone: 'Australia/Sydney' } }), 0);
for (const report of [{}, { rows: [{ metricValues: [{ value: '-1' }] }] }, { rows: [{ metricValues: [{ value: '9007199254740992' }] }] }, { rowCount: 0, metadata: { subjectToThresholding: true } }, { rowCount: 0, metadata: { dataLossFromOtherRow: true } }]) assert.throws(() => parseCount(report));
console.log('Active user report validation passed');
