/** Original schematic anatomical meshes. See ASSET_ATTRIBUTIONS.md; no downloaded textures. */
import * as T from 'three'
import type { RegionId } from '../types'
import type { PatientSide } from '../data/bodyParts'
import { buildEyeModel } from '../eye/model'

const material = (color: string, roughness = .5) => new T.MeshStandardMaterial({ color, roughness, metalness: .02 })
function ellipsoid(root: T.Group, name: string, position: number[], scale: number[], color: string, roughness = .5) {
  const mesh = new T.Mesh(new T.SphereGeometry(1, 64, 40), material(color, roughness))
  mesh.name = name; mesh.position.set(position[0]!, position[1]!, position[2]!); mesh.scale.set(scale[0]!, scale[1]!, scale[2]!)
  root.add(mesh); return mesh
}
function tube(root: T.Group, name: string, points: number[][], radius: number, color: string) {
  const curve = new T.CatmullRomCurve3(points.map(p => new T.Vector3(p[0], p[1], p[2])))
  const mesh = new T.Mesh(new T.TubeGeometry(curve, Math.max(32, points.length * 12), radius, 10, false), material(color))
  mesh.name = name; root.add(mesh); return mesh
}

function head(root: T.Group) {
  for (const side of [-1, 1]) {
    ellipsoid(root, 'Cerebral hemisphere', [side * .45, .14, 0], [.63, .84, .87], '#d99996')
    for (let i = 0; i < 15; i++) {
      const angle = i / 15 * Math.PI * 2
      const points = Array.from({ length: 20 }, (_, j) => {
        const p = .15 + j / 19 * (Math.PI - .3)
        return [side * .45 + .635 * Math.sin(p) * Math.cos(angle + .08 * Math.sin(j * 1.8)), .14 + .845 * Math.cos(p), .875 * Math.sin(p) * Math.sin(angle + .08 * Math.sin(j * 1.8))]
      })
      tube(root, 'Cortical fold', points, .025, '#b97578')
    }
  }
  ellipsoid(root, 'Cerebellum', [0, -.72, -.45], [.66, .35, .42], '#bd858a')
  tube(root, 'Brainstem', [[0, -.47, -.12], [0, -.9, -.12], [.05, -1.24, -.18]], .14, '#e6cbb3')
}
function chest(root: T.Group) {
  for (const side of [-1, 1]) {
    const lung = ellipsoid(root, side === 1 ? 'Left lung' : 'Right lung', [side * .57, .07, 0], [.49, .9, .4], '#d99399'); lung.rotation.z = side * -.12
    tube(root, 'Bronchus', [[0, .8, .2], [side * .3, .45, .22], [side * .55, .16, .25]], .065, '#e7c8ae')
    for (let i = 0; i < 7; i++) {
      const y = .79 - i * .24, width = .74 + Math.sin(i / 7 * Math.PI) * .32
      tube(root, 'Rib', [[side * .08, y, .55], [side * width * .68, y + .1, .61], [side * width, y + .05, .1], [side * width * .8, y + .12, -.43], [side * .12, y + .18, -.5]], .036, '#dfcfb1')
    }
  }
  const heart = ellipsoid(root, 'Heart', [.14, -.28, .46], [.31, .45, .28], '#ae4d58'); heart.rotation.z = -.35
  tube(root, 'Aorta', [[.15, -.1, .48], [.15, .37, .4], [-.03, .47, .35], [-.2, .22, .3]], .085, '#b65354')
  tube(root, 'Trachea', [[0, 1.24, .1], [0, .8, .12], [0, .55, .15]], .1, '#e2c5ae')
  tube(root, 'Sternum', [[0, .85, .6], [0, .25, .65], [0, -.5, .57]], .055, '#eadbbf')
}
function abdomen(root: T.Group) {
  ellipsoid(root, 'Liver', [-.34, .65, .05], [.76, .36, .41], '#a65a50').rotation.z = -.12
  ellipsoid(root, 'Stomach', [.5, .36, .14], [.38, .48, .3], '#dfa09a').rotation.z = -.35
  tube(root, 'Esophagus', [[.32, 1.13, -.02], [.32, .84, .02], [.44, .56, .1]], .075, '#dea395')
  for (const side of [-1, 1]) ellipsoid(root, 'Kidney', [side * .72, -.07, -.31], [.22, .37, .19], '#a55155').rotation.z = side * .23
  const loops = Array.from({ length: 64 }, (_, i) => [Math.sin(i * .57) * .52, .06 - i / 64 * .85, .21 + Math.cos(i * .57) * .13])
  tube(root, 'Small intestine', loops, .065, '#dfa094')
  tube(root, 'Large intestine', [[-.78, -.78, .08], [-.82, -.1, .09], [-.67, .17, .1], [0, .14, .2], [.72, .18, .1], [.82, -.15, .08], [.72, -.82, .08], [.2, -.96, .12], [0, -1.2, .07]], .115, '#bd7e79')
  ellipsoid(root, 'Gallbladder', [-.36, .37, .35], [.11, .2, .09], '#899d73')
  ellipsoid(root, 'Pancreas', [.1, .1, -.05], [.4, .09, .1], '#d9b275')
}
function limb(root: T.Group, leg: boolean) {
  const upper = leg ? 'Femur' : 'Humerus', lower = leg ? 'Tibia' : 'Ulna', second = leg ? 'Fibula' : 'Radius'
  tube(root, upper, [[0, 1.4, 0], [.06, .8, 0], [0, .05, 0]], .09, '#efdfbd')
  for (const y of [1.4, .05, -1.4]) ellipsoid(root, 'Bone articulation', [0, y, 0], [.15, .14, .14], '#e9d7b4')
  tube(root, lower, [[-.07, .05, 0], [-.12, -.65, 0], [-.08, -1.4, 0]], .07, '#f0dfbd')
  tube(root, second, [[.13, 0, 0], [.18, -.7, 0], [.11, -1.4, 0]], .045, '#e3d1b0')
  ellipsoid(root, leg ? 'Quadriceps' : 'Biceps', [-.14, .78, .14], [leg ? .31 : .23, .64, .17], '#c27970').rotation.z = -.08
  ellipsoid(root, leg ? 'Hamstrings' : 'Triceps', [.16, .78, -.13], [.2, .6, .16], '#ae645f')
  ellipsoid(root, leg ? 'Gastrocnemius' : 'Forearm flexors', [-.12, -.56, .1], [.2, .5, .16], '#ca8580')
  if (leg) ellipsoid(root, 'Patella', [0, .02, .2], [.14, .17, .08], '#efdfc6')
  else {
    ellipsoid(root, 'Hand bones', [0, -1.57, 0], [.16, .2, .065], '#ead8b8')
    for (let i = 0; i < 5; i++) tube(root, 'Phalanges', [[-.14 + i * .065, -1.66, 0], [-.19 + i * .09, -1.96 + Math.abs(i - 2) * .07, 0]], .025, '#ecdbb9')
  }
  tube(root, 'Artery', [[.25, 1.4, .12], [.27, .7, .2], [.19, 0, .22], [.25, -.7, .18], [.12, -1.4, .14]], .026, '#b94e55')
  tube(root, 'Vein', [[.32, 1.4, .11], [.34, .65, .15], [.3, -.1, .16], [.32, -.8, .14], [.2, -1.4, .12]], .022, '#638bac')
  root.position.y = .2
}
export function buildAnatomy(id: RegionId, side: PatientSide): T.Group {
  if (id === 'eyes') return buildEyeModel(side, 'transparent')
  const root = new T.Group(); root.name = `${side}-${id}`
  if (id === 'head') head(root)
  else if (id === 'chest') chest(root)
  else if (id === 'abdomen') abdomen(root)
  else limb(root, id === 'legs')
  // Patient left is viewer right in an anterior view. Mirror only paired anatomy.
  if (['eyes', 'arms', 'legs'].includes(id) && side === 'right') root.scale.x = -1
  return root
}
