declare module 'vanta/dist/vanta.net.min.js' {
  import type { WebGLRenderer } from 'three';
  interface VantaOptions { el: HTMLElement; THREE: { WebGLRenderer: typeof WebGLRenderer }; [key: string]: unknown }
  interface VantaNet { destroy(): void }
  const createEffect: (options: VantaOptions) => VantaNet;
  export type VantaEffect = VantaNet;
  export default createEffect;
}
