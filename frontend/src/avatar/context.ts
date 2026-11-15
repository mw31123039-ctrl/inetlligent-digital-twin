import { computed, inject, ref, type InjectionKey } from 'vue'
import { inspectPersonalGlb } from './personalModel'

export type BodyDisplay = 'realistic' | 'anatomy' | 'personal'
const modes: BodyDisplay[] = ['realistic', 'anatomy', 'personal']
type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem'>
export function createBodyDisplayContext(storage?: Storage) {
  const mode = ref<BodyDisplay>('realistic'), account = ref('guest'), personalUrl = ref(''), fileName = ref(''), fileHash = ref(''), rotation = ref(0), pending = ref(false)
  let generation = 0, disposed = false
  const key = () => 'humantwin.bodyDisplay.v1.' + account.value
  const title = computed(() => ({ realistic: 'Reference person', anatomy: 'Reference anatomy', personal: 'Personal 3D model' })[mode.value])
  function clearPersonal() {
    generation++; pending.value = false
    if (personalUrl.value) URL.revokeObjectURL(personalUrl.value)
    personalUrl.value = ''; fileName.value = ''; fileHash.value = ''; rotation.value = 0
  }
  function setAccount(id: number | null) {
    const next = id === null ? 'guest' : 'user-' + id
    if (next === account.value) return
    clearPersonal(); account.value = next; restore()
  }
  function restore() {
    let stored: string | null = null
    try { stored = storage?.getItem(key()) ?? null } catch {}
    mode.value = modes.includes(stored as BodyDisplay) ? stored as BodyDisplay : 'realistic'
  }
  function setMode(value: BodyDisplay) {
    if (!modes.includes(value)) return
    mode.value = value
    try { storage?.setItem(key(), value) } catch {}
  }
  async function attach(file: File, permitted: boolean) {
    if (!permitted) throw new Error('Confirm that you own this model or have permission to use it.')
    if (!/\.glb$/i.test(file.name) || file.size > 40 * 1024 * 1024) throw new Error('Choose a self-contained GLB model up to 40 MB.')
    const version = ++generation; pending.value = true
    try {
      const bytes = await file.arrayBuffer()
      inspectPersonalGlb(bytes)
      const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(value => value.toString(16).padStart(2, '0')).join('')
      if (disposed || version !== generation) return
      const previous = personalUrl.value
      personalUrl.value = URL.createObjectURL(new Blob([bytes], { type: 'model/gltf-binary' }))
      fileName.value = file.name; fileHash.value = hash; rotation.value = 0
      if (previous) URL.revokeObjectURL(previous)
      setMode('personal')
    } finally { if (version === generation) pending.value = false }
  }
  function dispose() { disposed = true; clearPersonal() }
  restore()
  return { mode, account, personalUrl, fileName, fileHash, rotation, pending, title, setAccount, setMode, attach, clearPersonal, dispose }
}
export type BodyDisplayContext = ReturnType<typeof createBodyDisplayContext>
export const bodyDisplayKey: InjectionKey<BodyDisplayContext> = Symbol('body-display')
export function useBodyDisplay() {
  const value = inject(bodyDisplayKey)
  if (!value) throw new Error('Body display provider is missing.')
  return value
}
