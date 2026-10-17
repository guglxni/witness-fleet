#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../..');
const input = resolve(root, 'docs/diagrams/command-evidence-sequence.mmd');
const output = resolve(root, 'docs/diagrams/command-evidence-sequence.svg');
const mmdc = resolve(here, 'node_modules/.bin/mmdc');
if (!existsSync(mmdc)) throw new Error('mmdc missing; run npm ci in scripts/diagrams');
const result = spawnSync(mmdc, ['-i', input, '-o', output, '-b', '#F6F5F1', '-t', 'base', '--size', '1500'],
  { cwd: root, encoding: 'utf8', timeout: 180_000 });
if (result.stdout) process.stdout.write(result.stdout);
if (result.status !== 0) {
  if (result.stderr) process.stderr.write(result.stderr);
  throw new Error(`Mermaid CLI render failed (status ${result.status})`);
}
if (!existsSync(output)) throw new Error(`Mermaid CLI produced no SVG: ${output}`);
console.log(`Mermaid CLI -> ${output}`);
