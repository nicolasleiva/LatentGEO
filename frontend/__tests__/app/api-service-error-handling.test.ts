process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000'
process.env.API_URL = 'http://localhost:8000'

import { api } from '@/lib/api'
import { fetchWithBackendAuth } from '@/lib/backend-auth'

jest.mock('@/lib/backend-auth', () => ({
  fetchWithBackendAuth: jest.fn(),
}))

describe('APIService error propagation', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('propagates backend detail.message for Kimi failures', async () => {
    ;(fetchWithBackendAuth as jest.Mock).mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        detail: {
          code: 'KIMI_UNAVAILABLE',
          message:
            'Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY.',
        },
      }),
    })

    await expect(api.generateAIContent('1', 'example.com', ['ai'])).rejects.toThrow(
      'Kimi provider is not configured'
    )
  })
})
