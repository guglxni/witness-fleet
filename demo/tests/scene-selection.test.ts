import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { isSceneObjectVisible } from '../src/sceneSelection';

describe('native scene visible-layer selection', () => {
  it('rejects ray hits inside hidden layers and accepts them again when shown', () => {
    const layer = new THREE.Group();
    const nested = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial());
    mesh.userData.objectId = 'floor'; layer.add(nested); nested.add(mesh);
    layer.updateMatrixWorld(true);
    const ray = new THREE.Raycaster(new THREE.Vector3(0, 0, 5), new THREE.Vector3(0, 0, -1));
    try {
      layer.visible = false;
      const hits = ray.intersectObjects([layer], true);
      expect(hits.length).toBeGreaterThan(0);
      expect(hits.filter(hit => isSceneObjectVisible(hit.object))).toEqual([]);
      layer.visible = true;
      expect(isSceneObjectVisible(mesh)).toBe(true);
      nested.visible = false;
      expect(isSceneObjectVisible(mesh)).toBe(false);
      nested.visible = true; mesh.visible = false;
      expect(isSceneObjectVisible(mesh)).toBe(false);
    } finally { mesh.geometry.dispose(); mesh.material.dispose(); }
  });
});
