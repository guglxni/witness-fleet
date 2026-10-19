import {describe,it,expect} from 'vitest';
import {OrthographicCamera,Vector3} from 'three';
import {applyCameraView} from '../src/CoordinateSpace';
describe('scientific camera coordinates',()=>{it('top projects +X right and +Y up without a degenerate basis',()=>{const c=new OrthographicCamera(-8,8,8,-8,.1,100);applyCameraView(c,'top');c.updateMatrixWorld();const o=new Vector3(0,0,0).project(c),x=new Vector3(1,0,0).project(c),y=new Vector3(0,1,0).project(c);expect(x.x).toBeGreaterThan(o.x);expect(Math.abs(x.y-o.y)).toBeLessThan(1e-5);expect(y.y).toBeGreaterThan(o.y);expect(Math.abs(y.x-o.x)).toBeLessThan(1e-5)})})
