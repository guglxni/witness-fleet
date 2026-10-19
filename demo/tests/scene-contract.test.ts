import { describe, expect, it } from 'vitest';
import { validateScene } from '../src/workbench';
import { sceneFixture } from './fixtures';

describe('accepted scene v1 contract', () => {
  it('accepts the allowlisted sampled +Z-up scene and retains half-extent primitive semantics', () => {
    const scene = validateScene(sceneFixture);
    expect(scene.geometries.find((g) => g.id === 'corridor_south_wall')?.size).toEqual([8, 0.11, 0.6]);
    expect(scene.geometries.find((g) => g.id === 'scout_chassis')?.size).toEqual([0.11, 0.11, 0.13]);
    expect(scene.world_tick).toBe(84);
  });

  it('rejects empty or partial geometry and sites, naming every omitted allowlisted ID', () => {
    const partialGeometry = { ...sceneFixture, geometries: sceneFixture.geometries.slice(0, 1) };
    expect(() => validateScene(partialGeometry)).toThrow(/scene_incomplete.*corridor_south_wall/);
    expect(() => validateScene({ ...sceneFixture, geometries: [] })).toThrow(/scene_incomplete.*alternate_block_geom/);
    expect(() => validateScene({ ...sceneFixture, sites: sceneFixture.sites.slice(0, 1) })).toThrow(/scene_incomplete.*north_staging/);
  });

  it('rejects fabricated geometry and malformed digest without a fallback scene', () => {
    const fabricated = structuredClone(sceneFixture);
    fabricated.geometries.push({ ...fabricated.geometries[0], id: 'invented_route', body: null });
    expect(() => validateScene(fabricated)).toThrow('scene_schema_invalid');
    expect(() => validateScene({ ...sceneFixture, model_sha256: 'x' })).toThrow('scene_schema_invalid');
  });
});
