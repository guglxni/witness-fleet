import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { SceneSnapshot } from './workbench';
import { isSceneObjectVisible } from './sceneSelection';

type Options = { selectedId: string | null; wireframe: boolean; showFacility: boolean; showSites: boolean };
export function SceneView({ scene, selectedId, onSelect, wireframe, showFacility, showSites, onFallbackChange }: {
  scene: SceneSnapshot; selectedId: string | null; onSelect: (id: string) => void; wireframe: boolean; showFacility: boolean; showSites: boolean; onFallbackChange?: (fallback: boolean) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const renderOptions = useRef<Options>({ selectedId, wireframe, showFacility, showSites });
  const updateView = useRef<(() => void) | null>(null);
  const selectObject = useRef(onSelect);
  const [fallback, setFallback] = useState(false);
  useEffect(() => { onFallbackChange?.(fallback); }, [fallback, onFallbackChange]);
  useEffect(() => { renderOptions.current = { selectedId, wireframe, showFacility, showSites }; updateView.current?.(); }, [selectedId, wireframe, showFacility, showSites]);
  useEffect(() => { selectObject.current = onSelect; }, [onSelect]);
  useEffect(() => {
    const root = host.current;
    if (!root || fallback) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    } catch {
      setFallback(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); renderer.setSize(Math.max(root.clientWidth, 1), Math.max(root.clientHeight, 1));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05; renderer.setClearColor(0x101817, 1); root.appendChild(renderer.domElement);

    const world = new THREE.Scene(); world.background = new THREE.Color(0x101817); world.fog = new THREE.Fog(0x101817, 24, 56);
    const aspect = root.clientWidth / Math.max(root.clientHeight, 1);
    const camera = new THREE.OrthographicCamera(-10 * aspect, 10 * aspect, 10, -10, 0.1, 90);
    camera.up.set(0, 1, 0); camera.position.set(0, 0, 27); camera.lookAt(0, 0, 0);
    const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = false; controls.screenSpacePanning = false;
    controls.minZoom = 0.65; controls.maxZoom = 3.2; controls.maxPolarAngle = Math.PI / 2.02; controls.enableRotate = false; controls.target.set(0, 0, 0);
    world.add(new THREE.HemisphereLight(0xd7eee3, 0x26322f, 2.0));
    const keyLight = new THREE.DirectionalLight(0xffe7c8, 3.4); keyLight.position.set(-5, -2, 14); keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1536, 1536); keyLight.shadow.camera.left = -13; keyLight.shadow.camera.right = 13;
    keyLight.shadow.camera.top = 10; keyLight.shadow.camera.bottom = -10; keyLight.shadow.bias = -0.00018; world.add(keyLight);
    const fill = new THREE.DirectionalLight(0x75cdb4, 1.2); fill.position.set(6, 8, 10); world.add(fill);

    // Projection grid is an orientation aid, explicitly separate from MuJoCo geometry.
    const grid = new THREE.GridHelper(30, 60, 0x39514a, 0x263b35); grid.rotation.x = Math.PI / 2; grid.position.z = -0.105; world.add(grid);
    const facility = new THREE.Group(); const fleet = new THREE.Group(); const siteGroup = new THREE.Group();
    world.add(facility, fleet, siteGroup);
    const materials: THREE.Material[] = []; const disposableGeometries: THREE.BufferGeometry[] = [];
    const boxGeometry = new THREE.BoxGeometry(1, 1, 1); disposableGeometries.push(boxGeometry);
    const material = (color: THREE.Color | number, transparent = false, opacity = 1) => {
      const instance = new THREE.MeshStandardMaterial({ color, roughness: 0.58, metalness: 0.12, transparent, opacity, wireframe: renderOptions.current.wireframe, side: THREE.DoubleSide, depthWrite: !transparent || opacity >= 1 });
      materials.push(instance); return instance;
    };
    const toQuaternion = (q: [number, number, number, number]) => new THREE.Quaternion(q[1], q[2], q[3], q[0]).normalize();
    const byId = new Map<string, THREE.Object3D>();
    for (const item of scene.geometries) {
      const tint = new THREE.Color().setRGB(item.rgba[0], item.rgba[1], item.rgba[2], THREE.SRGBColorSpace);
      let shape: THREE.BufferGeometry;
      if (item.kind === 'plane') shape = new THREE.PlaneGeometry(item.size[0] * 2, item.size[1] * 2);
      else if (item.kind === 'box') shape = boxGeometry;
      else if (item.kind === 'cylinder') { shape = new THREE.CylinderGeometry(item.size[0], item.size[0], item.size[2] * 2, 32, 1); shape.rotateX(Math.PI / 2); }
      else shape = new THREE.SphereGeometry(item.size[0], 24, 16);
      if (shape !== boxGeometry) disposableGeometries.push(shape);
      const mesh = new THREE.Mesh(shape, material(tint, item.rgba[3] < 0.999, item.rgba[3]));
      mesh.name = item.id; mesh.userData.objectId = item.id; mesh.position.set(...item.position); mesh.quaternion.copy(toQuaternion(item.quaternion));
      if (item.kind === 'box') mesh.scale.set(item.size[0] * 2, item.size[1] * 2, item.size[2] * 2);
      mesh.castShadow = item.id !== 'floor'; mesh.receiveShadow = true;
      byId.set(item.id, mesh); (item.body ? fleet : facility).add(mesh);
    }
    for (const site of scene.sites) {
      const radius = Math.max(site.size[0], 0.035);
      const marker = new THREE.Mesh(new THREE.SphereGeometry(radius, 18, 12), material(site.id.includes('sensor') ? 0xf0bd72 : 0x7ddcbd, true, 0.64));
      disposableGeometries.push(marker.geometry); marker.position.set(...site.position); marker.name = site.id; marker.userData.objectId = site.id;
      siteGroup.add(marker); byId.set(site.id, marker);
    }
    const selection = new THREE.Box3Helper(new THREE.Box3(), 0xf1c879); selection.visible = false; world.add(selection);
    const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2(); let pointerDown = { x: 0, y: 0 };
    const pointerStart = (event: PointerEvent) => { pointerDown = { x: event.clientX, y: event.clientY }; };
    const pointerEnd = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect(); pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects([facility, fleet, siteGroup], true).filter((hit) => isSceneObjectVisible(hit.object) && hit.object.userData.objectId);
      if (hits[0]) selectObject.current(hits[0].object.userData.objectId as string);
    };
    renderer.domElement.addEventListener('pointerdown', pointerStart); renderer.domElement.addEventListener('pointerup', pointerEnd);
    const resize = new ResizeObserver(() => {
      const width = root.clientWidth, height = root.clientHeight; if (!width || !height) return;
      const ratio = width / height, extent = 10 / camera.zoom; camera.left = -extent * ratio; camera.right = extent * ratio; camera.top = extent; camera.bottom = -extent;
      camera.updateProjectionMatrix(); renderer.setSize(width, height); render();
    }); resize.observe(root);

    const render = () => {
      const options = renderOptions.current; facility.visible = options.showFacility; fleet.visible = true; siteGroup.visible = options.showSites;
      for (const mat of materials) if (mat instanceof THREE.MeshStandardMaterial) mat.wireframe = options.wireframe;
      const selected = byId.get(options.selectedId ?? ''); selection.visible = !!selected && isSceneObjectVisible(selected);
      if (selected) selection.box.setFromObject(selected);
      renderer.render(world, camera);
    };
    updateView.current = render;
    const reset = () => { controls.enableRotate = false; camera.position.set(0, 0, 27); camera.up.set(0, 1, 0); camera.zoom = 1; camera.lookAt(0, 0, 0); camera.updateProjectionMatrix(); controls.target.set(0, 0, 0); render(); };
    const top = () => { controls.enableRotate = false; camera.position.set(0, 0, 27); camera.up.set(0, 1, 0); camera.lookAt(0, 0, 0); camera.updateProjectionMatrix(); controls.target.set(0, 0, 0); render(); };
    const orbit = () => { controls.enableRotate = true; camera.position.set(0, -17, 17); camera.up.set(0, 0, 1); camera.lookAt(0, 0, 0); camera.updateProjectionMatrix(); controls.target.set(0, 0, 0); render(); };
    const zoom = (event: Event) => { const change = Number((event as CustomEvent<number>).detail); camera.zoom = THREE.MathUtils.clamp(camera.zoom + change * 0.16, 0.65, 3.2); camera.updateProjectionMatrix(); render(); };
    const onControlChange = () => render();
    const contextLost = (event: Event) => { event.preventDefault(); updateView.current = null; const oldRenderer = renderer; oldRenderer.dispose(); oldRenderer.domElement.remove(); setFallback(true); };
    controls.addEventListener('change', onControlChange); renderer.domElement.addEventListener('webglcontextlost', contextLost);
    window.addEventListener('scene-reset', reset); window.addEventListener('scene-top', top); window.addEventListener('scene-orbit', orbit); window.addEventListener('scene-zoom', zoom);
    render();
    return () => {
      resize.disconnect(); controls.removeEventListener('change', onControlChange); controls.dispose(); renderer.domElement.removeEventListener('pointerdown', pointerStart); renderer.domElement.removeEventListener('pointerup', pointerEnd); renderer.domElement.removeEventListener('webglcontextlost', contextLost);
      window.removeEventListener('scene-reset', reset); window.removeEventListener('scene-top', top); window.removeEventListener('scene-orbit', orbit); window.removeEventListener('scene-zoom', zoom);
      for (const geometry of disposableGeometries) geometry.dispose(); for (const mat of materials) mat.dispose(); selection.geometry.dispose(); (selection.material as THREE.Material).dispose();
      renderer.dispose(); renderer.domElement.remove(); updateView.current = null;
    };
  }, [scene, fallback]);
  return <div ref={host} className={`three-host${fallback ? ' is-fallback' : ''}`} role="region" aria-label={`MuJoCo scene snapshot at world tick ${scene.world_tick}; plus Z up.${fallback ? ' 2D projection fallback; orbit, drag rotation, and wireframe unavailable.' : ' Drag to orbit; select visible geometry to inspect.'}`}>
    {fallback && <SceneFallback scene={scene} selectedId={selectedId} onSelect={onSelect} showFacility={showFacility} showSites={showSites} wireframe={wireframe} />}
  </div>;
}

export function SceneFallback({ scene, selectedId, onSelect, showFacility, showSites }: { scene: SceneSnapshot; selectedId: string | null; onSelect: (id: string) => void; showFacility: boolean; showSites: boolean; wireframe: boolean }) {
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const zoomView = (event: Event) => {
      const change = Number((event as CustomEvent<number>).detail);
      if (!Number.isFinite(change) || change === 0) return;
      setZoom((current) => Math.min(3.2, Math.max(0.65, Math.round((current + change * 0.16) * 100) / 100)));
    };
    const resetView = () => setZoom(1);
    window.addEventListener('scene-zoom', zoomView); window.addEventListener('scene-reset', resetView);
    return () => { window.removeEventListener('scene-zoom', zoomView); window.removeEventListener('scene-reset', resetView); };
  }, []);
  const x = (value: number) => 350 + value * 20; const y = (value: number) => 210 - value * 20;
  const yaw = (q: [number, number, number, number]) => Math.atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2)) * 180 / Math.PI;
  const fill = (rgba: [number, number, number, number]) => `rgba(${Math.round(rgba[0] * 255)},${Math.round(rgba[1] * 255)},${Math.round(rgba[2] * 255)},${rgba[3]})`;
  const width = 700 / zoom, height = 420 / zoom, left = (700 - width) / 2, top = (420 - height) / 2;
  const viewBox = zoom === 1 ? '0 0 700 420' : `${left.toFixed(3)} ${top.toFixed(3)} ${width.toFixed(3)} ${height.toFixed(3)}`;
  return <svg className="scene-fallback" viewBox={viewBox} role="img" aria-label={`2D top projection of the exact scene snapshot at world tick ${scene.world_tick}; +Z is up.`}>
    <defs><pattern id="sceneGrid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#344740" strokeWidth=".65" /></pattern></defs><rect width="700" height="420" fill="#111a18" /><rect width="700" height="420" fill="url(#sceneGrid)" />
    {showFacility && scene.geometries.filter((g) => !g.body).map((g) => <g key={g.id} data-object-id={g.id} transform={`translate(${x(g.position[0])} ${y(g.position[1])}) rotate(${-yaw(g.quaternion)})`} onClick={() => onSelect(g.id)} className="fallback-pick">
      {g.kind === 'plane' ? <rect x={-g.size[0] * 20} y={-g.size[1] * 20} width={g.size[0] * 40} height={g.size[1] * 40} fill={fill(g.rgba)} stroke="#95a99a" strokeWidth="1" /> : g.kind === 'cylinder' || g.kind === 'sphere' ? <circle r={Math.max(g.size[0] * 20, 2)} fill={fill(g.rgba)} stroke="#f0d29a" strokeWidth="1" /> : <rect x={-g.size[0] * 20} y={-g.size[1] * 20} width={g.size[0] * 40} height={g.size[1] * 40} fill={fill(g.rgba)} stroke={selectedId === g.id ? '#f1c879' : '#76877a'} strokeWidth="1" />}
      <title>{g.id} · top-view footprint approximation · xyz {g.position.map((v) => v.toFixed(3)).join(', ')} m · reported primitive size {g.size.map((v) => v.toFixed(3)).join(', ')} m</title>
    </g>)}
    {showSites && scene.sites.map((s) => <circle key={s.id} data-object-id={s.id} cx={x(s.position[0])} cy={y(s.position[1])} r={Math.max(s.size[0] * 20, 2)} fill={s.id.includes('sensor') ? '#f0bd72' : '#7ddcbd'} fillOpacity=".72" stroke={selectedId === s.id ? '#f1c879' : 'none'} onClick={() => onSelect(s.id)} className="fallback-pick"><title>{s.id} · xyz {s.position.map((v) => v.toFixed(3)).join(', ')} m</title></circle>)}
    {scene.geometries.filter((g) => !!g.body).map((g) => <g key={g.id} data-object-id={g.id} transform={`translate(${x(g.position[0])} ${y(g.position[1])}) rotate(${-yaw(g.quaternion)})`} onClick={() => onSelect(g.id)} className="fallback-pick"><rect x={-Math.max(g.size[0] * 20, 5)} y={-Math.max(g.size[1] * 20, 5)} width={Math.max(g.size[0] * 40, 10)} height={Math.max(g.size[1] * 40, 10)} rx={g.kind === 'cylinder' ? 12 : 2} fill={g.body === 'scout' ? '#609fe6' : g.body === 'recovery' ? '#e1a34f' : g.body === 'courier' ? '#72bd8a' : fill(g.rgba)} stroke={selectedId === g.id ? '#f1c879' : '#dce8dd'} strokeWidth="1.2" /><title>{g.id} · top-view footprint approximation · xyz {g.position.map((v) => v.toFixed(3)).join(', ')} m · reported primitive size {g.size.map((v) => v.toFixed(3)).join(', ')} m</title></g>)}
    <text x="14" y="401" fill="#afc0b4" fontSize="10" fontFamily="DM Mono, monospace">2D TOP PROJECTION · FOOTPRINT APPROXIMATIONS · SOURCE POSITIONS · +Z UP · METRES · WORLD TICK {scene.world_tick}</text>
  </svg>;
}
