import {expect,test} from '@playwright/test';
for(const width of [390,1440]){
 test(`scientific annotation labels remain readable at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:900});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
  const labels=['.judge-label','.judge-path small','.judge-loop>ol>li>strong','.phase-evidence-grid>div>span','.sequence-serial','.motion-status','.provenance-grid code','.readiness-status','.value-worksheet__field-unit'];
  for(const selector of labels){
   expect(await page.locator(selector).count(),selector).toBeGreaterThan(0);
   const size=await page.locator(selector).evaluateAll(nodes=>nodes.map(el=>parseFloat(getComputedStyle(el).fontSize)));
   expect(size.every(px=>px>=12),`${selector}: ${size.join(',')}`).toBe(true);
  }
 });
}
