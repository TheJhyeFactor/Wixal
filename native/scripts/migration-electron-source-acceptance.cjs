// Create one genuine legacy MCP export through the Electron UI, then pass that
// exact workspace.json through the production native importer.
const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { Store: ElectronStore } = require('../../app/store.cjs');

const root = path.resolve(__dirname, '../..');
const fixture = path.join(root, 'native/tests/mcp_fixture.py');
const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');

(async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-electron-source-'));
  const dataDirectory = path.join(temporary, 'electron-user-data');
  // Initialize only the disposable workspace's onboarding/launch preferences
  // through the production Store. Collection records are still created below
  // through the visible app form, never injected into Store.data.
  const initialStore = new ElectronStore(dataDirectory);
  initialStore.data.setup = { entryCompleted: true, completed: true };
  initialStore.data.ui.launchAnimation = false;
  initialStore.data.ui.launchSound = false;
  initialStore.save();
  const sourceFile = path.join(dataDirectory, 'workspace.json');
  const exportedFile = path.join(root, 'artifacts/native/electron-mcp-source-workspace.json');
  const targetDirectory = path.join(temporary, 'native-target');
  const reportFile = path.join(root, 'artifacts/native/migration-electron-source-acceptance.json');
  const environment = { ...process.env, WIXAL_DATA_DIR: dataDirectory, WIXAL_RUNTIME_MODE: 'external' };
  delete environment.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({
      args: [root], env: environment,
      ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}),
    });
    const page = await app.firstWindow();
    page.setDefaultTimeout(8000);
    await page.locator('#launch-screen').waitFor({ state: 'detached' });
    if (await page.locator('#start-guest').isVisible()) {
      await page.locator('#start-guest').click();
      await page.locator('#start-page').waitFor({ state: 'hidden' });
    }
    if (await page.locator('#setup-dialog').isVisible()) {
      await page.locator('#setup-finish').click();
      await page.locator('#setup-dialog').waitFor({ state: 'hidden' });
    }
    await page.locator('#welcome-toolkit').waitFor();
    await page.locator('#welcome-toolkit').click();
    await page.locator('#manage-extensions').click();
    await page.locator('#extensions-dialog[open]').waitFor();
    await page.locator('#extension-name').fill('Migration acceptance echo');
    await page.locator('#extension-command').fill('/opt/homebrew/bin/python3');
    await page.locator('#extension-args').fill(JSON.stringify([fixture]));
    await page.locator('#extension-form button[type="submit"]').click();
    await page.waitForFunction(async () => (await window.wixal.state()).mcpServers?.length === 1);
    await page.waitForFunction(() => document.querySelector('#extension-list')?.textContent.includes('Migration acceptance echo'));
    const uiState = await page.evaluate(() => window.wixal.state());
    assert.equal(uiState.appVersion, require('../../package.json').version);
    const diskSource = JSON.parse(await fs.readFile(sourceFile, 'utf8'));
    assert.equal(uiState.mcpServers.length, 1);
    assert.equal(diskSource.mcpServers.length, 1);
    assert.equal(diskSource.mcpServers[0].name, 'Migration acceptance echo');
    assert.equal(diskSource.mcpServers[0].command, '/opt/homebrew/bin/python3');
    assert.deepEqual(diskSource.mcpServers[0].args, [fixture]);
    assert.equal((diskSource.skills || []).length, 0);
    assert.equal((diskSource.schedules || []).length, 0);
    assert.equal(uiState.externalConnections.length, 0, 'Saving a source server must not auto-launch it');

    const bytes = await fs.readFile(sourceFile);
    await fs.mkdir(path.dirname(exportedFile), { recursive: true });
    await fs.writeFile(exportedFile, bytes);
    const sourceHash = sha256(bytes);
    await app.close(); app = null;

    const importerCode = [
      'import hashlib,json,sys',
      `sys.path.insert(0, ${JSON.stringify(path.join(root, 'native/engine'))})`,
      'from wixal.storage import Store',
      'store=Store(sys.argv[1])',
      'try:',
      ' result=store.import_legacy(sys.argv[2])',
      ' state=store.data',
      ' state_hash=hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False).encode()).hexdigest()',
      ' summary={"counts":result["counts"],"skippedExisting":result["skippedExisting"],"warnings":result["warnings"],"mcpServers":state["mcpServers"],"skills":state["skills"],"schedules":state["schedules"],"migration":state["migration"],"targetStateSha256":state_hash}',
      ' print(json.dumps(summary,ensure_ascii=False))',
      'finally: store.close()',
    ].join('\n');
    const python = path.join(root, 'native/.venv/bin/python');
    const imported = spawnSync(python, ['-c', importerCode, targetDirectory, exportedFile], {
      cwd: root, encoding: 'utf8', timeout: 30_000,
    });
    if (imported.status !== 0) throw new Error(`Native import failed (${imported.status}): ${imported.stderr}`);
    const target = JSON.parse(imported.stdout);
    assert.equal(target.counts.mcpServers, 1);
    assert.equal(target.mcpServers.length, 1);
    assert.equal(target.mcpServers[0].command, diskSource.mcpServers[0].command);
    assert.deepEqual(target.mcpServers[0].args, diskSource.mcpServers[0].args);
    assert.equal(target.mcpServers[0].credentialsExcluded, false);
    assert.equal(target.skills.length, 0);
    assert.equal(target.schedules.length, 0);
    assert.ok(target.warnings.some(warning => warning.includes('imported disconnected')));
    assert.equal(sha256(await fs.readFile(sourceFile)), sourceHash, 'Source workspace changed after import');
    const report = {
      status: 'passed',
      sourceApp: process.env.WIXAL_APP_PATH || 'Electron development entry using shipped UI files',
      sourceAppVersion: uiState.appVersion,
      sourceDataDirectoryWasDisposable: true,
      sourceCreatedThroughVisibleUi: true,
      sourceWorkspacePath: exportedFile,
      sourceFileBytes: bytes.byteLength,
      sourceFileSha256: sourceHash,
      sourceMcpServers: diskSource.mcpServers.length,
      sourceSkills: (diskSource.skills || []).length,
      sourceSchedules: (diskSource.schedules || []).length,
      nativeImportCounts: target.counts,
      importedMcp: target.mcpServers,
      importedDisconnectedWarning: target.warnings.find(warning => warning.includes('imported disconnected')),
      sourceUnchangedAfterImport: true,
      targetStateSha256: target.targetStateSha256,
      historyReview: {
        firstMcpUiCommit: '414f5b4 Release Wixal 0.6.0 with project recall, web tools and MCP connections',
        electronSkillsCreationApiFound: false,
        electronSchedulesCreationApiFound: false,
        repositoryJsonExportFixturesWithPopulatedSkillsOrSchedulesFound: false,
      },
    };
    await fs.writeFile(reportFile, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report, null, 2));
  } finally {
    if (app) await app.close().catch(() => {});
    await fs.rm(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
