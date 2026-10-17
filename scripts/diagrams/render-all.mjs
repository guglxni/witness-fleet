#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const run = (script, name) => {
  const result = spawnSync(process.execPath, [resolve(here, script)],
    { cwd: resolve(here, '../..'), encoding: 'utf8', timeout: 240_000 });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.status !== 0) {
    if (result.stderr) process.stderr.write(result.stderr);
    throw new Error(`${name} render failed with status ${result.status}`);
  }
};
run('render-drawio.mjs', 'draw.io');
run('render-mermaid.mjs', 'Mermaid');
run('render-excalidraw.mjs', 'Excalidraw');
