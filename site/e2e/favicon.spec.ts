import {test,expect} from '@playwright/test';

test('branded favicon and touch icon load as images from the built site',async({page,request})=>{
 await page.goto('/');
 await expect(page.locator('link[rel="icon"][type="image/svg+xml"]')).toHaveAttribute('href','/favicon.svg');
 await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute('href','/apple-touch-icon.png');
 for(const path of ['/favicon.svg','/favicon.ico','/apple-touch-icon.png']){
  const response=await request.get(path);expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toMatch(/image\//);
  expect((await response.body()).length).toBeGreaterThan(100);
 }
 const dimensions=await page.evaluate(async()=>{
  const img=new Image();img.src='/apple-touch-icon.png';await img.decode();return[img.naturalWidth,img.naturalHeight];
 });expect(dimensions).toEqual([180,180]);
});
