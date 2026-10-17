#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { exportToSvg } from '@excalidraw/utils';

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) throw new Error('usage: node export-excalidraw.mjs input.excalidraw output.svg');
const scene = JSON.parse(await readFile(inputPath, 'utf8'));
if (scene.type !== 'excalidraw' || !Array.isArray(scene.elements) || scene.version !== 2) {
  throw new Error('expected a standard Excalidraw v2 scene JSON');
}
const svg = exportToSvg(scene);
const xml = svg.outerHTML;
if (!xml.includes('<svg') || !xml.includes('viewBox=')) throw new Error('Excalidraw SVG renderer returned an invalid SVG document');
await writeFile(outputPath, `<?xml version="1.0" encoding="UTF-8"?>\n${xml}\n`, 'utf8');
console.log(`Rendered ${scene.elements.filter((e) => !e.isDeleted).length} Excalidraw elements.`);
