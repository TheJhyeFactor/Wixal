// Capture genuine Wixal UI with disposable project and application data.
// Run with: node website/scripts/capture-app.cjs /absolute/path/to/Wixal
// Requires the desktop app's existing Playwright, Electron and sharp dependencies.
const {createRequire} = require('node:module');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const appRoot = path.resolve(process.argv[2] || path.join(__dirname,'../..'));
const appRequire = createRequire(path.join(appRoot,'package.json'));
const {_electron: electron} = appRequire('playwright');
const sharp = appRequire('sharp');
const output = path.resolve(__dirname,'../public/assets');

(async()=>{
  const temp = await fs.mkdtemp(path.join(os.tmpdir(),'wixal-website-capture-'));
  const project = path.join(temp,'Website project');
  await fs.mkdir(project);
  await fs.writeFile(path.join(project,'README.md'),'# A small website project\n\nA project for exploring the Wixal workspace.\n\n## Working notes\n\n- Keep the layout simple and responsive.\n- Use the existing project assets.\n- Run the checks before publishing.\n\n## Files\n\nhello.js is a small JavaScript function.\nhello.test.js checks that the function returns a greeting.\n\nRun the checks with: node --test\n');
  await fs.writeFile(path.join(project,'hello.js'), 'export function greet(name) {\n  return `Hello, ${name}.`;\n}\n');
  await fs.writeFile(path.join(project,'hello.test.js'), "import {test} from 'node:test';\nimport assert from 'node:assert/strict';\nimport {greet} from './hello.js';\ntest('greets the visitor',()=>assert.equal(greet('Wixal'),'Hello, Wixal.'));\n");
  await fs.writeFile(path.join(project,'package.json'),'{"name":"website-project","type":"module","scripts":{"test":"node --test"}}');
  const env = {...process.env,WIXAL_DATA_DIR:path.join(temp,'state'),WIXAL_TEST_PROJECT:project};
  delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({args:[appRoot],env});
    const page = await app.firstWindow();
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1200,800));
    await page.locator('#project-label').filter({hasText:'Website project'}).waitFor();
    const failures=[];
    page.on('pageerror',error=>failures.push(error.message));
    await page.emulateMedia({reducedMotion:'reduce'});
    if(await page.locator('#sidebar').evaluate(e=>e.classList.contains('collapsed'))) await page.click('#sidebar-toggle');
    await page.waitForFunction(()=>!document.querySelector('#sidebar').classList.contains('collapsed'));
    async function shot(name,selector) {
      await page.locator('#toast').waitFor({state:'hidden'});
      await page.mouse.move(1100,15);
      const target=selector?page.locator(selector):page;
      const data=await target.screenshot();
      const meta=await sharp(data).metadata();
      await sharp(data).webp({quality:95}).toFile(path.join(output,name+'.webp'));
      console.log(JSON.stringify({name,width:meta.width,height:meta.height}));
    }
    async function openSection(id) {await page.click('#workspace-menu-toggle');await page.click(id);}
    await shot('workspace');
    await openSection('#files-button');
    await page.locator('[data-file="README.md"]').click();
    await page.locator('#file-content').filter({hasText:'Working notes'}).waitFor();
    await shot('files-focus','#files-dialog');
    await shot('files');
    await page.click('[data-close="files-dialog"]');
    await page.click('#model-button');
    await page.locator('.model-row').first().waitFor();
    await shot('models-focus','#models-dialog');
    await shot('models');
    await page.click('[data-close="models-dialog"]');
    await openSection('#memory-button');
    await page.fill('#memory-input','Keep the layout simple and responsive. Run node --test before publishing.');
    await page.locator('#memory-form button').click();
    await page.locator('.memory-entry').waitFor();
    await shot('memory-focus','#memory-drawer');
    await shot('memory');
    await page.click('#close-memory');
    await openSection('#toolkit-button');
    await shot('toolkit-focus','#toolkit-drawer');
    await shot('toolkit');
    await page.click('#close-toolkit');
    await openSection('#terminal-button');
    await page.locator('#terminal .xterm').waitFor();
    // This really executes the fixture's test. No staged terminal or model output.
    await page.evaluate(()=>window.wixal['terminal-write']('clear; node --test\r'));
    await page.waitForFunction(()=>document.querySelector('#terminal').textContent.includes('pass 1'));
    await shot('terminal-focus','#terminal-panel');
    await shot('terminal');
    await page.click('#close-terminal');
    await openSection('#connections-button');
    await shot('connections-focus','#connections-dialog');
    await page.click('[data-close="connections-dialog"]');
    if(failures.length) throw new Error(failures.join('\n'));
  } finally {if(app)await app.close();await fs.rm(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
