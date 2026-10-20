import{test,expect}from'@playwright/test';
import AxeBuilder from '@axe-core/playwright';
for(const width of [320,360,390,768,1024,1440])test(`FalkorDB explanatory graph and all capability choices at ${width}`,async({page})=>{
 await page.setViewportSize({width,height:900});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
 const section=page.locator('#falkordb');await section.scrollIntoViewIfNeeded();
 await expect(section.getByRole('heading',{name:/Why FalkorDB is in/,level:2})).toBeVisible();
 await expect(section.getByRole('heading',{name:/Follow the evidence path\./,level:3})).toBeVisible();
 await expect(section.getByRole('heading',{name:/Schema excerpt/,level:4})).toBeVisible();
 const labels=['Property graph','Cypher reads','Version-fenced writes','Shared fleet context'];
 for(const label of labels){const b=section.getByRole('button',{name:new RegExp(label)});await b.focus();await page.keyboard.press('Enter');await expect(b).toHaveAttribute('aria-pressed','true');if(label==='Property graph'){await expect(section.getByRole('group',{name:'Canonical FalkorDB schema diagram'})).toBeVisible();await expect(section.locator('.fdb-code-panel pre')).toHaveCount(0);}else{await expect(section.locator('.fdb-code-panel pre')).toBeVisible();}}
 const m=await page.evaluate(()=>({vw:innerWidth,doc:document.documentElement.scrollWidth,bad:[...document.querySelectorAll('#falkordb p,#falkordb h2,#falkordb h3,#falkordb strong,#falkordb button')].filter(e=>e.scrollWidth>e.clientWidth+2&&getComputedStyle(e).overflowX==='visible').map(e=>e.textContent)}));expect(m.doc).toBeLessThanOrEqual(width+1);expect(m.bad).toEqual([]);
 for(const img of await page.locator('img[src*="falkordb"]').all()){await expect.poll(()=>img.evaluate((e:HTMLImageElement)=>e.complete&&e.naturalWidth>0)).toBe(true);}
 await section.screenshot({path:`../qa/falkordb-${width}.png`});
 const a=await new AxeBuilder({page}).include('#falkordb').analyze();expect(a.violations).toEqual([]);
});

test('canonical schema paths stay connected and readable without shrinking mobile labels',async({page})=>{
 await page.setViewportSize({width:320,height:900});await page.goto('/');
 const region=page.getByRole('region',{name:'Scrollable canonical schema diagram'});
 await expect(region).toBeVisible();
 const metrics=await region.evaluate(el=>{
  const svg=el.querySelector('svg')!;
  const scale=svg.getScreenCTM()!.a;
  return {overflow:document.documentElement.scrollWidth,scale,labels:[...el.querySelectorAll('.fdb-schema-node strong,.fdb-schema-node small,.fdb-schema-edge span')].map(label=>({text:label.textContent,font:parseFloat(getComputedStyle(label).fontSize)*scale,scroll:label.scrollWidth,client:label.clientWidth})),paths:[...el.querySelectorAll('path[data-edge-id]')].map(path=>({from:path.getAttribute('data-from'),to:path.getAttribute('data-to'),marker:path.getAttribute('marker-end')}))};
 });
 expect(metrics.overflow).toBeLessThanOrEqual(321);
 expect(metrics.labels.filter(label=>label.font<12||label.scroll>label.client+1)).toEqual([]);
 expect(metrics.paths).toHaveLength(8);
 await region.focus();await page.keyboard.press('ArrowRight');
 await expect.poll(()=>region.evaluate(el=>el.scrollLeft)).toBeGreaterThan(0);
 await page.getByRole('button',{name:'APPROVED_BY relationship Release to Owner'}).focus();await page.keyboard.press('Space');
 await expect(page.getByRole('complementary',{name:'Selected schema detail'})).toContainText('Release → Owner');
 await expect(page.locator('.fdb-code-explorer')).not.toHaveAttribute('open');
 await page.getByRole('button',{name:/Property graph/}).click();
 const a=await new AxeBuilder({page}).include('#falkordb').analyze();expect(a.violations).toEqual([]);
});

test('FalkorDB directed schema edges, keyboard selection, readable code and copy work locally',async({page,context})=>{
 await context.grantPermissions(['clipboard-read','clipboard-write']);
 await page.setViewportSize({width:390,height:900});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
 const section=page.locator('#falkordb');await section.scrollIntoViewIfNeeded();
 const relationships=[
  ['IMPOSES','Decision → Restriction'],['APPLIES_TO','Restriction → Corridor'],['OWNED_BY','Decision → Owner'],['SUPPORTED_BY','Decision → EvidenceSpan'],
  ['IN_REVISION','EvidenceSpan → Revision'],['REVISION_OF','Revision → Source'],['LIFTS','Release → Restriction'],['APPROVED_BY','Release → Owner'],
 ];
 for(const [verb,direction] of relationships){
  const edge=section.getByRole('button',{name:new RegExp(`${verb} relationship`)});await edge.focus();await page.keyboard.press('Enter');
  await expect(edge).toHaveAttribute('aria-pressed','true');await expect(section.getByRole('complementary',{name:'Selected schema detail'})).toContainText(direction);
 }
 await section.locator('.fdb-code-explorer summary').click();
 const code=section.locator('.fdb-code-window pre');await expect(code).toBeVisible();
 await expect(code).toContainText('Decision -[:IMPOSES]-> Restriction');
 const style=await code.evaluate(el=>({font:parseFloat(getComputedStyle(el).fontSize),color:getComputedStyle(el).color,background:getComputedStyle(el).backgroundColor,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth}));
 expect(style.font).toBeGreaterThanOrEqual(12);expect(style.color).not.toBe(style.background);expect(style.scrollHeight).toBeLessThanOrEqual(style.clientHeight+1);
 const touchTargets=await section.locator('.fdb-selector button,.fdb-schema-node,.fdb-schema-edge,.fdb-code-actions button').evaluateAll(buttons=>buttons.map(button=>({label:button.getAttribute('aria-label')||button.textContent,height:button.getBoundingClientRect().height})));
 expect(touchTargets.filter(target=>target.height<44)).toEqual([]);
 await section.getByRole('button',{name:'Copy excerpt'}).click();
 await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toContain('Decision -[:IMPOSES]-> Restriction');
 await section.screenshot({path:'../qa/falkordb-390.png'});
});
