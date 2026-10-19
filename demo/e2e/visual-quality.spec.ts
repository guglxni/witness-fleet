import{test,expect}from'@playwright/test';import AxeBuilder from'@axe-core/playwright';import{sceneFixture,activeState}from'../tests/fixtures';
for(const width of [320,390,768,1440])test(`readable scientific UI and accessible controls ${width}`,async({page})=>{
 await page.route('**/demo/v1/**',r=>r.fulfill({json:r.request().url().endsWith('/scene')?sceneFixture:{session:{status:'active'},state:activeState}}));
 await page.setViewportSize({width,height:1000});await page.goto('/demo/');await expect(page.locator('.three-host,.scene-fallback').first()).toBeVisible();
 const small=await page.locator('.viewport-title p,.task-name,.task-state,.metric-label,.scene-meta,.sample-info small').evaluateAll(es=>es.filter(e=>parseFloat(getComputedStyle(e).fontSize)<12).map(e=>e.className));expect(small).toEqual([]);
 const bad=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();expect(bad.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
});
