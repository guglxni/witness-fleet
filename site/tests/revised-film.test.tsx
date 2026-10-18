// @ts-expect-error Node built-ins are available in Vitest; this project omits @types/node.
import {createHash} from 'node:crypto';
// @ts-expect-error Node built-ins are available in Vitest; this project omits @types/node.
import {readFileSync,statSync} from 'node:fs';
declare const process:{cwd:()=>string};
import {expect,it} from 'vitest';

it('retains archived film assets byte-for-byte without exposing cut selection',()=>{
 const archives={
  'public/media/campaign/product-ad.mp4':'89ea3f6151735c75e42cabc998e5ce8842efdf397612dd929987f3d59b6434fe',
  'public/media/campaign/product-ad-iv.mp4':'6a886d9dc33d2639ea24b7c1ebdc499dd4566f90ee0a9149496e5e209b6546f2',
  'public/media/campaign/product-ad-falkordb.mp4':'658bc4f6f96ccb4a4b14fa20a4414ada9d4ee54b24b1a4cf069eb752f3c9e772',
  'public/media/campaign/film-ii.mp4':'ba5ef6643062b0d9158042d13903bab694cfce2dac4a88be50e01561e69924a3',
  'public/media/launch.mp4':'1f781361d281df09999c7051d066c1d610ced861c6932a16fad2a8afe78bc869',
  'public/media/campaign/product-ad.vtt':'29b3c8146254230f7fe9effd1b23ddbc4df95c5bee4874bf3a015f6a92ba8ed0',
  'public/media/campaign/product-ad-iv.vtt':'64c55bb73b802f24f0184c404ae01782d06cb78bc07500adb044bc14f6f7dc3f',
  'public/media/campaign/product-ad-falkordb.vtt':'64c55bb73b802f24f0184c404ae01782d06cb78bc07500adb044bc14f6f7dc3f',
  'public/media/campaign/film-ii.vtt':'4d9d55506807f22e39da35c60404f0de571b3737373df35ccd3904b8c0c4f5b5',
  'public/media/captions.vtt':'d85937638bb9d0603d278e58ef1b1877d9a2e72ff9aa44e75cb4d705ac9a2e8d',
 };
 for(const [path,expectedHash] of Object.entries(archives)){
  const asset=`${process.cwd()}/${path}`;
  expect(statSync(asset).size).toBeGreaterThan(0);
  expect(createHash('sha256').update(readFileSync(asset)).digest('hex')).toBe(expectedHash);
 }
});
