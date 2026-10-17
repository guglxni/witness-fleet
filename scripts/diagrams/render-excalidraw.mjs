#!/usr/bin/env node
import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import sharp from 'sharp';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../..');
const scenePath = resolve(root, 'docs/diagrams/sc-001-robotics.excalidraw');
const svgPath = resolve(root, 'docs/diagrams/sc-001-robotics.svg');
const pngPath = resolve(root, 'docs/diagrams/sc-001-robotics.png');
const tmp = resolve(here, '.excalidraw-render');
const bundle = resolve(tmp, 'renderer.mjs');
const scene = JSON.parse(await readFile(scenePath, 'utf8'));
if (scene.type !== 'excalidraw' || scene.version !== 2 || !Array.isArray(scene.elements)) {
  throw new Error('Expected a standard editable Excalidraw v2 scene');
}
await build({
  entryPoints: [resolve(here, 'browser-export.mjs')], bundle: true, format: 'esm', platform: 'browser',
  target: ['chrome120'], outfile: bundle, logLevel: 'silent', loader: { '.css': 'empty' },
});
const html = `<!doctype html><meta charset="utf-8"><body><script type="module" src="/renderer.mjs"></script></body>`;
const js = await readFile(bundle);
const server = createServer((req, res) => {
  if (req.url === '/') { res.writeHead(200, { 'content-type': 'text/html' }); res.end(html); return; }
  if (req.url === '/renderer.mjs') { res.writeHead(200, { 'content-type': 'text/javascript' }); res.end(js); return; }
  if (req.url === '/scene.json') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(scene)); return; }
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  res.writeHead(404); res.end();
});
await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const address = server.address();
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${address.port}/`, { waitUntil: 'networkidle', timeout: 30000 });
  const result = await page.evaluate(async () => {
    const { exportToSvg } = await import('/renderer.mjs');
    const scene = await (await fetch('/scene.json')).json();
    const svg = await exportToSvg({data: scene});
    return { svg: svg.outerHTML, count: scene.elements.filter((element) => !element.isDeleted).length };
  });
  if (errors.length) throw new Error(`Browser Excalidraw renderer error: ${errors.join('; ')}`);
  if (!result.svg.includes('<svg') || !result.svg.includes('viewBox=')) throw new Error('Excalidraw SVG export failed');
  const svg = `<?xml version="1.0" encoding="UTF-8"?>\n${result.svg}\n`;
  await writeFile(svgPath, svg, 'utf8');
  await sharp(Buffer.from(svg)).png({ width: 1800 }).toFile(pngPath);
  console.log(`Excalidraw official SVG renderer exported ${result.count} elements via Chromium DOM.`);
  console.log(`SVG -> ${svgPath}`);
  console.log(`PNG raster of official SVG -> ${pngPath}`);
} finally {
  await browser.close();
  await new Promise((ok, bad) => server.close((error) => error ? bad(error) : ok()));
}
