const test = require('node:test');
const assert = require('node:assert/strict');
const activity = require('../ui/activity.js');
const call = (name, args = {}) => ({ role: 'assistant', content: '', tool_calls: [{ function: { name, arguments: args } }] });
const result = (name, data) => ({ role: 'tool', tool_name: name, content: JSON.stringify(data) });
test('command polling becomes one step without losing chunks or raw results', () => {
  const [turn] = activity.turns([
    { role: 'user', content: 'Inspect' },
    call('command_start', { command: 'printf proof' }), result('command_start', { session_id: 'one', state: 'running', command: 'printf proof' }),
    call('command_read'), result('command_read', { session_id: 'one', state: 'running', offset: 0, output: 'proof' }),
    call('command_read'), result('command_read', { session_id: 'one', state: 'completed', exitCode: 0, offset: 5, output: '' }),
  ]);
  assert.equal(turn.actions.length, 1); assert.equal(turn.calls, 3);
  assert.equal(turn.actions[0].results.length, 3); assert.equal(turn.actions[0].status, 'Completed');
  assert.equal(activity.evidence(turn.actions[0]).output, 'proof');
  assert.equal(activity.evidence(turn.actions[0]).command, 'printf proof');
});
test('different requests never share command steps, and old result-only histories work', () => {
  const turns = activity.turns([{ role: 'user', content: 'First' }, result('command_read', { session_id: 'one', state: 'completed', exitCode: 0, output: 'first' }), { role: 'user', content: 'Second' }, result('command_read', { session_id: 'one', state: 'failed', exitCode: 2, output: 'second' })]);
  assert.equal(turns.length, 2); assert.equal(turns[0].actions[0].status, 'Completed');
  assert.equal(turns[1].actions[0].status, 'Failed');
  assert.equal(activity.evidence(turns[0].actions[0]).output, 'first');
});
test('parallel same-name calls pair with their own results and retain pending work', () => {
  const [turn] = activity.turns([{ role: 'user', content: 'Read' }, { role: 'assistant', content: 'I will inspect both files.', tool_calls: [{ function: { name: 'read_file', arguments: { path: 'a.md' } } }, { function: { name: 'read_file', arguments: { path: 'b.md' } } }] }, { role: 'tool', tool_name: 'read_file', content: 'A' }]);
  assert.equal(turn.updates.length, 1); assert.equal(turn.actions[1].status, 'Pending');
  assert.equal(activity.title(turn.actions[0]), 'Read a.md');
  assert.equal(activity.evidence(turn.actions[0]).output, 'A');
});
test('overlapping command reads do not repeat stdout and stdin does not finish a process', () => {
  const [turn] = activity.turns([{ role: 'user', content: 'Observe' }, result('command_read', { session_id: 'one', state: 'running', offset: 0, output: 'first' }), result('command_read', { session_id: 'one', state: 'running', offset: 0, output: 'firstsecond' }), result('command_write', { session_id: 'one', inputSent: true })]);
  assert.equal(turn.actions[0].status, 'Running');
  assert.equal(activity.evidence(turn.actions[0]).output, 'firstsecond');
  assert.equal(activity.evidence(turn.actions[0]).meta, 'Running');
});
