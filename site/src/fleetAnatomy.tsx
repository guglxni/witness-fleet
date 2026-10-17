import { useMemo } from 'react';
import { depthOf, fitProjection, iso, pathOf, roundedPlan, slabOf, topTicks, type FitOptions, type Plan, type Point3, type Projection, type SolidPaths } from './anatomy-kit';

const WORLD_W=244;
const WORLD_D=136;
const WIDTH=840;
const HEIGHT=575;
const FLOOR:Plan={x:-WORLD_W/2,y:-WORLD_D/2,w:WORLD_W,d:WORLD_D,r:10};
const PROJECTION:FitOptions={pad:46,azimuth:46,elevation:31};
export const STORY_PHASES=[
 {key:'authority',name:'Authority check',short:'Graph authority',status:'AUTHORIZED SCOPE',tint:'#ca7623',description:'FalkorDB checks who can act, what evidence still holds, and which policy release is in scope.'},
 {key:'recovery',name:'MuJoCo recovery',short:'MuJoCo recovery',status:'SIMULATION RECEIPT',tint:'#cc682b',description:'The recovery robot moves the obstruction in simulation; this mechanism view is illustrative, not telemetry.'},
 {key:'release',name:'Configured demo-owner release',short:'Owner release',status:'SCRIPTED DEMO OWNER',tint:'#ae6a20',description:'A configured demo-owner release is required before the courier route is unlocked.'},
 {key:'sensing',name:'Fresh courier sensing',short:'Courier sensing',status:'FRESH OBSERVATION',tint:'#71845a',description:'The courier must observe again inside the permitted sensing horizon before delivery proceeds.'},
 {key:'delivery',name:'Evidence-backed delivery',short:'Delivery',status:'MISSION COMPLETE',tint:'#536f58',description:'The mission controller reports completion after the released courier task is verified.'},
] as const;
export type StoryPhaseKey=typeof STORY_PHASES[number]['key'];
interface Shape {id:string;label:string;assembly:string;plan:Plan;bottom:number;height:number;tone:'low'|'mid'|'high'|'lit';phase?:number;visibleAt?:number;geometry?:SolidPaths}
const SHAPES:Shape[]=[
{id:'rubber-foot-near-left',label:'Front-left isolation foot',assembly:'chassis',plan:{x:-100,y:50,w:19,d:15,r:5},bottom:-14,height:7,tone:'low'},
{id:'rubber-foot-far-left',label:'Rear-left isolation foot',assembly:'chassis',plan:{x:-100,y:-67,w:19,d:15,r:5},bottom:-14,height:7,tone:'low'},
{id:'rubber-foot-near-right',label:'Front-right isolation foot',assembly:'chassis',plan:{x:81,y:50,w:19,d:15,r:5},bottom:-14,height:7,tone:'low'},
{id:'rubber-foot-far-right',label:'Rear-right isolation foot',assembly:'chassis',plan:{x:81,y:-67,w:19,d:15,r:5},bottom:-14,height:7,tone:'low'},
{id:'base-cast',label:'Lower cast bedplate',assembly:'chassis',plan:{x:-120,y:-71,w:240,d:136,r:10},bottom:-7,height:11,tone:'mid'},
{id:'base-inset-track',label:'Bedplate machined perimeter groove',assembly:'chassis',plan:{x:-113,y:-64,w:226,d:122,r:8},bottom:4.15,height:.2,tone:'low'},
{id:'lower-ruler-bed',label:'Engraved lower ruler strip',assembly:'chassis',plan:{x:-98,y:44,w:196,d:11,r:2},bottom:4.2,height:1,tone:'low'},
{id:'base-label',label:'Fixture serial plate',assembly:'chassis',plan:{x:-105,y:-63,w:42,d:10,r:2},bottom:4.2,height:1,tone:'low'},
{id:'plinth-left',label:'Left riser block',assembly:'chassis',plan:{x:-98,y:-51,w:9,d:101,r:2},bottom:4,height:8,tone:'mid'},
{id:'plinth-right',label:'Right riser block',assembly:'chassis',plan:{x:89,y:-51,w:9,d:101,r:2},bottom:4,height:8,tone:'mid'},
{id:'recovery-rail-foot-left',label:'Recovery rail left pedestal',assembly:'recovery',plan:{x:-78,y:-48,w:17,d:17,r:3},bottom:12,height:8,tone:'mid'},
{id:'recovery-rail-foot-right',label:'Recovery rail right pedestal',assembly:'recovery',plan:{x:60,y:-48,w:17,d:17,r:3},bottom:12,height:8,tone:'mid'},
{id:'recovery-pillar-left',label:'Recovery gantry left stanchion',assembly:'recovery',plan:{x:-75,y:-45,w:11,d:11,r:2},bottom:20,height:55,tone:'mid'},
{id:'recovery-pillar-right',label:'Recovery gantry right stanchion',assembly:'recovery',plan:{x:63,y:-45,w:11,d:11,r:2},bottom:20,height:55,tone:'mid'},
{id:'gantry-crossbar',label:'Machined recovery gantry crossbar',assembly:'recovery',plan:{x:-77,y:-47,w:155,d:15,r:4},bottom:72,height:11,tone:'high'},
{id:'gantry-inset-face',label:'Gantry face inset',assembly:'recovery',plan:{x:-68,y:-45,w:137,d:2,r:1},bottom:77,height:2,tone:'low'},
{id:'upper-ruler',label:'Recovery gantry ruler strip',assembly:'recovery',plan:{x:-62,y:-42,w:121,d:3,r:1},bottom:81,height:1,tone:'lit',phase:1},
{id:'travel-end-stop-left',label:'Recovery travel end stop left',assembly:'recovery',plan:{x:-77,y:-46,w:5,d:13,r:1},bottom:81,height:7,tone:'high'},
{id:'travel-end-stop-right',label:'Recovery travel end stop right',assembly:'recovery',plan:{x:71,y:-46,w:5,d:13,r:1},bottom:81,height:7,tone:'high'},
{id:'mujoco-carriage-plate',label:'Recovery carriage, simulated mechanism',assembly:'recovery',plan:{x:11,y:-49,w:42,d:21,r:5},bottom:84,height:7,tone:'mid'},
{id:'carriage-bushing-a',label:'Carriage guide bushing A',assembly:'recovery',plan:{x:16,y:-47,w:9,d:17,r:4},bottom:82,height:11,tone:'low'},
{id:'carriage-bushing-b',label:'Carriage guide bushing B',assembly:'recovery',plan:{x:39,y:-47,w:9,d:17,r:4},bottom:82,height:11,tone:'low'},
{id:'tool-mount',label:'Recovery end-effector mount',assembly:'recovery',plan:{x:22,y:-35,w:20,d:13,r:3},bottom:91,height:10,tone:'high'},
{id:'telescopic-cylinder',label:'Recovery telescopic cylinder',assembly:'recovery',plan:{x:28,y:-32,w:9,d:9,r:4},bottom:101,height:18,tone:'mid'},
{id:'cylinder-collar',label:'Recovery piston gland collar',assembly:'recovery',plan:{x:27,y:-33,w:11,d:11,r:5},bottom:115,height:3,tone:'low'},
{id:'recovery-piston-rod',label:'Recovery piston rod',assembly:'recovery',plan:{x:29,y:-32,w:7,d:7,r:3},bottom:118,height:19,tone:'high'},
{id:'wedge-head',label:'Obstruction clearing wedge',assembly:'recovery',plan:{x:24,y:-29,w:17,d:16,r:6},bottom:135,height:8,tone:'lit',phase:1},
{id:'wedge-face-inlay',label:'Wedge polished contact face',assembly:'recovery',plan:{x:29,y:-28,w:8,d:7,r:3},bottom:143,height:1,tone:'high'},
{id:'recovery-stop-block',label:'Recovery travel stop block',assembly:'recovery',plan:{x:49,y:-44,w:10,d:10,r:2},bottom:84,height:9,tone:'mid'},
{id:'tamper-guard-left',label:'Recovery bellows guard left',assembly:'recovery',plan:{x:7,y:-46,w:4,d:16,r:2},bottom:84,height:8,tone:'low'},
{id:'tamper-guard-right',label:'Recovery bellows guard right',assembly:'recovery',plan:{x:54,y:-46,w:4,d:16,r:2},bottom:84,height:8,tone:'low'},
{id:'evidence-tape-guide',label:'Sensor readout support rail',assembly:'evidence',plan:{x:-51,y:-24,w:102,d:8,r:3},bottom:15,height:7,tone:'mid'},
{id:'reader-support-left',label:'Readout left support',assembly:'evidence',plan:{x:-44,y:-21,w:8,d:8,r:3},bottom:22,height:38,tone:'high'},
{id:'reader-support-right',label:'Readout right support',assembly:'evidence',plan:{x:36,y:-21,w:8,d:8,r:3},bottom:22,height:38,tone:'high'},
{id:'display-housing',label:'Provenance reader housing',assembly:'evidence',plan:{x:-50,y:-31,w:100,d:15,r:5},bottom:59,height:12,tone:'mid'},
{id:'display-bezel',label:'Provenance reader bezel',assembly:'evidence',plan:{x:-46,y:-29,w:92,d:9,r:3},bottom:71,height:2,tone:'low'},
{id:'display-glass',label:'Matte reader glass',assembly:'evidence',plan:{x:-43,y:-28,w:86,d:7,r:2},bottom:73,height:.6,tone:'high'},
{id:'display-led-one',label:'Graph authority status indicator',assembly:'evidence',plan:{x:-35,y:-26,w:17,d:2,r:1},bottom:74,height:.6,tone:'lit',phase:0},
{id:'display-led-two',label:'Evidence freshness indicator',assembly:'evidence',plan:{x:-9,y:-26,w:17,d:2,r:1},bottom:74,height:.6,tone:'high',phase:3},
{id:'display-led-three',label:'Release scope indicator',assembly:'evidence',plan:{x:18,y:-26,w:17,d:2,r:1},bottom:74,height:.6,tone:'high',phase:2},
{id:'reader-selector',label:'Physical reader selection knob',assembly:'evidence',plan:{x:41,y:-14,w:10,d:10,r:5},bottom:58,height:6,tone:'high'},
{id:'reader-knob-cap',label:'Reader knurled knob cap',assembly:'evidence',plan:{x:43,y:-12,w:6,d:6,r:3},bottom:64,height:2,tone:'lit',phase:0},
{id:'provenance-latch',label:'Physical evidence-latch lever',assembly:'evidence',plan:{x:-5,y:-10,w:29,d:5,r:2},bottom:78,height:4,tone:'high',phase:0},
{id:'latch-pin',label:'Evidence-latch pivot pin',assembly:'evidence',plan:{x:8,y:-9,w:5,d:5,r:3},bottom:81,height:2,tone:'low'},
{id:'scope-key',label:'Release scope brass key',assembly:'release',plan:{x:67,y:16,w:23,d:15,r:7},bottom:4.5,height:3,tone:'lit',phase:2},
{id:'scope-key-bit-one',label:'Release key bit one',assembly:'release',plan:{x:84,y:14,w:8,d:3,r:1},bottom:3,height:2,tone:'high'},
{id:'scope-key-bit-two',label:'Release key bit two',assembly:'release',plan:{x:88,y:18,w:4,d:7,r:1},bottom:3,height:2,tone:'mid'},
{id:'key-docking-socket',label:'Configured owner release socket',assembly:'release',plan:{x:70,y:20,w:18,d:13,r:6},bottom:5.6,height:2,tone:'mid'},
{id:'scope-seal',label:'Policy-bound release seal',assembly:'release',plan:{x:74,y:22,w:9,d:6,r:3},bottom:7.6,height:.8,tone:'lit',phase:2},
{id:'release-safety-cover',label:'Guarded owner release cover',assembly:'release',plan:{x:57,y:31,w:33,d:14,r:5},bottom:4.4,height:4,tone:'high',phase:2},
{id:'cover-hinge',label:'Release-cover hinge pin',assembly:'release',plan:{x:59,y:33,w:5,d:10,r:2},bottom:8.4,height:2,tone:'low'},
{id:'release-interlock',label:'Mechanical courier interlock',assembly:'release',plan:{x:45,y:29,w:9,d:13,r:3},bottom:10,height:8,tone:'mid',phase:2},
{id:'release-lamp-ring',label:'Release-gate indicator collar',assembly:'release',plan:{x:93,y:30,w:11,d:11,r:5},bottom:5,height:2,tone:'low'},
{id:'release-lamp-lens',label:'Release-gate lens',assembly:'release',plan:{x:95,y:32,w:7,d:7,r:3},bottom:7,height:.6,tone:'lit',phase:2},
{id:'fresh-sensing-tray',label:'Fresh sensing tray',assembly:'sensing',plan:{x:-19,y:1,w:46,d:32,r:6},bottom:4.5,height:3,tone:'high',phase:3},
{id:'tray-floor-inlay',label:'Sensing tray floor inlay',assembly:'sensing',plan:{x:-14,y:5,w:36,d:23,r:4},bottom:7.5,height:.6,tone:'low'},
{id:'courier-sensor-canister',label:'Courier sensor canister',assembly:'sensing',plan:{x:-12,y:7,w:13,d:13,r:6},bottom:8,height:13,tone:'mid',phase:3},
{id:'sensor-canister-cap',label:'Fresh sensing lens bezel',assembly:'sensing',plan:{x:-11,y:8,w:11,d:11,r:5},bottom:21,height:2,tone:'high',phase:3},
{id:'sensor-lens',label:'Fresh sensing aperture',assembly:'sensing',plan:{x:-9,y:10,w:7,d:7,r:4},bottom:23,height:.6,tone:'lit',phase:3},
{id:'sensor-joint-hub',label:'Courier sensor joint hub',assembly:'sensing',plan:{x:8,y:8,w:11,d:11,r:5},bottom:8,height:13,tone:'high'},
{id:'sensor-joint-upper',label:'Courier sensor tilt joint',assembly:'sensing',plan:{x:10,y:10,w:7,d:7,r:3},bottom:21,height:7,tone:'mid'},
{id:'sensing-datum-post',label:'Sensing reference datum pin',assembly:'sensing',plan:{x:13,y:28,w:4,d:4,r:2},bottom:8,height:15,tone:'high'},
{id:'courier-roadway',label:'Verified courier delivery lane',assembly:'sensing',plan:{x:30,y:-10,w:73,d:27,r:5},bottom:4.5,height:1,tone:'low',phase:4},
{id:'courier-lane-divider',label:'Courier lane painted divider',assembly:'sensing',plan:{x:37,y:2,w:59,d:2,r:1},bottom:5.6,height:.35,tone:'lit',phase:4},
{id:'lane-end-gate-left',label:'Courier approach guide left',assembly:'sensing',plan:{x:35,y:-10,w:6,d:26,r:2},bottom:5.6,height:4,tone:'mid'},
{id:'lane-end-gate-right',label:'Courier approach guide right',assembly:'sensing',plan:{x:96,y:-10,w:6,d:26,r:2},bottom:5.6,height:4,tone:'mid'},
{id:'courier-carriage',label:'Courier robot chassis',assembly:'courier',plan:{x:46,y:-6,w:30,d:24,r:8},bottom:7,height:8,tone:'mid',visibleAt:3},
{id:'courier-wheel-left',label:'Courier wheel left',assembly:'courier',plan:{x:49,y:-7,w:7,d:26,r:3},bottom:4,height:5,tone:'low',visibleAt:3},
{id:'courier-wheel-right',label:'Courier wheel right',assembly:'courier',plan:{x:68,y:-7,w:7,d:26,r:3},bottom:4,height:5,tone:'low',visibleAt:3},
{id:'courier-payload-cradle',label:'Courier payload cradle',assembly:'courier',plan:{x:52,y:0,w:18,d:12,r:4},bottom:15,height:3,tone:'high',visibleAt:3},
{id:'delivery-payload',label:'Evidence-backed delivery payload',assembly:'courier',plan:{x:54,y:2,w:14,d:8,r:3},bottom:18,height:7,tone:'lit',phase:4,visibleAt:3},
{id:'courier-antenna',label:'Courier state receiver mast',assembly:'courier',plan:{x:70,y:4,w:3,d:3,r:2},bottom:15,height:14,tone:'high',visibleAt:3},
{id:'courier-antenna-cap',label:'Courier receiver end cap',assembly:'courier',plan:{x:69,y:3,w:5,d:5,r:3},bottom:29,height:2,tone:'lit',phase:4,visibleAt:3},
];
export const ANATOMY_PART_COUNT=SHAPES.length+1;
function buildGeometry(width:number,height:number){
 const points:Point3[]=[];
 for(const shape of SHAPES)for(const [x,y]of roundedPlan(shape.plan,5))points.push([x,y,shape.bottom],[x,y,shape.bottom+shape.height]);
 for(const[x,y]of roundedPlan(FLOOR,6))points.push([x,y,-14],[x,y,0]);
 const projection:Projection=fitProjection(points,width,height,PROJECTION);
 const ordered=SHAPES.map(shape=>({...shape,geometry:slabOf(shape.plan,shape.bottom,shape.height,projection,shape.plan.r>3?10:6,.65)})).sort((a,b)=>depthOf([a.plan.x+a.plan.w/2,a.plan.y+a.plan.d/2,a.bottom+a.height/2],projection)-depthOf([b.plan.x+b.plan.w/2,b.plan.y+b.plan.d/2,b.bottom+b.height/2],projection));
 const ticks=topTicks(-94,94,4,5,54,4.25,[2,4],projection,'x');
 const floor=slabOf(FLOOR,-7,7,projection,10,1.1);
 const groove=pathOf(roundedPlan({x:-115,y:-66,w:230,d:126,r:8},9).map(([x,y])=>iso([x,y,.16],projection)),true);
 const gridX=Array.from({length:23},(_,i)=>-110+i*10).map(x=>pathOf([iso([x,-63,.08],projection),iso([x,61,.08],projection)]));
 const gridY=Array.from({length:13},(_,i)=>-60+i*10).map(y=>pathOf([iso([-114,y,.08],projection),iso([114,y,.08],projection)]));
 const screws=[[-111,-62],[-111,56],[111,-62],[111,56],[-88,-48],[88,-48],[-54,49],[54,49],[0,-48],[0,49]]as const;
 const screwCenters=screws.map(([x,y])=>iso([x,y,4.1],projection));
 const screwRings=screws.map(([x,y])=>pathOf(roundedPlan({x:x-1.6,y:y-1.6,w:3.2,d:3.2,r:1.5},8).map(([px,py])=>iso([px,py,4.1],projection)),true));
 return{projection,ordered,ticks,floor,groove,gridX,gridY,screwCenters,screwRings,route:pathOf([iso([35,-19,8],projection),iso([44,-6,20],projection),iso([62,0,14],projection)])};
}
export function useFleetAnatomy(){return useMemo(()=>buildGeometry(WIDTH,HEIGHT),[])}
export type FleetAnatomy=ReturnType<typeof buildGeometry>;
