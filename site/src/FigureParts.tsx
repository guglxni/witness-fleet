import type { Flat, SolidPaths, Tone } from './anatomy-kit';

export function FigureSolid({paths,tone='hi',className}:{paths:SolidPaths;tone?:Tone;className?:string}) {
 return <g className={`anatomy-solid ${className??''}`} data-tone={tone}><path className="anatomy-fill" d={paths.fill}/>{paths.shades.map((d,index)=>d?<path key={index} className="anatomy-shade" data-shade={index} d={d}/>:null)}<path className="anatomy-top" d={paths.top}/><path className="anatomy-crease" d={paths.crease}/>{paths.bevel?<path className="anatomy-bevel" d={paths.bevel}/>:null}<path className="anatomy-outline" d={paths.outline}/></g>;
}
export function FigureDots({points,tone='mid',size=.5}:{points:Flat[];tone?:Tone;size?:number}) {return <g className={`anatomy-dots tone-${tone}`}>{points.map(([x,y],index)=><circle key={index} cx={Math.round(x*100)/100} cy={Math.round(y*100)/100} r={size}/>)}</g>;}
