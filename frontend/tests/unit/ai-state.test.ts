import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAiAssessment } from '../../src/composables/useAiAssessment'
import { aiApi } from '../../src/services/aiApi'
import type { ChatEnvelope } from '../../src/types/ai'

vi.mock('../../src/services/aiApi', () => ({ aiApi: { get: vi.fn(), post: vi.fn(), delete: vi.fn(), csrf: vi.fn() }, ApiError: class extends Error { status = 0 } }))
let flows: ReturnType<typeof useAiAssessment>[] = []
const deferred = <T>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
function flow() { const value = useAiAssessment(); flows.push(value); return value }
function envelope(region = 'eyes'): ChatEnvelope {
  return { id: 'test-conversation', revision: 0, token: 'encrypted-token', messages: [], assessment: { schema_version: '1.0', selected_region: region, side: 'unknown', facts: [], limitations: [], supporting_sources: [], urgency: { level: 'not_established', reasons: [], rule_ids: [] } } } as unknown as ChatEnvelope
}
beforeEach(() => { vi.resetAllMocks() })
afterEach(() => { flows.forEach(f => f.dispose()); flows = [] })

describe('private AI chat state', () => {
  it('drops late replies when the body region changes', async () => {
    const f = flow(); f.state.user = { id: 1, email: 'synthetic@example.test' }; f.state.processingConsent = true
    const pending = deferred<ChatEnvelope>()
    vi.mocked(aiApi.post).mockReturnValueOnce(pending.promise)
    const request = f.send('Synthetic dry feeling')
    f.reset('legs')
    pending.resolve(envelope('eyes'))
    expect(await request).toBe(false)
    expect(f.state.region).toBe('legs')
    expect(f.state.envelope).toBeNull()
  })

  it('does not restore another account’s late saved-record response', async () => {
    const f = flow(); f.state.user = { id: 1, email: 'a@example.test' }
    const pending = deferred<never>()
    vi.mocked(aiApi.get).mockReturnValueOnce(pending.promise)
    const listing = f.listSaved()
    f.reset(); f.state.user = { id: 2, email: 'b@example.test' }; f.state.savedChats = []
    pending.resolve([{ id: 'a-private-record', region: 'eyes', created_at: '2026-10-20' }] as never)
    await listing
    expect(f.state.savedChats).toEqual([])
  })

  it('requires separate saving consent without making a persistence request', async () => {
    const f = flow(); f.state.envelope = envelope(); f.state.storageConsent = false
    await f.save()
    expect(aiApi.post).not.toHaveBeenCalled()
  })

  it('ignores a stale authentication initialization after the context was reset', async () => {
    const f = flow()
    const pending = deferred<{ user: { id: number; email: string } }>()
    vi.mocked(aiApi.get).mockResolvedValueOnce({ available: true, provider_configured: false }).mockReturnValueOnce(pending.promise)
    const initialization = f.init()
    await Promise.resolve()
    f.reset(); f.state.user = { id: 2, email: 'current@example.test' }
    pending.resolve({ user: { id: 1, email: 'previous@example.test' } })
    await initialization
    expect(f.state.user.id).toBe(2)
  })
})
