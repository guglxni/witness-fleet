// Real local HTTP+DOM mission acceptance. Never intercept responses or use fixture JSON.
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
const require = createRequire(path.resolve('web/package.json'));
const { chromium, expect } = require('@playwright/test');
const base = process.env.WF_VERIFY_BASE ?? 'http://127.0.0.1:8095';
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)) throw new Error('Loopback-only verifier');
const out = path.resolve(process.env.WF_VERIFY_OUT ?? 'report-artifacts/final-repair/live-mission-ui');
await mkdir(out, {recursive: true});
const state = async () => { const r = await fetch(base+'/api/state'); if (!r.ok) throw new Error(await r.text()); return r.json(); };
const initial = await state();
if (initial.operator_mode !== 'local_mission' || initial.world_tick !== 0 || initial.commands.length) throw new Error('Requires new inert opt-in mission');
const browser = await chromium.launch();
const errors=[]; const phases=[];
try {
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(base);
  await expect(page.getByRole('button',{name:'Run tasks',exact:true})).toBeEnabled();
  phases.push({phase:'inert',state:await state()});
  await page.screenshot({path:path.join(out,'01-inert.png'),fullPage:true});
  await page.getByRole('button',{name:'Run tasks',exact:true}).click();
  await expect(page.locator('.mission-release-box')).toBeVisible({timeout:90000});
  const paused=await state();
  if(paused.mission_phase!=='awaiting_owner_release'||paused.commands.length!==4||paused.commands.some(c=>c.robot_id==='courier'))throw new Error('Owner boundary bypassed');
  const release=page.locator('.mission-release-box').getByRole('button');
  await expect(release).toBeDisabled();
  await page.getByRole('button',{name:/^Load retained source /}).first().click();
  await expect(page.locator('.source-card blockquote').first()).toBeVisible();
  await page.getByRole('button',{name:/^Open witness for /}).first().click();
  await expect(page.locator('.witness-card')).toBeVisible();
  phases.push({phase:'owner-pause',state:paused});
  await page.screenshot({path:path.join(out,'02-owner-pause.png'),fullPage:true});
  await page.locator('.evidence-panel').screenshot({path:path.join(out,'02-evidence.png')});
  await page.locator('.mission-release-box input[type=checkbox]').check();
  await expect(release).toBeEnabled();
  await release.click();
  await expect(page.getByRole('button',{name:'Run tasks',exact:true})).toBeEnabled({timeout:30000});
  await page.getByRole('button',{name:'Run tasks',exact:true}).click();
  await expect.poll(async()=> (await state()).mission_phase,{timeout:90000}).toBe('complete');
  const final=await state();
  if(final.commands.length!==7||!final.commands.every(c=>c.state==='OUTCOME_VERIFIED')||final.metrics.delivery_completed!==1)throw new Error('Incomplete graph mission');
  await expect(page.getByRole('button',{name:'Run tasks',exact:true})).toBeDisabled();
  phases.push({phase:'complete',state:final});
  for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844],['narrow',320,700]]) {
    await page.setViewportSize({width,height});
    await page.screenshot({path:path.join(out,`03-complete-${name}.png`),fullPage:true});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);
    if(overflow)throw new Error(`horizontal overflow:${name}`);
  }
  if(errors.length)throw new Error(JSON.stringify(errors));
  await writeFile(path.join(out,'verification.json'),JSON.stringify({base,errors,phases,passed:true},null,2));
  console.log(JSON.stringify({base,episode:final.episode_id,commands:final.commands.length,delivery:final.metrics.delivery_completed,errors,passed:true,out}));
} finally {await browser.close();}
