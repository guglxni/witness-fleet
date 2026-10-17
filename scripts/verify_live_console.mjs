// Actual local API/DOM smoke. No intercepted responses, fixtures or mutations.
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
const require = createRequire(path.resolve('web/package.json'));
const { chromium } = require('@playwright/test');
const base = 'http://127.0.0.1:8094';
const out = path.resolve('artifacts/showcase-20261017/live-ui');
await mkdir(out, { recursive: true });
const stateResponse = await fetch(base + '/api/state');
if (!stateResponse.ok) throw new Error('state not available');
const state = await stateResponse.json();
if (state.operator_mode !== 'inspection_only' || state.dispatch_ready || state.commands.length)
  throw new Error('unexpected authority posture');
const browser = await chromium.launch();
const results = [];
try {
  for (const [name, viewport] of [['desktop', {width:1440,height:1000}], ['mobile', {width:390,height:844}]]) {
    const page = await browser.newPage({viewport});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.getByText(state.episode_id, {exact:true}).first().waitFor();
    if (await page.getByLabel('Robots', {exact:true}).getByRole('listitem').count() !== state.robots.length)
      throw new Error('robot projection count mismatch');
    if (!await page.getByRole('button', {name:'Run',exact:true}).isDisabled())
      throw new Error('run improperly enabled');
    await page.getByRole('button', {name: /^Load retained source /}).first().click();
    await page.locator('.source-card blockquote').first().waitFor();
    const witnessButton = page.getByRole('button', {name: /^Open witness for /}).first();
    await witnessButton.click();
    await page.locator('.witness-card').waitFor();
    const relationText = await page.locator('.witness-links').innerText();
    if (!relationText.includes('SUPPORTED_BY') || !relationText.includes('OWNED_BY'))
      throw new Error('real witness provenance edges missing');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (overflow || errors.length) throw new Error(JSON.stringify({name,overflow,errors}));
    await page.screenshot({path:path.join(out, name + '.png'), fullPage:true});
    await page.locator('.evidence-panel').screenshot({path:path.join(out, name + '-witness.png')});
    results.push({name,viewport,episode:state.episode_id,graph_version:state.graph_version,
      robots:state.robots.length,tasks:state.tasks.length,sources:state.sources.length,
      dispatch_ready:state.dispatch_ready,mode:state.operator_mode,overflow,errors,
      screenshot:path.join(out,name+'.png')});
    await page.close();
  }
} finally { await browser.close(); }
await writeFile(path.join(out,'verification.json'), JSON.stringify(results,null,2));
console.log(JSON.stringify(results,null,2));
