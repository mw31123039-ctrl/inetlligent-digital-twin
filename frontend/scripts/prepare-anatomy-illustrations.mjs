// Original vector artwork, released under MIT (public/illustrations/LICENSE.txt).
// Run from any directory: node scripts/prepare-anatomy-illustrations.mjs
import { mkdir, writeFile } from 'node:fs/promises'
const directory = new URL('../public/illustrations/', import.meta.url)
await mkdir(directory, { recursive: true })
const path = (d, fill = 'none', stroke = '#bd7e7b', width = 3) => `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`
const ellipse = (x, y, rx, ry, fill, stroke = '#b97e77') => `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`
const label = (name, x, y, tx, ty) => `<g fill="#446575" font-family="Segoe UI,Arial,sans-serif" font-size="16">${path(`M${x} ${y}L${tx > 380 ? tx - 10 : tx + 100} ${ty - 5}`, 'none', '#80b3b5', 1.5)}<circle cx="${x}" cy="${y}" r="3" fill="#008e99"/><text x="${tx}" y="${ty}">${name}</text></g>`
function eye(view) {
  if (view === 'front') return ellipse(380, 265, 167, 153, 'url(#sclera)', '#cec1b9') +
    Array.from({ length: 24 }, (_, i) => { const a = i / 24 * Math.PI * 2; return path(`M${380 + Math.cos(a) * 165} ${265 + Math.sin(a) * 151}Q${380 + Math.cos(a + .07) * 128} ${265 + Math.sin(a + .07) * 118} ${380 + Math.cos(a) * 98} ${265 + Math.sin(a) * 96}`, 'none', '#d3a4a0', 1.2) }).join('') +
    ellipse(380, 265, 77, 77, 'url(#iris)', '#315b61') + Array.from({ length: 100 }, (_, i) => { const a = i / 100 * Math.PI * 2; return path(`M${380 + Math.cos(a) * 32} ${265 + Math.sin(a) * 32}L${380 + Math.cos(a + .025) * 73} ${265 + Math.sin(a + .025) * 73}`, 'none', i % 3 ? '#8dbba5' : '#d2bd87', 1.3) }).join('') + ellipse(380, 265, 29, 29, '#142b33', '#30515b') + ellipse(399, 244, 11, 8, '#ffffffbb', 'none') + label('Sclera', 490, 190, 575, 150) + label('Iris', 440, 292, 575, 330) + label('Pupil', 380, 265, 55, 220) + label('Cornea', 380, 185, 55, 140)
  const section = view === 'section'
  return path('M520 234L653 208L661 246L523 280Z', '#e0c589', '#bd9d65') +
    ellipse(372, 262, 159, 151, 'url(#sclera)', '#c1afa2') +
    (section ? ellipse(372, 262, 149, 141, '#e8cac1', '#b57570') + ellipse(372, 262, 140, 133, '#f8eee0', '#d7a66d') + path('M250 174Q205 262 250 350Q176 335 176 262Q176 188 250 174Z', '#d9f0ef', '#80b3ba') + ellipse(251, 262, 23, 63, '#c5e0df', '#88aeb3') + path('M222 199L222 236M222 288L222 325', 'none', '#428184', 12) + ellipse(480, 262, 9, 12, '#e4b46e', '#bb8960') + label('Lens', 252, 262, 49, 370) + label('Retina', 464, 173, 550, 121) + label('Vitreous body', 367, 262, 319, 468) + label('Iris', 222, 215, 48, 122) : path('M246 169Q173 262 246 355Q202 352 190 262Q202 172 246 169Z', '#cae5e6', '#779fa8') + ellipse(216, 262, 15, 69, '#4f8589', '#396572') + path('M325 121Q409 84 486 153L486 172Q398 117 334 144Z', '#c8897d', '#ae6e6b') + path('M325 399Q408 438 488 371L485 348Q403 402 331 377Z', '#c8897d', '#ae6e6b') + label('Sclera', 391, 136, 345, 75) + label('Eye muscle', 408, 408, 385, 470)) + label('Cornea', 184, 264, 36, 258) + label('Optic nerve', 600, 232, 564, 355)
}
function head(view) {
  const side = view !== 'front'
  let s = side ? ellipse(372, 236, 150, 121, '#e1a9a1') : ellipse(312, 242, 81, 128, '#e1a9a1') + ellipse(467, 242, 81, 128, '#e1a9a1')
  for (let i = 0; i < 18; i++) {
    const x = 245 + i * 15, y = 180 + (i % 3) * 10
    s += path(`M${x} ${y}q-22 22 0 42q22 20 0 40q-18 22 0 35`, 'none', '#b57577', 3)
  }
  s += ellipse(426, 351, 65, 37, '#c68d8e') + path('M363 326Q350 375 372 424L398 424Q372 377 392 337Z', '#e0c5ac', '#b79585')
  if (view === 'section') s += path('M274 252Q358 176 449 248L428 276Q358 220 302 274Z', '#f3dac0', '#bf9290') + ellipse(375, 279, 40, 31, '#c78e8d')
  return s + label('Cerebrum', 414, 171, 551, 121) + label('Cerebellum', 453, 348, 550, 399) + label('Brainstem', 381, 400, 68, 440) + (view === 'section' ? label('Corpus callosum', 359, 228, 35, 160) : '')
}
function chest(view) {
  const side = view === 'side'
  let s = path('M363 83L363 171L321 210M383 83L383 171L425 210', 'none', '#c7ad8e', 16)
  s += path('M344 158Q266 130 236 263Q219 348 313 376L346 352Z', '#d79ca1', '#b97980')
  if (!side) s += path('M408 158Q492 130 518 263Q536 348 437 376L402 352Z', '#dfaaac', '#b97980')
  s += path('M375 252C324 203 322 322 395 356C447 308 432 217 397 241Z', '#b65d64', '#954853')
  s += path('M389 250Q373 193 411 194Q438 198 427 225', 'none', '#bd6565', 13)
  if (view !== 'section') for (let i = 0; i < 7; i++) { const y = 162 + i * 28; s += path(`M374 ${y + 11}Q${side ? 270 : 194} ${y - 40} 244 ${y + 26}M388 ${y + 11}Q551 ${y - 40} 508 ${y + 26}`, 'none', '#d8c8a7', 7) }
  else s += path('M253 390Q380 353 504 390L504 408Q380 381 253 408Z', '#d8a48f', '#b98c7e')
  return s + label('Trachea', 373, 106, 50, 100) + label('Lung', 281, 275, 50, 285) + label('Heart', 397, 295, 559, 330) + label(view === 'section' ? 'Diaphragm' : 'Rib cage', view === 'section' ? 453 : 481, view === 'section' ? 391 : 190, 560, 175)
}
function abdomen(view) {
  const section = view === 'section'
  let s = path('M219 163Q315 112 432 151L398 224Q296 236 219 199Z', '#ac6557', '#8f524c') +
    path('M432 155Q492 146 493 224Q509 281 448 286Q397 281 405 238Q448 239 432 155Z', '#dda79e') +
    path('M411 101L414 173', 'none', '#dcada1', 15) + ellipse(283, 244, 24, 43, '#a45d5b') + ellipse(473, 297, 24, 43, '#a45d5b')
  for (let i = 0; i < 7; i++) s += path(`M310 ${274 + i * 14}C240 ${249 + i * 14} 440 ${249 + i * 14} 438 ${285 + i * 14}S280 ${295 + i * 14} 310 ${274 + i * 14}`, 'none', '#dda193', 10)
  s += path('M258 383L251 282Q251 254 288 257L460 260Q488 260 488 297L484 384Q483 404 441 402L382 402L380 438', 'none', '#b97772', 21)
  if (section) s += ellipse(381, 240, 53, 11, '#d6b875', '#b49b66')
  if (view === 'side') s = `<g transform="translate(115 0) scale(.72 1)">${s}</g>`
  return s + label('Liver', 306, 171, 65, 105) + label('Stomach', 470, 212, 560, 172) + label('Small intestine', 356, 321, 35, 338) + label('Colon', 484, 370, 562, 415) + (section ? label('Pancreas', 381, 240, 563, 270) : '')
}
function limb(view, leg) {
  if (view === 'section') return ellipse(380, 261, 140, 128, '#edd3b7', '#c4a992') + ellipse(349, 255, 71, 90, '#c47f79') + ellipse(435, 265, 48, 84, '#d29587') + ellipse(382, 262, 37, 39, '#f5e8c8', '#bdab90') + ellipse(382, 262, 19, 21, '#d6b58c', '#b59c7d') + ellipse(479, 224, 11, 12, '#bd5d62') + ellipse(492, 263, 12, 13, '#7098af') + label('Muscle', 301, 233, 60, 155) + label(leg ? 'Femur' : 'Humerus', 382, 262, 550, 354) + label('Artery', 478, 225, 559, 154) + label('Vein', 492, 263, 559, 264) + label('Bone marrow', 382, 262, 60, 420)
  let s = path('M379 102L381 253M370 265L362 426M395 267L400 426', 'none', '#d5bf98', 13) + ellipse(379, 100, 20, 17, '#eadbb8', '#bba789') + ellipse(381, 259, 25, 18, '#eadbb8', '#bba789') + ellipse(383, 428, 24, 15, '#eadbb8', '#bba789')
  s += path('M363 110C286 150 298 228 362 241Q342 175 363 110Z', '#c57e75') + path('M396 108C449 147 445 221 398 244Q412 172 396 108Z', '#d59a8e') + path('M354 283Q300 318 345 399L363 389Q339 335 370 287Z', '#d09383')
  if (leg) s += ellipse(381, 261, 15, 21, '#f5e8cb', '#bba789')
  else for (let i = 0; i < 5; i++) s += path(`M${356 + i * 12} 439L${348 + i * 16} ${469 - Math.abs(i - 2) * 6}`, 'none', '#d5bf98', 5)
  s += path('M421 108Q445 196 420 259Q435 329 416 417', 'none', '#b85b5e', 4) + path('M431 108Q457 195 432 259Q449 329 428 417', 'none', '#7098af', 3)
  if (view === 'side') s = `<g transform="translate(110 0) scale(.72 1)">${s}</g>`
  return s + label(leg ? 'Femur' : 'Humerus', 380, 157, 60, 130) + label(leg ? 'Quadriceps' : 'Biceps', 333, 188, 60, 241) + label(leg ? 'Patella' : 'Elbow joint', 382, 259, 555, 280) + label(leg ? 'Tibia' : 'Ulna', 364, 355, 60, 390) + label(leg ? 'Fibula' : 'Radius', 399, 370, 555, 419)
}
const parts = ['eyes', 'head', 'chest', 'abdomen', 'arms', 'legs']
for (const part of parts) for (const view of ['front', 'side', 'section']) {
  const title = `${part[0].toUpperCase() + part.slice(1)} · ${view === 'section' ? 'Cross-section' : view === 'front' ? 'Anterior view' : 'Lateral view'}`
  const content = part === 'eyes' ? eye(view) : part === 'head' ? head(view) : part === 'chest' ? chest(view) : part === 'abdomen' ? abdomen(view) : limb(view, part === 'legs')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="760" height="540" viewBox="0 0 760 540" role="img" aria-labelledby="title"><title id="title">${title}. Original schematic anatomical illustration.</title><defs><radialGradient id="sclera" cx=".35" cy=".3"><stop stop-color="#fffdf8"/><stop offset=".75" stop-color="#f2e7dc"/><stop offset="1" stop-color="#c7bcb3"/></radialGradient><radialGradient id="iris"><stop offset=".3" stop-color="#243d40"/><stop offset=".5" stop-color="#8eb7a1"/><stop offset=".9" stop-color="#487b7c"/><stop offset="1" stop-color="#284c55"/></radialGradient></defs>${content}<text x="380" y="514" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="12" fill="#81979e">${title} · Schematic anatomy</text></svg>`
  await writeFile(new URL(`${part}-${view}.svg`, directory), svg)
}
await writeFile(new URL('LICENSE.txt', directory), `MIT License\n\nCopyright (c) 2026 HumanTwin contributors\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n`)
console.log('Prepared 18 original anatomical illustrations and their MIT license.')
