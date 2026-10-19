import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Box, Rotate3D, Scan, ZoomIn, ZoomOut } from 'lucide-react';
import type { RobotProjection } from '../api-contract';

type ViewMode = '3d' | '2d';
type CameraPreset = 'isometric' | 'top';

const roleColor: Record<RobotProjection['role'], string> = {
  scout: '#7ddcbd', recovery: '#f0bd72', courier: '#a9c6f2',
};

export function applyCameraView(camera: THREE.Camera & {updateProjectionMatrix:()=>void},view:CameraPreset,center={x:0,y:0},radius=12){
  if(view==='top')camera.position.set(center.x,center.y,radius*1.75);
  else camera.position.set(center.x+radius*.72,center.y-radius*.9,radius*.8);
  camera.up.set(0,view==='top'?1:0,view==='top'?0:1);camera.lookAt(center.x,center.y,0);camera.updateProjectionMatrix();
}

export function CoordinateSpace({ robots }: { robots: RobotProjection[] }) {
  const [mode, setMode] = useState<ViewMode>('3d');
  const [preset, setPreset] = useState<CameraPreset>('isometric');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [webglUnavailable, setWebglUnavailable] = useState(false);
  const [zoom, setZoom] = useState(1);
  const zoomRatio = useRef(1);
  const orbit = useRef({ x: 0, y: 0 });
  const canvasHost = useRef<HTMLDivElement>(null);
  const selected = robots.find((robot) => robot.id === selectedId) ?? null;

  useEffect(() => {
    if (!robots.some((robot) => robot.id === selectedId)) setSelectedId(robots[0]?.id ?? null);
  }, [robots, selectedId]);

  useEffect(() => {
    if (mode !== '3d' || !canvasHost.current) return;
    if (typeof window.WebGLRenderingContext === 'undefined') {
      setWebglUnavailable(true);
      return;
    }
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' });
    } catch {
      setWebglUnavailable(true);
      return;
    }
    setWebglUnavailable(false);
    const host = canvasHost.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#101b1b');
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 400);
    const center = robots.length ? robots.reduce((point, robot) => ({ x: point.x + robot.pose.x / robots.length, y: point.y + robot.pose.y / robots.length }), { x: 0, y: 0 }) : { x: 0, y: 0 };
    const span = Math.max(8, ...robots.map((robot) => Math.hypot(robot.pose.x - center.x, robot.pose.y - center.y) * 2 + 3));
    const cameraRadius = span * 1.25 / zoom;
    orbit.current = { x: 0, y: 0 };
    const aim = (view: CameraPreset) => applyCameraView(camera,view,center,cameraRadius);
    aim(preset);
    const gridSpan = Math.max(12, Math.ceil(span / 4) * 4);
    const divisions = Math.min(40, Math.max(12, gridSpan * 2));
    const grid = new THREE.GridHelper(gridSpan, divisions, '#497268', '#29433e');
    grid.rotation.x = Math.PI / 2;
    grid.position.set(center.x, center.y, -0.03);
    scene.add(grid);
    const axes = new THREE.AxesHelper(Math.min(gridSpan / 2, 4));
    axes.position.set(center.x, center.y, 0.01);
    scene.add(axes);
    const robotMeshes: { id: string; body: THREE.Mesh; heading: THREE.Line }[] = [];
    robots.forEach((robot) => {
      const size = Math.max(.28, robot.footprint_m || .4);
      const body = new THREE.Mesh(new THREE.BoxGeometry(size, size * .72, .2), new THREE.MeshStandardMaterial({ color: roleColor[robot.role], roughness: .65 }));
      body.position.set(robot.pose.x, robot.pose.y, .13);
      body.rotation.z = robot.pose.yaw;
      body.userData.robotId = robot.id;
      scene.add(body);
      const headingGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, .25), new THREE.Vector3(size * .85, 0, .25)]);
      const heading = new THREE.Line(headingGeometry, new THREE.LineBasicMaterial({ color: '#eef5ee' }));
      heading.position.set(robot.pose.x, robot.pose.y, .08);
      heading.rotation.z = robot.pose.yaw;
      scene.add(heading);
      robotMeshes.push({ id: robot.id, body, heading });
    });
    scene.add(new THREE.HemisphereLight('#d4eee4', '#203431', 2));
    const keyLight = new THREE.DirectionalLight('#ffffff', 1.2);
    keyLight.position.set(5, 6, 12);
    scene.add(keyLight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(Math.max(1, host.clientWidth), Math.max(1, host.clientHeight), false);
    renderer.domElement.setAttribute('aria-hidden', 'true');
    renderer.domElement.tabIndex = -1;
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    host.replaceChildren(renderer.domElement);
    let frame = 0;
    const render = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const width = Math.max(1, host.clientWidth);
        const height = Math.max(1, host.clientHeight);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        robotMeshes.forEach(({ id, body }) => {
          const material = body.material as THREE.MeshStandardMaterial;
          material.emissive.set(id === selectedId ? '#315e50' : '#000000');
        });
        renderer.render(scene, camera);
      });
    };
    render();
    const observer = new ResizeObserver(render);
    observer.observe(host);
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    const onPointerDown = (event: PointerEvent) => { dragging = true; lastX = event.clientX; lastY = event.clientY; renderer.domElement.setPointerCapture?.(event.pointerId); };
    const onPointerMove = (event: PointerEvent) => {
      if (!dragging) return;
      orbit.current = { x: orbit.current.x + (event.clientX - lastX) * .008, y: Math.max(-1.35, Math.min(1.35, orbit.current.y + (event.clientY - lastY) * .006)) };
      lastX = event.clientX; lastY = event.clientY;
      const azimuth = preset === 'top' ? orbit.current.x : -0.9 + orbit.current.x;
      const elevation = preset === 'top' ? 1.5 : .62 + orbit.current.y;
      camera.position.set(center.x + Math.cos(azimuth) * cameraRadius * Math.cos(elevation), center.y + Math.sin(azimuth) * cameraRadius * Math.cos(elevation), cameraRadius * Math.sin(elevation));
      camera.lookAt(center.x, center.y, 0);
      render();
    };
    const onPointerUp = () => { dragging = false; };
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      zoomRatio.current = Math.max(.42, Math.min(3, zoomRatio.current * (event.deltaY > 0 ? .92 : 1.08)));
      camera.position.sub(new THREE.Vector3(center.x, center.y, 0)).multiplyScalar(event.deltaY > 0 ? 1.08 : .92).add(new THREE.Vector3(center.x, center.y, 0));
      camera.lookAt(center.x, center.y, 0);
      render();
    };
    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerup', onPointerUp);
    renderer.domElement.addEventListener('pointercancel', onPointerUp);
    renderer.domElement.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerup', onPointerUp);
      renderer.domElement.removeEventListener('pointercancel', onPointerUp);
      renderer.domElement.removeEventListener('wheel', onWheel);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.GridHelper || object instanceof THREE.AxesHelper) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      renderer.dispose();
      host.replaceChildren();
    };
  }, [mode, preset, robots, selectedId, zoom]);

  const xs = robots.map((robot) => robot.pose.x);
  const ys = robots.map((robot) => robot.pose.y);
  const minX = Math.min(0, ...xs) - 1;
  const maxX = Math.max(0, ...xs) + 1;
  const minY = Math.min(0, ...ys) - 1;
  const maxY = Math.max(0, ...ys) + 1;
  const plotX = (x: number) => 48 + ((x - minX) / Math.max(.01, maxX - minX)) * 520;
  const plotY = (y: number) => 255 - ((y - minY) / Math.max(.01, maxY - minY)) * 210;

  return <section className="panel coordinate-panel" aria-labelledby="facility-heading">
    <div className="panel-heading coordinate-heading"><div><p className="eyebrow">LIVE PROJECTION · {robots.length} POSES</p><h2 id="facility-heading">Robot pose projection</h2></div><span className="section-meta">X / Y · METRES</span></div>
    <div className="coordinate-toolbar" role="toolbar" aria-label="Coordinate view controls">
      <button type="button" className={mode === '3d' ? 'view-control is-active' : 'view-control'} aria-label="3D coordinate view" aria-pressed={mode === '3d'} onClick={() => setMode('3d')}><Rotate3D size={16} />3D</button>
      <button type="button" className={mode === '2d' ? 'view-control is-active' : 'view-control'} aria-label="2D accessible view" aria-pressed={mode === '2d'} onClick={() => setMode('2d')}><Scan size={16} />2D</button>
      <span className="toolbar-divider" />
              <button type="button" className="view-control" aria-label="Top view" aria-pressed={preset === 'top'} onClick={() => { setPreset('top'); setZoom(1); }}>Top</button>
      <button type="button" className="view-control" aria-label="Reset view" onClick={() => { setPreset('isometric'); setZoom(1); }}><Rotate3D size={15} />Reset</button>
      <button type="button" className="view-control zoom-control" aria-label="Zoom out" onClick={() => setZoom((value) => Math.max(.6, value * .85))}><ZoomOut size={15} /></button>
      <button type="button" className="view-control zoom-control" aria-label="Zoom in" onClick={() => setZoom((value) => Math.min(2.4, value * 1.18))}><ZoomIn size={15} /></button>
    </div>
    {mode === '3d' && !webglUnavailable ? <div className="scene-canvas" ref={canvasHost} role="img" aria-label={`Three-dimensional coordinate view of ${robots.length} projected robot poses. Drag to orbit; scroll to zoom.`} /> : <div className="map-wrap">
      {mode === '3d' && webglUnavailable && <p className="fallback-note" role="status">3D rendering is unavailable in this browser; showing the accessible coordinate plot.</p>}
      {mode === '3d' && webglUnavailable && <svg className="facility-map coordinate-plot" viewBox="0 0 620 310" role="img" aria-label={`2D coordinate plot of ${robots.length}`}>
        <defs><pattern id="coordinate-grid" width="31" height="31" patternUnits="userSpaceOnUse"><path d="M31 0H0V31" fill="none" stroke="currentColor" strokeWidth=".7" opacity=".55" /></pattern></defs><rect width="620" height="310" fill="url(#coordinate-grid)" />
        {robots.map((robot) => <circle key={robot.id} cx={48 + ((robot.pose.x - minX) / Math.max(.01, maxX-minX))*520} cy={255 - ((robot.pose.y-minY)/Math.max(.01,maxY-minY))*210} r="9" fill={roleColor[robot.role]} />)}
      </svg>}
    </div>}
    <p className="coordinate-note"><span className="sensor-pill">API</span> Backend pose projection · metre coordinates · no facility geometry is supplied by this API.</p>
    <div className="robot-list" role="list" aria-label="Robots">
      {robots.map((robot) => <button type="button" className={`robot-row robot-select role-select-${robot.role}${robot.id === selectedId ? ' is-selected' : ''}`} key={robot.id} aria-label={`Select ${robot.id}`} aria-pressed={robot.id === selectedId} onClick={() => setSelectedId(robot.id)}>
        <span className={`robot-glyph role-${robot.role}`} aria-hidden="true"><Box size={17} /></span><span className="robot-identity"><strong>{robot.id}</strong><small>{robot.role} · {robot.state.replaceAll('_', ' ')}</small></span><span className="robot-pose"><b>{robot.pose.x.toFixed(2)}, {robot.pose.y.toFixed(2)}</b><small>m · θ {robot.pose.yaw.toFixed(2)}</small></span>
      </button>)}
      {robots.length === 0 && <p className="empty-copy">Robot roster is empty in the returned projection.</p>}
    </div>
    {mode === '2d' && <div className="map-wrap">
      <svg className="facility-map coordinate-plot" viewBox="0 0 620 310" role="img" aria-label={`2D coordinate plot of ${robots.length}`}>
        <defs><pattern id="coordinate-grid" width="31" height="31" patternUnits="userSpaceOnUse"><path d="M31 0H0V31" fill="none" stroke="currentColor" strokeWidth=".7" opacity=".55" /></pattern></defs>
        <rect width="620" height="310" fill="url(#coordinate-grid)" /><line x1="48" y1="255" x2="568" y2="255" className="map-axis" /><line x1="48" y1="45" x2="48" y2="255" className="map-axis" />
        <text x="535" y="281" className="map-label">X · m</text><text x="14" y="43" className="map-label">Y · m</text>
        <text x="48" y="278" className="map-coordinate">{minX.toFixed(1)}</text><text x="540" y="278" className="map-coordinate">{maxX.toFixed(1)}</text><text x="13" y="251" className="map-coordinate">{maxY.toFixed(1)}</text><text x="13" y="58" className="map-coordinate">{minY.toFixed(1)}</text>
        {robots.map((robot) => { const x = plotX(robot.pose.x); const y = plotY(robot.pose.y); const isSelected = robot.id === selectedId; const size = Math.max(7, Math.min(19, robot.footprint_m * 13)); return <g key={robot.id} transform={`translate(${x} ${y})`} onClick={() => setSelectedId(robot.id)} className="plot-robot" role="button" tabIndex={0} aria-label={`Select ${robot.id}`} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') setSelectedId(robot.id); }}>
          <circle r={size + (isSelected ? 8 : 4)} fill="none" stroke={roleColor[robot.role]} strokeWidth={isSelected ? 2 : 1} opacity=".75" /><path d={`M ${-size * .65} ${-size * .55} L ${size} 0 L ${-size * .65} ${size * .55} Z`} fill={roleColor[robot.role]} transform={`rotate(${-robot.pose.yaw * 180 / Math.PI})`} /><text x={size + 10} y="4" className="robot-map-label">{robot.id}</text>
        </g>; })}
      </svg>
    </div>}
    {selected && <section className="selected-robot" aria-label="Selected robot" aria-live="polite"><div><span className="eyebrow">SELECTED ROBOT</span><strong>{selected.id}</strong></div><dl><div><dt>Position x</dt><dd>{selected.pose.x}</dd></div><div><dt>Position y</dt><dd>{selected.pose.y}</dd></div><div><dt>Yaw</dt><dd>{selected.pose.yaw}</dd></div><div><dt>Footprint</dt><dd>{selected.footprint_m} m</dd></div><div><dt>Last observation tick</dt><dd>{selected.last_observation_tick ?? 'Unknown'}</dd></div></dl></section>}
  </section>;
}
