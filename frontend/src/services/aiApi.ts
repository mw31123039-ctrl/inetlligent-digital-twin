export class ApiError extends Error {
  constructor(message: string, public status = 0) { super(message) }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const csrf = document.cookie.split('; ').find(item => item.startsWith('XSRF-TOKEN='))?.slice(11)
  const timeout = new AbortController()
  const timer = window.setTimeout(() => timeout.abort(), 35_000)
  try {
    const response = await fetch(path, {
      ...options, credentials: 'include', cache: 'no-store',
      signal: options.signal ? AbortSignal.any([options.signal, timeout.signal]) : timeout.signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(csrf ? { 'X-XSRF-TOKEN': decodeURIComponent(csrf) } : {}), ...options.headers },
    })
    if (response.status === 204) return undefined as T
    const body = await response.json().catch(() => null)
    if (!response.ok) {
      const message = response.status === 401 ? 'Sign in to continue.' : response.status === 419 ? 'Your session expired. Sign in again.' : typeof body?.message === 'string' ? body.message : 'The API could not complete this request.'
      throw new ApiError(message, response.status)
    }
    if (body === null) throw new ApiError('The API returned an invalid response.')
    return body as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (options.signal?.aborted) throw error
    throw new ApiError('The service is unavailable or timed out. Your draft remains on this screen. For severe or sudden symptoms, seek urgent medical help.')
  } finally { window.clearTimeout(timer) }
}

export const aiApi = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(`/api${path}`, { signal }),
  post: <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>(`/api${path}`, { method: 'POST', body: JSON.stringify(body), signal }),
  delete: (path: string) => request<void>(`/api${path}`, { method: 'DELETE' }),
  csrf: () => request<void>('/sanctum/csrf-cookie'),
}
