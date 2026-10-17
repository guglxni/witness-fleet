import {expect,test} from '@playwright/test';
const widths=[320,390,768,1440];
for(const width of widths){
 test(`responsive ${width}px: no overflow, working stage, video and no console errors`,async({page})=>{
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await page.setViewportSize({width,height:width<500?844:920});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:/motion needs evidence/i})).toBeVisible();
  await expect(page.locator('[data-part]')).toHaveCount(74);
  const dimensions=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,body:document.body.scrollWidth,video:document.querySelector('video')?.getAttribute('src')}));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.client);
  await page.getByRole('button',{name:'MuJoCo recovery'}).first().click();
  await expect(page.getByRole('heading',{name:'MuJoCo recovery'})).toBeVisible();
  const video=page.getByLabel(/Narrated product launch film with recorded MuJoCo evidence/i);await expect(video).toHaveAttribute('controls');
  expect(errors).toEqual([]);
 });
}
test('mobile navigation opens, navigates, and is usable at 320px',async({page})=>{
 await page.setViewportSize({width:320,height:760});await page.goto('/');
 const toggle=page.getByRole('button',{name:'Open navigation'});await toggle.click();await expect(page.getByRole('link',{name:'Launch film'})).toBeVisible();
 await page.getByRole('link',{name:'Launch film'}).click();await expect(page).toHaveURL(/#film$/);await expect(page.getByRole('heading',{name:/real evidence/i})).toBeVisible();
});
test('keyboard stage selector and reduced motion respect state without hiding content',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:390,height:844});await page.goto('/');
 const stage=page.getByRole('group',{name:'Interactive fleet-mechanism stage selector'});await stage.focus();await page.keyboard.press('ArrowRight');await expect(page.locator('[data-stage]')).toHaveAttribute('data-stage','recovery');
 await page.keyboard.press('End');await expect(page.locator('[data-stage]')).toHaveAttribute('data-stage','delivery');
 await expect(page.getByRole('heading',{name:/the model proposes/i})).toHaveCSS('opacity','1');
 const pause=page.getByRole('button',{name:'Pause all motion'});await pause.click();await expect(page.getByRole('button',{name:'Resume all motion'})).toHaveAttribute('aria-pressed','true');
});
test('native silent MuJoCo mp4 asset is served successfully',async({request})=>{const response=await request.get('/media/launch.mp4');expect(response.ok()).toBeTruthy();expect(Number(response.headers()['content-length'])).toBeGreaterThan(250000);});
