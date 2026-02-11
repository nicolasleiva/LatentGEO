import { createHmac } from 'crypto'
import { NextResponse } from 'next/server'

import { auth0 } from '@/lib/auth0'

export const runtime = 'nodejs'

const TOKEN_TTL_SECONDS = 5 * 60

const base64UrlEncode = (value: string) =>
  Buffer.from(value)
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')

const encodeJson = (value: Record<string, unknown>) => base64UrlEncode(JSON.stringify(value))

const signJwt = (payload: Record<string, unknown>, secret: string) => {
  const header = { alg: 'HS256', typ: 'JWT' }
  const encodedHeader = encodeJson(header)
  const encodedPayload = encodeJson(payload)
  const signingInput = `${encodedHeader}.${encodedPayload}`
  const signature = createHmac('sha256', secret)
    .update(signingInput)
    .digest('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')

  return `${signingInput}.${signature}`
}

export async function GET() {
  const session = await auth0.getSession()
  const user = session?.user
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const userId = typeof user.sub === 'string' ? user.sub : ''
  const email = typeof user.email === 'string' ? user.email.trim().toLowerCase() : null
  if (!userId) {
    return NextResponse.json({ error: 'Invalid user session' }, { status: 401 })
  }

  const secret =
    process.env.BACKEND_INTERNAL_JWT_SECRET || process.env.SECRET_KEY || process.env.AUTH0_SECRET
  if (!secret) {
    return NextResponse.json(
      { error: 'Server misconfiguration: missing signing secret' },
      { status: 500 }
    )
  }

  const now = Math.floor(Date.now() / 1000)
  const exp = now + TOKEN_TTL_SECONDS
  const token = signJwt(
    {
      sub: userId,
      email,
      user_email: email,
      iat: now,
      exp,
      iss: 'latentgeo-frontend',
    },
    secret
  )

  return NextResponse.json({
    token,
    expires_at: exp * 1000,
    user_id: userId,
    email,
  })
}
