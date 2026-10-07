const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');
(async () => {
  const root = path.resolve(__dirname, '..'), temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-sidebar-'));
  const store = new Store(path.join(temp, 'data'));
  for (const name of ['Wixal', 'Client portal']) { const folder = path.join(temp, name); await fs.mkdir(folder); const p = store.addProject(folder); store.session().title = `${name} first chat`; store.remember(`${name} only memory`); const s = store.newSession(); s.title = `${name} second chat`; }
  const a = store.data.projects[0], b = store.data.projects[1]; store.selectProject(null); store.session().title = 'Personal thought'; store.selectProject(a.id);
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: path.join(temp, 'data') }; delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.locator('.session-item').first().waitFor();
    const group = id => page.locator(`[data-project-group="${id}"]`);
    assert.equal(await group(a.id).locator('.session-item').count(), 2);
    await page.click(`[data-project-expand="${b.id}"]`);
    assert.equal(await group(b.id).locator('.session-item').count(), 2);
    await group(b.id).locator('.session-item').filter({ hasText: 'first chat' }).click();
    await page.waitForFunction(id => state.activeProject === id, b.id);
    assert.equal(await page.locator('#conversation-label').textContent(), 'Client portal first chat');
    await page.click(`[data-project-memory="${a.id}"]`); await page.locator('#memory-drawer').waitFor();
    assert.match(await page.locator('#memories').textContent(), /Wixal only memory/);
    assert.doesNotMatch(await page.locator('#memories').textContent(), /Client portal/);
    await page.fill('#memory-input', 'Use scoped project decisions'); await page.locator('#memory-form button').click();
    await page.waitForFunction(() => state.memories.some(m => m.content === 'Use scoped project decisions'));
    assert.equal(await group(a.id).locator('.memory-total').textContent(), '2');
    await page.click('#close-memory');
    await page.click(`[data-project-new="${b.id}"]`);
    await page.waitForFunction(id => state.activeProject === id && session().title === 'New conversation', b.id);
    assert.equal(await group(b.id).locator('.session-item').count(), 3);
    await page.click('[data-project-select="personal"]');
    await page.locator('.session-item').filter({ hasText: 'Personal thought' }).click();
    assert.equal(await page.evaluate(() => state.activeProject), null);
    await page.fill('#session-search', 'Wixal first'); assert.equal(await page.locator('.session-item').count(), 1);
    await page.fill('#session-search', '');
    // The flow under test is expanded navigation -> collapse/reverse -> aligned, saved rail.
    // Browser plugin not available; the Electron app requires its real preload and IPC.
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.fill('#prompt', 'Keep this draft while the sidebar moves.');
    await page.locator('#session-search').focus();
    await page.evaluate(() => toggleSidebar(true));
    assert.equal(await page.locator('#sidebar-content').evaluate(el => el.inert), true);
    assert.equal(await page.locator('#sidebar-toggle').evaluate(el => el === document.activeElement), true);
    await page.waitForFunction(() => {
      const width = document.querySelector('#sidebar').getBoundingClientRect().width;
      return width > 63 && width < 250;
    });
    const midpoint = await page.locator('#sidebar').evaluate(el => ({ width: el.getBoundingClientRect().width, contentWidth: el.querySelector('.sidebar-content').getBoundingClientRect().width }));
    assert.ok(midpoint.width > 62 && midpoint.width < 260);
    assert.equal(midpoint.contentWidth, 236, 'Navigation retains its width during collapse');
    await page.waitForFunction(() => Math.abs(document.querySelector('#sidebar').getBoundingClientRect().width - 62) < .1);
    assert.equal(await page.locator('#sidebar-wordmark').evaluate(el => getComputedStyle(el).visibility), 'hidden');
    assert.equal(await page.locator('#sidebar-content').evaluate(el => getComputedStyle(el).visibility), 'hidden');
    await page.evaluate(() => {
      window.sidebarOriginalInvoke = invoke; window.sidebarPending = 0; window.sidebarPeak = 0;
      invoke = async (name, ...args) => {
        if (name !== 'layout') return window.sidebarOriginalInvoke(name, ...args);
        window.sidebarPeak = Math.max(window.sidebarPeak, ++window.sidebarPending);
        try { await new Promise(resolve => setTimeout(resolve, 90)); return await window.sidebarOriginalInvoke(name, ...args); }
        finally { window.sidebarPending--; }
      };
    });
    await page.evaluate(async () => {
      toggleSidebar(false);
      await new Promise(resolve => setTimeout(resolve, 65));
      toggleSidebar(true);
      await new Promise(resolve => setTimeout(resolve, 40));
      await toggleSidebar(false);
    });
    await page.waitForFunction(() => document.querySelector('#sidebar').getBoundingClientRect().width === 260 && !state.ui.sidebarCollapsed);
    assert.equal(await page.evaluate(() => window.sidebarPeak), 1, 'Layout saves are serialized');
    await page.evaluate(() => { invoke = window.sidebarOriginalInvoke; });
    assert.equal(await page.locator('#sidebar-content').evaluate(el => el.inert), false);
    assert.equal(await page.locator('#prompt').inputValue(), 'Keep this draft while the sidebar moves.');
    await page.reload(); await page.locator('[data-project-select]').first().waitFor();
    assert.equal(await page.locator('#sidebar').evaluate(el => el.classList.contains('collapsed')), false);
    // The popover follows its anchor while geometry is moving; it never drifts above another row.
    await page.click('#workspace-menu-toggle');
    await page.waitForFunction(() => document.querySelector('#workspace-menu').getAnimations().every(animation => animation.playState !== 'running'));
    await page.evaluate(() => toggleSidebar(true));
    await page.waitForFunction(() => document.querySelector('#sidebar').getBoundingClientRect().width < 240);
    const anchored = await page.evaluate(() => {
      const menu = document.querySelector('#workspace-menu').getBoundingClientRect();
      const button = document.querySelector('#workspace-menu-toggle').getBoundingClientRect();
      return { left: menu.left, anchorLeft: Math.max(12, button.left), bottom: menu.bottom, anchorTop: button.top };
    });
    assert.ok(Math.abs(anchored.left - anchored.anchorLeft) < 2);
    assert.ok(Math.abs(anchored.bottom + 8 - anchored.anchorTop) < 2);
    await page.click('#workspace-menu-toggle');
    await page.waitForFunction(() => !document.querySelector('#workspace-menu').matches(':popover-open'));
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.evaluate(() => toggleSidebar(false));
    assert.equal(await page.locator('#sidebar').evaluate(el => el.getBoundingClientRect().width), 260);
    assert.equal(await page.locator('#sidebar').evaluate(el => getComputedStyle(el).transitionDuration), '0s');
    await page.evaluate(() => toggleSidebar(true));
    assert.equal(await page.locator('#sidebar').evaluate(el => el.getBoundingClientRect().width), 62);
    await page.evaluate(() => toggleSidebar(false));
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1360, 880));
    await page.screenshot({ path: path.join(root, 'artifacts/sidebar-projects.png'), animations: 'disabled' });
    await page.reload(); await page.locator('[data-project-select]').first().waitFor();
    await page.click(`[data-project-select="${a.id}"]`);
    await page.click(`[data-project-memory="${a.id}"]`);
    assert.match(await page.locator('#memories').textContent(), /Use scoped project decisions/);
    await page.click('#close-memory');
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640));
    const overflow = await page.locator('#sidebar').evaluate(el => el.scrollHeight - el.clientHeight); assert.ok(overflow <= 1, overflow);
    await page.screenshot({ path: path.join(root, 'artifacts/sidebar-compact.png'), animations: 'disabled' });
    for (const [width, height] of [[1360, 880], [920, 640]]) {
      await app.evaluate(({ BrowserWindow }, size) => BrowserWindow.getAllWindows()[0].setSize(...size), [width, height]);
      for (const collapsed of [false, true]) {
        await page.evaluate(value => toggleSidebar(value), collapsed);
        await page.emulateMedia({ reducedMotion: 'reduce' });
        const bounds = await page.evaluate(() => {
          const ids = ['models-page-button', 'settings-button', 'workspace-menu-toggle'];
          const sidebar = document.querySelector('#sidebar').getBoundingClientRect();
          return ids.map(id => {
            const el = document.getElementById(id), rect = el.getBoundingClientRect(), icon = el.querySelector('span').getBoundingClientRect();
            return { left: rect.left, right: rect.right, height: rect.height, top: rect.top, bottom: rect.bottom, iconX: icon.left + icon.width / 2, iconY: icon.top + icon.height / 2, centerX: rect.left + rect.width / 2, centerY: rect.top + rect.height / 2, sidebarLeft: sidebar.left, sidebarRight: sidebar.right };
          });
        });
        for (const rect of bounds) {
          assert.equal(rect.height, 40); assert.ok(rect.left >= rect.sidebarLeft && rect.right <= rect.sidebarRight);
          assert.ok(Math.abs(rect.iconY - rect.centerY) <= 1);
          assert.ok(Math.abs(rect.iconX - bounds[0].iconX) <= 1);
          if (collapsed) assert.ok(Math.abs(rect.iconX - rect.centerX) <= 1);
        }
        assert.equal(bounds[1].top - bounds[0].bottom, 4); assert.equal(bounds[2].top - bounds[1].bottom, 4);
        await page.click('#workspace-menu-toggle');
        await page.waitForFunction(() => document.querySelector('#workspace-menu-toggle').getAttribute('aria-expanded') === 'true');
        const menu = await page.locator('#workspace-menu').boundingBox(); assert.ok(menu.x >= 0 && menu.x + menu.width <= width && menu.y >= 0 && menu.y + menu.height <= height);
        assert.ok(menu.y + menu.height <= bounds[2].top);
        await page.screenshot({ path: path.join(root, `artifacts/sidebar-footer-${width}-${collapsed ? 'collapsed' : 'expanded'}.png`), animations: 'disabled' });
        await page.click('#workspace-menu-toggle');
        await page.waitForFunction(() => !document.querySelector('#workspace-menu').matches(':popover-open'));
      }
    }
    assert.deepEqual(errors, []);
    console.log('PASS: nested project chats, cross-project selection/new chat, personal workspace, memory isolation/persistence/counts, search, coordinated motion, rapid reversal persistence, focus and inert content, anchored menu during motion, reduced motion, compact rail and aligned Models/Settings/Workspace controls with anchored menu in both sidebar modes');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
