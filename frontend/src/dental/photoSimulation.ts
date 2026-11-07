export interface PhotoPoint { x: number; y: number }
export interface PhotoCrown {
  id: string; jaw: 'upper' | 'lower' | 'unknown'; points: PhotoPoint[]; fdi: number | null
  origin: 'manual' | 'ai-draft'; reviewed: boolean; target: { dx: number; dy: number; rotation: number }
}
export interface PhotoStudy {
  version: 'photo-study-v1'; crowns: PhotoCrown[]; blend: number; maskColor: string
  detection: { input_sha256: string; image_quality: string; possible_case_ids: string[] } | null
}
export const newPhotoStudy = (): PhotoStudy => ({ version: 'photo-study-v1', crowns: [], blend: 0, maskColor: '#533638', detection: null })
export const zeroTarget = () => ({ dx: 0, dy: 0, rotation: 0 })
export function polygonArea(points: PhotoPoint[]) { return Math.abs(points.reduce((sum, p, i) => { const q = points[(i + 1) % points.length]!; return sum + p.x * q.y - q.x * p.y }, 0)) / 2 }
function cross(a: PhotoPoint,b: PhotoPoint,c: PhotoPoint) { return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x) }
export function validOutline(points: PhotoPoint[]) {
  if (points.length < 4 || points.length > 12 || points.some(p=>!p||typeof p!=='object'||!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<0||p.x>1||p.y<0||p.y>1)) return false
  const area=polygonArea(points); if(area<.00001||area>.8)return false
  for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){
    if(j===i+1||(i===0&&j===points.length-1))continue
    const a=points[i]!,b=points[(i+1)%points.length]!,c=points[j]!,d=points[(j+1)%points.length]!
    if(cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0)return false
  }
  return true
}
export function crownBounds(crown:Pick<PhotoCrown,'points'>){const xs=crown.points.map(p=>p.x),ys=crown.points.map(p=>p.y);return {left:Math.min(...xs),right:Math.max(...xs),top:Math.min(...ys),bottom:Math.max(...ys),cx:(Math.min(...xs)+Math.max(...xs))/2,cy:(Math.min(...ys)+Math.max(...ys))/2}}
export function crownTransform(crown:PhotoCrown,blend:number,width=1000,height=1000){const b=crownBounds(crown),k=crown.reviewed?Math.max(0,Math.min(1,blend)):0;return `translate(${crown.target.dx*width*k} ${crown.target.dy*height*k}) rotate(${crown.target.rotation*k} ${b.cx*width} ${b.cy*height})`}
export function targetWithinPhoto(crown:PhotoCrown,width:number,height:number){
 const b=crownBounds(crown),angle=crown.target.rotation*Math.PI/180,cos=Math.cos(angle),sin=Math.sin(angle)
 return crown.points.every(p=>{const x=(p.x-b.cx)*width,y=(p.y-b.cy)*height,tx=b.cx*width+x*cos-y*sin+crown.target.dx*width,ty=b.cy*height+x*sin+y*cos+crown.target.dy*height;return Number.isFinite(tx)&&Number.isFinite(ty)&&tx>=0&&tx<=width&&ty>=0&&ty<=height})
}

/** A geometric sketch of rows selected by a reviewer, not a treatment recommendation or feasible tooth movement. */
export function arrangeVisibleCrowns(crowns:PhotoCrown[]){
  if(crowns.length<2||crowns.some(c=>!c.reviewed||c.jaw==='unknown'))throw new Error('Review each outline and assign its arch before arranging the visible crowns.')
  const targets:Record<string,{dx:number;dy:number;rotation:number}>={}
  for(const jaw of ['upper','lower'] as const){
    const row=crowns.filter(c=>c.jaw===jaw).map(c=>({c,b:crownBounds(c)})).sort((a,b)=>a.b.cx-b.b.cx)
    if(!row.length)continue
    const widths=row.map(({b})=>b.right-b.left),total=widths.reduce((a,b)=>a+b,0),center=row.reduce((n,{b})=>n+b.cx,0)/row.length,level=row.reduce((n,{b})=>n+(jaw==='upper'?b.bottom:b.top),0)/row.length
    let left=center-total/2
    for(const {c,b} of row){const w=b.right-b.left,h=b.bottom-b.top,desiredY=jaw==='upper'?level-h/2:level+h/2;const dx=left+w/2-b.cx,dy=desiredY-b.cy;if(Math.abs(dx)>.25||Math.abs(dy)>.25||left<0||left+w>1)throw new Error('This arrangement exceeds the photo. Adjust individual targets instead.');targets[c.id]={dx,dy,rotation:0};left+=w}
  }
  return targets
}
export function validateDetection(value:unknown,expectedHash:string): {image_quality:string;input_sha256:string;crowns:{jaw:PhotoCrown['jaw'];points:PhotoPoint[]}[];possible_case_ids:string[]} {
  if(!value||typeof value!=='object')throw new Error('The detector returned no usable result.')
  const r=value as Record<string,unknown>
  if(r.mode!=='photo-outline-draft'||r.clinical_validation!==false||r.input_sha256!==expectedHash||!['usable','insufficient','unsupported_view'].includes(String(r.image_quality))||!Array.isArray(r.crowns)||r.crowns.length>32||!Array.isArray(r.possible_case_ids)||r.possible_case_ids.length>3||r.possible_case_ids.some(id=>typeof id!=='string'))throw new Error('The detection response did not match this photograph.')
  const crowns=r.crowns.map(item=>{if(!item||typeof item!=='object'||!['upper','lower','unknown'].includes(item.jaw)||!Array.isArray(item.points)||!validOutline(item.points))throw new Error('A tooth outline was invalid. No draft was applied.');return {jaw:item.jaw as PhotoCrown['jaw'],points:item.points.map((p:PhotoPoint)=>({x:p.x,y:p.y}))}})
  if(r.image_quality!=='usable'&&(crowns.length||r.possible_case_ids.length))throw new Error('An unusable photograph cannot have accepted detections.')
  if(r.image_quality==='usable'&&!crowns.length)throw new Error('No usable visible crown outlines were returned.')
  return {image_quality:String(r.image_quality),input_sha256:expectedHash,crowns,possible_case_ids:r.possible_case_ids as string[]}
}
export async function preparePhoto(url:string){
  const image=new Image();image.src=url;await image.decode()
  const scale=Math.min(1,1024/Math.max(image.width,image.height)),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale))
  const context=canvas.getContext('2d');if(!context)throw new Error('The photo could not be prepared.')
  context.fillStyle='#fff';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height)
  let data_url=canvas.toDataURL('image/jpeg',.72);if(data_url.length>340000)data_url=canvas.toDataURL('image/jpeg',.45);if(data_url.length>340000)throw new Error('Choose a smaller or less detailed photograph for AI detection.')
  const binary=atob(data_url.split(',')[1]!),bytes=Uint8Array.from(binary,c=>c.charCodeAt(0)),digest=await crypto.subtle.digest('SHA-256',bytes),input_sha256=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('')
  return {data_url,width:canvas.width,height:canvas.height,input_sha256}
}
