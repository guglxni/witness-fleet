import{test,expect}from'@playwright/test';
for(const width of [390,1440])test(`single YouTube embed DOM and responsive layout at ${width}px (YouTube transport isolated)`,async({page})=>{
 // Transport isolation only: keep the real YouTube iframe host out of this DOM/layout test.
 await page.route('https://www.youtube-nocookie.com/**',route=>route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><title>Benign YouTube transport-isolation stub</title>'}));
 await page.setViewportSize({width,height:900});await page.goto('/');
 const frame=page.getByTitle('Witness Fleet × FalkorDB — YouTube video player');
 await expect(page.locator('#film iframe')).toHaveCount(1);
 await expect(page.locator('#film video')).toHaveCount(0);
 await expect(frame).toHaveAttribute('src','https://www.youtube-nocookie.com/embed/v7P9KVyTrWY?autoplay=0&controls=1&playsinline=1&rel=0');
 await expect(frame).toHaveAttribute('loading','lazy');
 await expect(frame).toHaveAttribute('referrerpolicy','strict-origin-when-cross-origin');
 await expect(frame).toHaveAttribute('allowfullscreen','');
 await expect(page.getByRole('link',{name:/Watch on YouTube/})).toHaveAttribute('href','https://youtu.be/v7P9KVyTrWY');
 const layout=await page.locator('.youtube-player').evaluate(element=>{const iframe=element.querySelector('iframe')!;const host=element.getBoundingClientRect();const box=iframe.getBoundingClientRect();return{hostWidth:host.width,frameWidth:box.width,frameHeight:box.height};});
 expect(Math.abs(layout.frameWidth-layout.hostWidth)).toBeLessThanOrEqual(1);
 expect(layout.frameHeight).toBeGreaterThanOrEqual(200);
});
