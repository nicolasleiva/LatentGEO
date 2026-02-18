type BackendTokenResponse = {
  token?: string
  access_token?: string
  expires_at?: number
}

let cachedToken: string | null = null
let cachedExpiry = 0
let pendingTokenRequest: Promise<string | null> | null = null

const resolveApiUrl = () => {
  const publicUrl = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_BACKEND_URL
  const serverUrl = process.env.API_URL || publicUrl
  const url = typeof window !== 'undefined' ? publicUrl : serverUrl
  if (!url) {
    throw new Error('API URL is not configured. Set NEXT_PUBLIC_API_URL and API_URL.')
  }
  return url.replace(/\/+$/, '')
}

const BACKEND_API_URL = resolveApiUrl()

const isTokenFresh = () => {
  if (!cachedToken) return false
  // Refresh one minute before expiry.
  return Date.now() < cachedExpiry - 60_000
}

export const clearBackendTokenCache = () => {
  cachedToken = null
  cachedExpiry = 0
  pendingTokenRequest = null
}

export const getBackendAccessToken = async (forceRefresh = false): Promise<string | null> => {
  if (!forceRefresh && isTokenFresh()) {
    return cachedToken
  }

  if (pendingTokenRequest) {
    return pendingTokenRequest
  }

  pendingTokenRequest = (async () => {
    try {
      const res = await fetch('/api/auth/backend-token', {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      })
      if (!res.ok) {
        clearBackendTokenCache()
        return null
      }

      const payload = (await res.json()) as BackendTokenResponse
      const token = payload.token || payload.access_token || null
      if (!token) {
        clearBackendTokenCache()
        return null
      }

      cachedToken = token
      cachedExpiry = Number(payload.expires_at || Date.now() + 5 * 60_000)
      return cachedToken
    } catch {
      clearBackendTokenCache()
      return null
    } finally {
      pendingTokenRequest = null
    }
  })()

  return pendingTokenRequest
}

const shouldAttachBackendAuth = (requestUrl: URL) => {
  const backendOrigin = new URL(BACKEND_API_URL).origin
  return requestUrl.origin === backendOrigin && requestUrl.pathname.startsWith('/api/')
}

export const fetchWithBackendAuth = async (
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> => {
  if (typeof window === 'undefined') {
    return fetch(input, init)
  }

  const requestUrl =
    input instanceof Request
      ? new URL(input.url)
      : new URL(input.toString(), window.location.origin)

  if (!shouldAttachBackendAuth(requestUrl)) {
    return fetch(input, init)
  }

  const token = await getBackendAccessToken()
  const baseRequest = input instanceof Request ? input : new Request(input, init)
  const headers = new Headers(baseRequest.headers)

  if (init?.headers) {
    const initHeaders = new Headers(init.headers)
    initHeaders.forEach((value, key) => headers.set(key, value))
  }

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const credentials = init?.credentials ?? baseRequest.credentials ?? 'include'

  const buildRequest = (authHeaders: Headers) =>
    new Request(baseRequest, {
      ...init,
      headers: authHeaders,
      credentials,
    })

  let response = await fetch(buildRequest(headers))

  // Token may be expired/rotated; refresh once and retry transparently.
  if (response.status === 401 && token) {
    clearBackendTokenCache()
    const refreshedToken = await getBackendAccessToken(true)
    if (refreshedToken) {
      const retryHeaders = new Headers(headers)
      retryHeaders.set('Authorization', `Bearer ${refreshedToken}`)
      response = await fetch(buildRequest(retryHeaders))
    }
  }

  return response
}

export const buildAuthenticatedSseUrl = async (
  baseUrl: string,
  path: string
): Promise<string> => {
  const url = new URL(path, baseUrl)
  const token = await getBackendAccessToken()
  if (token) {
    url.searchParams.set('token', token)
  }
  return url.toString()
}
