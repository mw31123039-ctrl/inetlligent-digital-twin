import { afterEach, describe, expect, it, vi } from 'vitest'
import fs from 'node:fs'
import * as T from 'three'
import { inspectPersonalGlb } from '../../src/avatar/personalModel'
import { createBodyDisplayContext } from '../../src/avatar/context'
import { restoreAnatomySourcePose } from '../../src/three/anatomyOverview'
import { buildSurfaceRig } from '../../src/three/buildSurfaceRig'
import { disposeScene } from '../../src/three/disposeScene'

const asset = fs.readFileSync(new URL('../../public/models/human.glb', import.meta.url))
const bytes = () => asset.buffer.slice(asset.byteOffset, asset.byteOffset + asset.byteLength) as ArrayBuffer
function documentWith(change: (document: any) => void) {
  const original = bytes(), source = new DataView(original), jsonLength = source.getUint32(12, true)
  const document = JSON.parse(new TextDecoder().decode(new Uint8Array(original, 20, jsonLength)))
  change(document)
  const encoded = new TextEncoder().encode(JSON.stringify(document)), padded = Math.ceil(encoded.length / 4) * 4
  const binary = new Uint8Array(original, 20 + jsonLength)
  const result = new ArrayBuffer(20 + padded + binary.length), output = new Uint8Array(result), view = new DataView(result)
  view.setUint32(0, 0x46546c67, true); view.setUint32(4, 2, true); view.setUint32(8, result.byteLength, true)
  view.setUint32(12, padded, true); view.setUint32(16, 0x4e4f534a, true)
  output.fill(32, 20, 20 + padded); output.set(encoded, 20); output.set(binary, 20 + padded)
  return result
}
const file = () => ({ name: 'permitted-synthetic-test.glb', size: asset.byteLength, arrayBuffer: async () => bytes() }) as File
afterEach(() => vi.restoreAllMocks())

describe('personal model admission and account isolation', () => {
  it('accepts the existing self-contained licensed human but rejects remote content and malformed geometry', () => {
    expect(inspectPersonalGlb(bytes()).triangles).toBeGreaterThan(1000)
    expect(inspectPersonalGlb(bytes()).imageCount).toBeGreaterThan(0)
    for (const change of [
      (document: any) => { document.buffers[0].uri = 'https://example.invalid/private-model.bin' },
      (document: any) => { document.images[0].uri = 'https://example.invalid/tracker.png' },
      (document: any) => { document.extensionsRequired = ['KHR_draco_mesh_compression'] },
      (document: any) => { document.nodes[0].children = [0] },
      (document: any) => { document.accessors[0].count = 100000000 },
      (document: any) => { document.bufferViews[0].byteLength = 100000000 },
    ]) expect(() => inspectPersonalGlb(documentWith(change))).toThrow()
    const corrupt = bytes(); new DataView(corrupt).setUint32(8, 1, true)
    expect(() => inspectPersonalGlb(corrupt)).toThrow()
  })

  it('stores only per-account view preferences and clears personal files on account changes', async () => {
    const saved = new Map<string, string>(), storage = { getItem: (key: string) => saved.get(key) ?? null, setItem: (key: string, value: string) => { saved.set(key, value) } }
    const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:synthetic-private-avatar')
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const context = createBodyDisplayContext(storage)
    context.setMode('anatomy'); context.setAccount(1)
    expect(context.mode.value).toBe('realistic')
    await expect(context.attach(file(), false)).rejects.toThrow('permission')
    expect(create).not.toHaveBeenCalled()
    await context.attach(file(), true)
    expect(context.personalUrl.value).toBe('blob:synthetic-private-avatar')
    expect(context.mode.value).toBe('personal')
    context.setAccount(2)
    expect(context.personalUrl.value).toBe(''); expect(context.fileName.value).toBe('')
    expect(revoke).toHaveBeenCalledWith('blob:synthetic-private-avatar')
    context.setAccount(1)
    expect(context.mode.value).toBe('personal'); expect(context.personalUrl.value).toBe('')
    context.setAccount(null); expect(context.mode.value).toBe('anatomy')
    expect([...saved.values()].every(value => ['anatomy', 'personal', 'realistic'].includes(value))).toBe(true)
    context.dispose()
  })

  it('ignores a late file read from a previous account and tolerates unavailable preference storage', async () => {
    let resolve!: (value: ArrayBuffer) => void
    const slow = { ...file(), arrayBuffer: () => new Promise<ArrayBuffer>(done => { resolve = done }) } as File
    const create = vi.spyOn(URL, 'createObjectURL')
    const context = createBodyDisplayContext({ getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') } })
    const pending = context.attach(slow, true)
    context.setAccount(99); resolve(bytes()); await pending
    expect(context.personalUrl.value).toBe(''); expect(context.pending.value).toBe(false)
    expect(create).not.toHaveBeenCalled()
    context.setMode('anatomy'); expect(context.mode.value).toBe('anatomy')
    context.dispose()
  })
})

describe('reference anatomy coordinates and static body interaction', () => {
  it('restores common source positions instead of stacking normalized organs at the same origin', () => {
    const scenes: T.Group[] = []
    for (const [name, height] of [['head', 1500], ['chest', 1200]] as const) {
      const scene = new T.Group(), source = new T.Group()
      source.name = 'BodyParts3D-' + name; source.position.set(10, -12, 3); source.scale.setScalar(.01); source.rotation.x = -Math.PI / 2
      const mesh = new T.Mesh(new T.BoxGeometry(10, 10, 10), new T.MeshStandardMaterial()); mesh.position.z = height
      source.add(mesh); scene.add(source)
      restoreAnatomySourcePose(scene, name)
      expect(new T.Box3().setFromObject(scene).getCenter(new T.Vector3()).y).toBeCloseTo(height)
      expect(source.rotation.x).toBeCloseTo(-Math.PI / 2)
      expect(mesh.userData.bodyRegion).toBe(name); scenes.push(scene)
    }
    const root = new T.Group(); root.add(...scenes)
    const rig = buildSurfaceRig(root, true)
    expect(rig.anchor('head').y).toBeGreaterThan(rig.anchor('chest').y)
    expect(rig.idle).toBeUndefined()
    expect(new T.Box3().setFromObject(root).getSize(new T.Vector3()).y).toBeCloseTo(1.8, 2)
    disposeScene(root)
  })

  it('only picks real surface hits for static personal models and keeps anchors finite', () => {
    const root = new T.Group(), mesh = new T.Mesh(new T.BoxGeometry(.4, 1.8, .2), new T.MeshStandardMaterial())
    mesh.position.y = .9; root.add(mesh)
    const rig = buildSurfaceRig(root, false)
    for (const part of ['head','eyes','chest','abdomen','arms','legs'] as const) expect(rig.anchor(part).toArray().every(Number.isFinite)).toBe(true)
    const hit = new T.Raycaster(new T.Vector3(0, 1.35, 3), new T.Vector3(0, 0, -1))
    expect(rig.pick(hit, new T.Vector3(0, 1.35, 3))).toBe('chest')
    const empty = new T.Raycaster(new T.Vector3(8, 1.35, 3), new T.Vector3(0, 0, -1))
    expect(rig.pick(empty, new T.Vector3(8, 1.35, 3))).toBeNull()
    expect(rig.diagnostics().bodyKind).toBe('personal')
    disposeScene(root)
  })
})
