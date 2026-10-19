// @ts-expect-error Node built-ins are available in Vitest; this project omits @types/node.
import {readFileSync} from 'node:fs';
import {expect,it} from 'vitest';
it('serves branded SVG, legacy ICO and Apple touch icons with explicit links',()=>{
 const html=readFileSync('index.html','utf8');
 expect(html).toContain('href="/favicon.svg"');
 expect(html).toContain('href="/favicon.ico"');
 expect(html).toContain('href="/apple-touch-icon.png"');
 const svg=readFileSync('public/favicon.svg','utf8');
 expect(svg).toContain('viewBox="0 0 64 64"');
 expect(svg).toContain('Witness Fleet');
 expect(svg).not.toMatch(/<script|<foreignObject|(?:href|src)=/i);
 const ico=readFileSync('public/favicon.ico');
 expect([...ico.subarray(0,4)]).toEqual([0,0,1,0]);
 const png=readFileSync('public/apple-touch-icon.png');
 expect([...png.subarray(0,8)]).toEqual([137,80,78,71,13,10,26,10]);
});
