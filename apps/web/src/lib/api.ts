const base = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export class ApiError extends Error {
  readonly status: number
  readonly retryAfter: number | null
  constructor(status: number, message: string, retryAfter: number | null = null) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

/** The server could not be reached at all (network down, refused, DNS). */
export class NetworkError extends Error {}

let csrfToken: string | null = null
export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

interface Options {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: unknown
  signal?: AbortSignal
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken
  let response: Response
  try {
    response = await fetch(`${base}${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: base ? 'include' : 'same-origin',
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new NetworkError('server unreachable')
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      const data = (await response.json()) as { detail?: unknown }
      if (typeof data.detail === 'string') detail = data.detail
    } catch {
      /* no JSON body */
    }
    const retry = response.headers.get('Retry-After')
    throw new ApiError(response.status, detail, retry ? Number(retry) : null)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
