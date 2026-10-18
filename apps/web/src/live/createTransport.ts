import { sessionSocketUrl, WebSocketTransport, type Transport } from './transport'

/**
 * The transport for a session. `?mock=1` swaps in the scripted session, in the dev server only:
 * `import.meta.env.DEV` is a build-time constant, so the branch and the mock module are removed
 * from production builds (tests/prodBuild.test.ts proves it).
 */
export async function createTransport(
  sessionId: string,
  search: string = window.location.search,
): Promise<Transport> {
  if (import.meta.env.DEV) {
    const params = new URLSearchParams(search)
    if (params.get('mock') === '1') {
      const { ScriptedTransport } = await import('./mock')
      return new ScriptedTransport({ speed: Number(params.get('speed') ?? '1') || 1 })
    }
  }
  return new WebSocketTransport({ url: sessionSocketUrl(sessionId) })
}
