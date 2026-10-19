import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const receipt=JSON.parse(readFileSync(new URL('../public/media/recorded-evidence.json',import.meta.url),'utf8'));
for(const width of [320,360,375,390,414,430,768,1024,1165,1440]){
 test(`recorded evidence readable and exact at ${width}`,async({page,request},testInfo)=>{
  // Isolate only the third-party video document; keep all app/runtime requests observable.
  // Real YouTube playback is verified separately against production.
  await page.route('https://www.youtube-nocookie.com/embed/**', route => route.fulfill({
    status: 200, contentType: 'text/html', body: '<!doctype html><title>YouTube transport isolated for static-control test</title>',
  }));
  await page.setViewportSize({width,height:width===768?430:900});
  await page.emulateMedia({reducedMotion:'reduce'});
  const mutations:string[]=[];page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))mutations.push(r.url());});
  await page.goto('/');
  const section=page.getByRole('region',{name:'Recorded run evidence'});
  await section.scrollIntoViewIfNeeded();
  await expect(section.locator('tbody tr')).toHaveCount(7);
  await expect(section.locator('.recorded-command')).toHaveCount(4);
  await section.getByRole('button',{name:'Show final complete snapshot'}).click();
  await expect(section.locator('.recorded-command')).toHaveCount(7);
  await expect(section.locator('.recorded-metrics')).toContainText('null is unknown, not zero');
  const delivery=section.locator('.recorded-command').filter({has:page.locator('.recorded-command-type',{hasText:'deliver'})});
  await delivery.locator('summary').click();
  await expect(delivery).toContainText('4855');
  const response=await request.get('/media/recorded-evidence.json');expect(response.ok()).toBe(true);expect(await response.json()).toEqual(receipt);
  const measurements=await section.evaluate(el=>({overflow:document.documentElement.scrollWidth>innerWidth,fonts:[...el.querySelectorAll('th,td,td code,.recorded-state,.recorded-command summary code,.recorded-command-type,.recorded-command-state,.recorded-toggle button,.recorded-metrics small')].filter(e=>e.getBoundingClientRect().height>0).map(e=>({text:e.textContent,font:parseFloat(getComputedStyle(e).fontSize)})),buttons:[...el.querySelectorAll('.recorded-toggle button')].map(e=>e.getBoundingClientRect().height)}));
  expect(measurements.overflow).toBe(false);
  expect(measurements.fonts.filter(x=>x.font<12)).toEqual([]);
  expect(measurements.buttons.every(h=>h>=44)).toBe(true);
  expect(mutations).toEqual([]);
  await testInfo.attach(`evidence-${width}`,{body:JSON.stringify(measurements),contentType:'application/json'});
  if(width===390||width===1440)await section.screenshot({path:testInfo.outputPath(`evidence-${width}.png`)});
 });
}
