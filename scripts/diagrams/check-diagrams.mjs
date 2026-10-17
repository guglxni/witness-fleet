#!/usr/bin/env node
import { readFile, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../..');
const errors = [];
const need = (condition, message) => { if (!condition) errors.push(message); };
const read = (path) => readFile(resolve(root, path), 'utf8');
const files = [
  'docs/guide/README.md','docs/guide/architecture.md','docs/guide/graph-model.md',
  'docs/guide/sc-001-mission.md','docs/guide/simulation.md','docs/guide/security.md',
  'docs/guide/operations.md','docs/guide/evidence.md','docs/guide/deployment.md',
  'docs/diagrams/README.md',
];
const markdown = new Map(await Promise.all(files.map(async (f) => [f, await read(f)])));
const markdownLink = /\[[^\]]*\]\(([^)]+)\)/g;
for (const [source, text] of markdown) {
  for (const match of text.matchAll(markdownLink)) {
    const raw = match[1].split('#')[0];
    if (!raw || raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('mailto:')) continue;
    const target = resolve(root, dirname(source), decodeURIComponent(raw));
    need(existsSync(target), `${source}: missing local target ${raw}`);
  }
}

const drawio = await read('docs/diagrams/system-boundaries.drawio');
need((drawio.match(/<mxCell id=/g) ?? []).length >= 15, 'draw.io source does not have expected architecture detail');
for (const label of ['CURRENT / LOCAL TRUST DOMAIN','CLOUD INTEGRATION / VERIFY FIRST','Model is disabled for SC-001','atomic event','HOLD']) {
  need(drawio.includes(label), `draw.io source missing key label: ${label}`);
}
const mermaid = await read('docs/diagrams/command-evidence-sequence.mmd');
for (const label of ['sequenceDiagram','ALLOW receipt','Applied receipt (not physical outcome)','UNKNOWN','HOLD','Postconditions verified']) {
  need(mermaid.includes(label), `Mermaid source missing key label: ${label}`);
}
const scene = JSON.parse(await read('docs/diagrams/sc-001-robotics.excalidraw'));
need(scene.type === 'excalidraw' && scene.version === 2, 'Excalidraw scene must be standard v2 JSON');
const text = scene.elements.filter((e) => e.type === 'text' && !e.isDeleted).map((e) => e.text).join('\n');
for (const label of ['CORRIDOR C','SCOUT','RECOVERY','COURIER','PAUSE','UNKNOWN / mismatch','DELIVERY ZONE']) {
  need(text.includes(label), `Excalidraw source missing key label: ${label}`);
}
const elements = scene.elements;
const elementIds = elements.map((e) => e.id);
need(elementIds.length === new Set(elementIds).size, 'Excalidraw element IDs must be unique');
for (const e of elements.filter((x) => x.type === 'text' && x.containerId)) {
  need(elementIds.includes(e.containerId), `Excalidraw container missing for ${e.id}`);
}

const images = [
  ['docs/diagrams/system-boundaries.svg', 'svg'],
  ['docs/diagrams/system-boundaries.png', 'png'],
  ['docs/diagrams/command-evidence-sequence.svg', 'svg'],
  ['docs/diagrams/sc-001-robotics.svg', 'svg'],
  ['docs/diagrams/sc-001-robotics.png', 'png'],
];
const dimensions = {};
for (const [path, format] of images) {
  try {
    const bytes = await readFile(resolve(root, path));
    const meta = await sharp(bytes).metadata();
    need(meta.format === format, `${path}: expected ${format} but parsed ${meta.format}`);
    need(Number(meta.width) > 400 && Number(meta.height) > 180, `${path}: unexpectedly small image dimensions ${meta.width}x${meta.height}`);
    need((await stat(resolve(root, path))).size > 2000, `${path}: rendered output is too small`);
    dimensions[path] = {format:meta.format,width:meta.width,height:meta.height,bytes:(await stat(resolve(root,path))).size};
  } catch (error) { errors.push(`${path}: unreadable or missing render (${error.message})`); }
}
const seqSvg = await read('docs/diagrams/command-evidence-sequence.svg').catch(()=>'');
need(seqSvg.includes('<svg'), 'Mermaid output missing SVG root');
for (const label of ['Deterministic authorizer','HOLD','Postconditions verified']) {
  need(seqSvg.includes(label), `Rendered Mermaid SVG missing key label: ${label}`);
}
const archSvg = await read('docs/diagrams/system-boundaries.svg').catch(()=>'');
need(archSvg.includes('<svg'), 'draw.io output missing SVG root');
const robotSvg = await read('docs/diagrams/sc-001-robotics.svg').catch(()=>'');
need(robotSvg.includes('<svg'), 'Excalidraw output missing SVG root');

if (errors.length) {
  console.error(`Diagram checks failed (${errors.length}):\n- ${errors.join('\n- ')}`);
  process.exit(1);
}
console.log(JSON.stringify({status:'passed', checked_markdown_files:markdown.size, checked_relative_links:'all local markdown links under guide/diagrams', editable_sources:3, rendered_artifacts:images.length, dimensions}, null, 2));
