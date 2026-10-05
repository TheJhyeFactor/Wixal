const os = require('node:os');
const { createHash } = require('node:crypto');
const { streamChat } = require('./agent.cjs');
const { localEndpoint } = require('./models.cjs');
let deviceIdentity;
function hardware() {
  if (!deviceIdentity) {
    const cpus = os.cpus(), cpu = cpus[0]?.model || 'Unknown CPU', totalMemory = os.totalmem(), arch = os.arch();
    deviceIdentity = { cpu, arch, cores: cpus.length, totalMemory, memoryBudget: Math.floor(totalMemory * .75), id: createHash('sha256').update(`${cpu}:${arch}:${totalMemory}`).digest('hex').slice(0, 16) };
  }
  return { ...deviceIdentity, freeMemory: os.freemem() };
}
function estimate(model, device, contextSize, cacheBytes = 2) {
  const context = Math.min(contextSize, model.contextLength || contextSize);
  const required = Math.ceil((model.size || 0) * 1.15 + context * (model.kvBytesPerToken ? model.kvBytesPerToken * cacheBytes : 128 * 1024) + 1024 ** 3);
  return { required, context, fits: model.size > 0 && required <= device.memoryBudget, estimated: true };
}
async function benchmark(model, contextSize, signal, emit, fetcher = fetch) {
  const context = Math.min(contextSize, model.contextLength || contextSize), samples = [];
  for (let sample = 0; sample < 2; sample++) {
    emit({ phase: sample ? 'Warm run · measuring generation speed' : 'First run · loading and generating', sample: sample + 1, tokens: 0 });
    let received = 0;
    const result = await streamChat({ model: model.name, stream: true, think: false,
      messages: [{ role: 'user', content: 'Count upwards from 1 to 200. Write each number and its English word on a separate line. Continue until you reach 200.' }],
      options: { num_ctx: context, num_predict: 128, temperature: 0, seed: 42 } }, signal,
      () => { emit({ phase: sample ? 'Warm run' : 'First run', sample: sample + 1, chunks: ++received }); }, fetcher);
    if (!result.metrics?.tokens || !result.metrics.tokensPerSecond) throw new Error('The engine reported no generated tokens; this run cannot be scored.');
    samples.push(result.metrics);
  }
  let loaded, engineVersion = 'unknown';
  try { const response = await fetcher(`${await localEndpoint()}/api/version`, { signal }); if (response.ok) engineVersion = (await response.json()).version || 'unknown'; } catch { if (signal.aborted) throw new Error('Benchmark stopped.'); }
  try { const response = await fetcher(`${await localEndpoint()}/api/ps`, { signal }); if (response.ok) loaded = (await response.json()).models?.find(m => m.name === model.name || m.model === model.name); } catch { if (signal.aborted) throw new Error('Benchmark stopped.'); }
  return { name: model.name, digest: model.digest, context, created: Date.now(), status: 'completed', engineVersion, samples,
    tokensPerSecond: samples[1].tokensPerSecond, timeToFirstToken: samples[0].timeToFirstToken,
    loadedBytes: loaded?.size || null, gpuBytes: loaded?.size_vram || null,
    totalTokens: samples.reduce((sum, s) => sum + s.tokens, 0) };
}
module.exports = { hardware, estimate, benchmark };
