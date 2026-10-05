const { randomUUID } = require('node:crypto');
const { performance } = require('node:perf_hooks');
const { pullModel, validateModelName } = require('./models.cjs');
// Serial downloads keep one owner for the active library and avoid network/disk contention.
class ModelDownloads {
  constructor({ store, emit, pull = pullModel, verify = async () => {}, complete = () => {} }) {
    Object.assign(this, { store, emit, pull, verify, complete });
    this.items = (store.data.modelDownloads || []).slice(-30).map(item => ['downloading', 'queued'].includes(item.state) ? { ...item, state: 'paused', status: 'Interrupted by restart. Resume when ready.', rate: 0, eta: null } : item);
    this.active = null; this.closed = false; this.save();
  }
  snapshot() { return this.items.map(item => ({ ...item })); }
  save() { this.store.data.modelDownloads = this.snapshot(); this.store.save(); }
  publish() { this.emit({ type: 'model-downloads', items: this.snapshot(), active: this.active?.item.id || null }); }
  enqueue(name, mode) {
    validateModelName(name);
    if (this.items.some(item => item.name === name && item.mode === mode && ['queued', 'downloading'].includes(item.state))) throw new Error('This model is already in the download queue.');
    if (this.items.filter(item => ['queued', 'downloading', 'paused', 'failed'].includes(item.state)).length >= 12) throw new Error('Finish or remove a download before adding more.');
    const item = { id: randomUUID(), name, mode, state: 'queued', status: 'Queued', completed: 0, total: 0, rate: 0, eta: null, created: Date.now() };
    this.items = this.items.filter(item => !['completed', 'cancelled'].includes(item.state)).concat(this.items.filter(item => ['completed', 'cancelled'].includes(item.state)).slice(-17)).concat(item);
    this.save(); this.publish(); this.pump(); return item;
  }
  action(id, action, mode) {
    const item = this.items.find(item => item.id === id); if (!item) throw new Error('Unknown download.');
    if (action === 'resume' || action === 'retry') {
      if (!['paused', 'failed', 'cancelled'].includes(item.state)) throw new Error('This download cannot be resumed.');
      if (this.items.some(other => other !== item && other.name === item.name && other.mode === item.mode && ['queued', 'downloading'].includes(other.state))) throw new Error('This model is already in the download queue.');
      if (item.mode !== mode) throw new Error('Switch back to the original local engine to resume this download.');
      item.state = 'queued'; item.status = 'Queued to resume'; item.error = ''; item.rate = 0; item.eta = null;
    } else if (action === 'pause' || action === 'cancel') {
      if (!['queued', 'downloading', 'paused', 'failed'].includes(item.state)) throw new Error('This download is already finished.');
      item.state = action === 'pause' ? 'paused' : 'cancelled'; item.status = action === 'pause' ? 'Paused · resume to continue' : 'Cancelled'; item.rate = 0; item.eta = null;
      if (this.active?.item === item) this.active.controller.abort();
    } else if (action === 'remove') {
      if (['downloading', 'queued'].includes(item.state)) throw new Error('Cancel the download first.');
      this.items = this.items.filter(row => row !== item);
    } else throw new Error('Unknown download action.');
    this.save(); this.publish(); this.pump();
  }
  get busy() { return !!this.active || this.items.some(item => item.state === 'queued'); }
  async pump() {
    if (this.active || this.closed) return;
    const item = this.items.find(item => item.state === 'queued'); if (!item) return;
    const controller = new AbortController(); this.active = { item, controller };
    item.state = 'downloading'; item.status = 'Starting download'; item.rate = 0; item.eta = null; this.save(); this.publish();
    const layers = new Map(); let lastEmit = -Infinity, lastBytes = null, lastRate = performance.now();
    try {
      await this.pull(item.name, controller.signal, progress => {
        if (controller.signal.aborted) return;
        const now = performance.now();
        if (progress.digest && progress.total) layers.set(progress.digest, { total: progress.total, completed: Math.min(progress.total, progress.completed) });
        const entries = [...layers.values()];
        item.total = entries.length ? entries.reduce((sum, layer) => sum + layer.total, 0) : progress.total || item.total;
        item.completed = entries.length ? entries.reduce((sum, layer) => sum + layer.completed, 0) : progress.completed || item.completed;
        item.status = progress.status;
        if (lastBytes === null) { lastBytes = item.completed; lastRate = now; }
        if (now - lastRate >= 500) { item.rate = Math.max(0, (item.completed - lastBytes) * 1000 / (now - lastRate)); lastBytes = item.completed; lastRate = now; }
        item.eta = item.rate > 0 && item.total > item.completed ? Math.ceil((item.total - item.completed) / item.rate) : null;
        if (now - lastEmit >= 200 || progress.status !== this.lastStatus) { lastEmit = now; this.lastStatus = progress.status; this.publish(); }
      });
      if (controller.signal.aborted) return;
      item.status = 'Verifying installation'; this.publish();
      await this.verify(item.name);
      if (controller.signal.aborted) return;
      item.state = 'completed'; item.status = 'Installed'; item.completed = item.total; item.finished = Date.now();
      this.complete(item.name);
    } catch (error) {
      if (!controller.signal.aborted) { item.state = 'failed'; item.status = 'Download failed'; item.error = String(error.message).slice(0, 800); }
    } finally {
      item.rate = 0; item.eta = null; this.active = null; this.save(); this.publish(); this.pump();
    }
  }
  shutdown() {
    this.closed = true;
    for (const item of this.items) if (['queued', 'downloading'].includes(item.state)) { item.state = 'paused'; item.status = 'Paused when Wixal closed'; }
    this.active?.controller.abort(); this.save();
  }
}
module.exports = { ModelDownloads };
