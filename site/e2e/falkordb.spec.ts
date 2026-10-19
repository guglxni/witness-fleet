import{test,expect}from'@playwright/test';
import AxeBuilder from '@axe-core/playwright';
for(const width of [320,390,768,1440])test(`FalkorDB explanatory graph and all capability choices at ${width}`,async({page})=>{
 await page.setViewportSize({width,height:900});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
 const section=page.locator('#falkordb');await section.scrollIntoViewIfNeeded();
 await expect(section.getByRole('heading',{name:/Why FalkorDB is in/})).toBeVisible();
 const labels=['Property graph','Cypher reads','Version-fenced writes','Shared fleet context'];
 for(const label of labels){const b=section.getByRole('button',{name:new RegExp(label)});await b.focus();await page.keyboard.press('Enter');await expect(b).toHaveAttribute('aria-pressed','true');await expect(section.locator('pre')).toBeVisible();}
 const m=await page.evaluate(()=>({vw:innerWidth,doc:document.documentElement.scrollWidth,bad:[...document.querySelectorAll('#falkordb p,#falkordb h2,#falkordb h3,#falkordb strong,#falkordb button')].filter(e=>e.scrollWidth>e.clientWidth+2&&getComputedStyle(e).overflowX==='visible').map(e=>e.textContent)}));expect(m.doc).toBeLessThanOrEqual(width+1);expect(m.bad).toEqual([]);
 for(const img of await page.locator('img[src*="falkordb"]').all()){await expect.poll(()=>img.evaluate((e:HTMLImageElement)=>e.complete&&e.naturalWidth>0)).toBe(true);}
 await section.screenshot({path:`../qa/falkordb-${width}.png`});
 const a=await new AxeBuilder({page}).include('#falkordb').analyze();expect(a.violations).toEqual([]);
});
