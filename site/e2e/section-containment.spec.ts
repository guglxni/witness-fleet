import{expect,test}from'@playwright/test';
for(const width of[320,360,390,768,1024,1440])test(`every content section contains its content at ${width}`,async({page})=>{
 await page.setViewportSize({width,height:900});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
 const overflow=await page.locator('main>section').evaluateAll(es=>es.filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>({section:e.id||e.className,client:e.clientWidth,scroll:e.scrollWidth})));
 expect(overflow).toEqual([]);
});
