#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../..');
const executable = [
  process.env.DRAWIO_BIN,
  '/Applications/draw.io.app/Contents/MacOS/draw.io',
  '/Applications/draw.io.app/Contents/MacOS/Electron',
  'drawio',
].filter(Boolean).find((candidate) => candidate.includes('/') ? existsSync(candidate) : true);
if (!executable) throw new Error('draw.io CLI not found; install draw.io or set DRAWIO_BIN');

const input = resolve(root, 'docs/diagrams/system-boundaries.drawio');
for (const ext of ['svg', 'png']) {
  const output = resolve(root, `docs/diagrams/system-boundaries.${ext}`);
  const args = ['-x', input, '-o', output, ...(ext === 'svg' ? ['--svg-theme', 'light', '--embed-svg-fonts', 'false'] : ['-b', '14', '-s', '1.4'])];
  const result = spawnSync(executable, args, { cwd: root, encoding: 'utf8', timeout: 120_000 });
  if (result.status !== 0) {
    process.stderr.write(result.stdout ?? '');
    process.stderr.write(result.stderr ?? '');
    throw new Error(`draw.io ${ext} export failed (status ${result.status})`);
  }
  if (!existsSync(output)) throw new Error(`draw.io reported success but output is missing: ${output}`);
  console.log(`draw.io -> ${output}`);
}
