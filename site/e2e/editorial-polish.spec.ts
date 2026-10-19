import {expect,test} from '@playwright/test';
test('worksheet desktop introduction gives the heading a readable column',async({page})=>{
 await page.setViewportSize({width:1440,height:1000});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
 const heading=await page.locator('#value-worksheet-title').boundingBox();
 expect(heading!.width).toBeGreaterThan(400);
 expect(heading!.height).toBeLessThan(210);
});
test('site motion preserves native scrolling and avoids decorative WebGL',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('/');await page.waitForTimeout(700);
 expect(await page.locator('html').getAttribute('class')||'').not.toContain('lenis');
 await expect(page.locator('.vanta-surface canvas')).toHaveCount(0);
 await page.getByRole('button',{name:'Pause ambient motion'}).click();
 await expect(page.getByRole('button',{name:'Resume ambient motion'})).toHaveAttribute('aria-pressed','true');
});
