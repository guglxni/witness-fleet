import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import AxeBuilder from '@axe-core/playwright';
const receipt=JSON.parse(readFileSync(new URL('../public/media/recorded-evidence.json',import.meta.url),'utf8'));
for(const width of [320,360,390,768,1024,1440]){
 test(`recorded evidence readable and exact at ${width}`,async({page,request,context},testInfo)=>{
  // Isolate only the third-party YouTube document; leave all application requests real.
  await page.route('https://www.youtube-nocookie.com/embed/**',route=>route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><title>YouTube transport isolated for static-control test</title>'}));
  await page.setViewportSize({width,height:900});
  await page.emulateMedia({reducedMotion:'reduce'});
  const mutations:string[]=[];page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))mutations.push(r.url());});
  await page.goto('/');
  await expect(page.locator('#film iframe')).toHaveCount(1);
  await expect(page.locator('#film iframe')).toHaveAttribute('src',/v7P9KVyTrWY/);
  const section=page.locator('#recorded-evidence');
  await expect(section.getByRole('heading',{name:/inspect the retained run/i})).toBeVisible();
  await section.scrollIntoViewIfNeeded();
  await expect(section.locator('.rw-task')).toHaveCount(7);
  await expect(section.locator('.rw-command')).toHaveCount(4);
  await section.getByRole('button',{name:/final · complete/i}).click();
  await expect(section.locator('.rw-command')).toHaveCount(7);
  await expect(section.locator('.rw-outcomes')).toContainText('Unknown · null in retained evidence; not zero.');
  const delivery=section.locator('.rw-command').filter({hasText:'deliver'});
  await delivery.click();
  const inspector=section.getByRole('complementary',{name:/selected command detail/i});
  await expect(inspector).toContainText('4855');
  const receiptCommandId='command-974485c2a0fa45909dac06e726f59722';
  await expect(inspector.locator('.rw-full-id').first()).toHaveText(receiptCommandId);
  await expect(inspector.locator('.rw-id-control button').first()).toHaveAttribute('aria-label',/Copy ID, Copy command ID/);
  await context.grantPermissions(['clipboard-read','clipboard-write']);
  await inspector.getByRole('button',{name:'Copy ID, Copy command ID'}).first().click();
  await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toBe(receiptCommandId);
  for(const [index,expected] of receipt.stages[1].commands.entries()){
   await section.locator('.rw-command').nth(index).click();
   await expect(inspector.locator('.rw-full-id').first()).toHaveText(expected.command_id);
   await expect(inspector.locator('.rw-full-id').nth(1)).toHaveText(expected.task_id);
  }
  for(const [index,expected] of receipt.stages[1].tasks.entries()){
   const task=section.locator('.rw-task').nth(index);await task.locator('summary').click();
   await expect(task.locator('.rw-full-id').first()).toHaveText(expected.task_id);
   await task.locator('.rw-full-id').first().scrollIntoViewIfNeeded();
   const idBox=await task.locator('.rw-full-id').first().evaluate(id=>({width:id.getBoundingClientRect().width,scroll:id.scrollWidth,client:id.clientWidth,wrap:getComputedStyle(id).overflowWrap}));
   expect(idBox.width,expected.task_id).toBeGreaterThan(0);expect(idBox.wrap).toBe('anywhere');expect(idBox.scroll).toBeLessThanOrEqual(idBox.client+1);
   if(expected.last_command_id)await expect(task.locator('.rw-full-id').nth(1)).toHaveText(expected.last_command_id);
  }
  const response=await request.get('/media/recorded-evidence.json');expect(response.ok()).toBe(true);expect(await response.json()).toEqual(receipt);
  const measurements=await section.evaluate(el=>({overflow:document.documentElement.scrollWidth>innerWidth,fonts:[...el.querySelectorAll('button,input,summary,code,small,strong,h2,h3,h4,h5,dt,dd,a,span,p')].filter(e=>e.getBoundingClientRect().height>0&&e.textContent?.trim()).map(e=>({text:e.textContent,font:parseFloat(getComputedStyle(e).fontSize)})),buttons:[...el.querySelectorAll('button')].map(e=>e.getBoundingClientRect().height)}));
  expect(measurements.overflow).toBe(false);
  expect(measurements.fonts.filter(x=>x.font<12)).toEqual([]);
  expect(measurements.buttons.every(h=>h>=44)).toBe(true);
  expect(mutations).toEqual([]);
  const visibleIds=await section.locator('.rw-full-id').evaluateAll(ids=>ids.filter(id=>id.getBoundingClientRect().width>0).map(id=>({text:id.textContent,width:id.getBoundingClientRect().width,wrap:getComputedStyle(id).overflowWrap,scroll:id.scrollWidth,client:id.clientWidth})));
  expect(visibleIds.filter(id=>id.width<100),'Every full identifier needs a readable column, not one character per line').toEqual([]);
  expect(visibleIds.every(id=>id.wrap==='anywhere'&&id.scroll<=id.client+1)).toBe(true);
  const accessibility=await new AxeBuilder({page}).include('#recorded-evidence').withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(accessibility.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
  await testInfo.attach(`evidence-${width}`,{body:JSON.stringify(measurements),contentType:'application/json'});
  await section.screenshot({path:testInfo.outputPath(`evidence-${width}.png`)});
  if(width===390||width===1440)await section.screenshot({path:`../qa/recorded-evidence-${width}.png`});
 });
}
