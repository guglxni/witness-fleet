import {expect,test} from '@playwright/test';

for(const width of [320,390,768,1024,1440]){
 test(`scientific reading layout ${width}`,async({page})=>{
  await page.setViewportSize({width,height:900});
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/');
  expect(await page.locator('.recorded-evidence').evaluate(el=>el.parentElement?.tagName)).toBe('MAIN');
  const bounds=await page.locator('.site-header').evaluate(el=>{
   const box=el.getBoundingClientRect();
   return [...el.querySelectorAll('a,button')].filter(node=>node.getBoundingClientRect().height>0&&getComputedStyle(node).visibility!=='hidden').map(node=>({label:node.textContent,left:node.getBoundingClientRect().left,right:node.getBoundingClientRect().right,top:node.getBoundingClientRect().top,bottom:node.getBoundingClientRect().bottom,container:box.toJSON()}));
  });
  for(const box of bounds){expect(box.left,box.label||'control').toBeGreaterThanOrEqual(0);expect(box.right,box.label||'control').toBeLessThanOrEqual(width);}
  for(const selector of ['.hero-lede','.story-lower p','.applications-summary','.faq-list details>p']){
   const sizes=await page.locator(selector).evaluateAll(nodes=>nodes.map(node=>parseFloat(getComputedStyle(node).fontSize)));
   expect(sizes.every(size=>size>=16),selector).toBe(true);
  }
  await page.getByRole('button',{name:'Find a section'}).click();
  const finder=page.getByRole('dialog',{name:'Explore Witness Fleet'});
  await expect(finder).toBeVisible();
  await finder.getByRole('searchbox').fill('recorded evidence');
  await finder.getByRole('link',{name:/Recorded evidence/}).click();
  await expect(page).toHaveURL(/#recorded-evidence$/);
  await expect(finder).toHaveCount(0);
  await expect(page.locator('.recorded-evidence')).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 });
}
