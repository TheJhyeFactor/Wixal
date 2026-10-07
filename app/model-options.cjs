// Follow the controls reported by the engine instead of assuming think is boolean.
function thinkingOptions(info = {}) {
  if (!info.capabilities?.includes('thinking')) return {};
  const values = info.thinking?.values;
  if (values?.includes(false)) return { think: false };
  if (values?.includes('low')) return { think: 'low' };
  if (values?.length) return { think: info.thinking.default ?? values[0] };
  return { think: info.details?.family === 'gptoss' ? 'low' : false };
}
function selectionContext(model, requested = 8192) {
  // A model switch starts with a practical window. Larger windows are an explicit advanced choice.
  return Math.min(16384, require('./memory.cjs').safeContext(model, requested));
}
module.exports = { thinkingOptions, selectionContext };
