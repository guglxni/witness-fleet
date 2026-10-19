import '@testing-library/jest-dom/vitest';
import {afterEach, beforeEach, vi} from 'vitest';
import {cleanup} from '@testing-library/react';
class MockObserver{observe(){} disconnect(){} unobserve(){} takeRecords(){return [] as IntersectionObserverEntry[];}}
Object.defineProperty(globalThis,'IntersectionObserver',{configurable:true,writable:true,value:MockObserver});
Object.defineProperty(window,'matchMedia',{configurable:true,writable:true,value:vi.fn((query:string)=>({matches:query.includes('reduced-motion'),media:query,onchange:null,addEventListener(){},removeEventListener(){},addListener(){},removeListener(){},dispatchEvent(){return true;}}))});
Object.defineProperty(window,'requestIdleCallback',{configurable:true,writable:true,value:()=>0});
Object.defineProperty(window,'cancelIdleCallback',{configurable:true,writable:true,value:()=>{}});
Object.defineProperty(window,'scrollTo',{configurable:true,writable:true,value:()=>{}});
beforeEach(()=>{vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});});
afterEach(()=>cleanup());
