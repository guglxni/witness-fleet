import {expect,test} from '@playwright/test';
test('navigation tracks the current section without changing history',async({page})=>{
 await page.setViewportSize({width:1440,height:900});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
 await page.locator('#falkordb').scrollIntoViewIfNeeded();
 await expect(page.locator('.primary-nav a[href="#falkordb"]')).toHaveAttribute('aria-current','location');
 await expect(page).not.toHaveURL(/#falkordb/);
 await page.locator('#faq').scrollIntoViewIfNeeded();
 await expect(page.locator('.reading-progress')).toHaveAttribute('aria-hidden','true');
 await expect.poll(()=>page.locator('.reading-progress').evaluate(el=>el.getBoundingClientRect().width)).toBeGreaterThan(900);
});
