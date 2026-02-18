import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import KeywordsPage from '@/app/[locale]/audits/[id]/keywords/page'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'

jest.mock('next/navigation', () => ({
  useParams: jest.fn(),
}))

jest.mock('@/components/header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}))

jest.mock('@/lib/api', () => ({
  api: {
    getKeywords: jest.fn(),
    getAudit: jest.fn(),
    researchKeywords: jest.fn(),
  },
}))

describe('KeywordsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useParams as jest.Mock).mockReturnValue({ id: '1' })
    ;(api.getKeywords as jest.Mock).mockResolvedValue([])
    ;(api.getAudit as jest.Mock).mockResolvedValue({ url: 'https://example.com' })
  })

  it('shows Kimi detail errors for keyword research', async () => {
    const user = userEvent.setup()
    ;(api.researchKeywords as jest.Mock).mockRejectedValue(
      new Error('Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY.')
    )

    render(<KeywordsPage />)

    await waitFor(() => {
      expect(api.getKeywords).toHaveBeenCalledWith('1')
    })

    await user.type(screen.getByPlaceholderText(/software, saas/i), 'ai seo')
    await user.click(screen.getByRole('button', { name: /find keywords/i }))

    expect(
      await screen.findByText(/Kimi provider is not configured/i)
    ).toBeInTheDocument()
    expect(screen.queryByText(/OpenAI\/Gemini/i)).not.toBeInTheDocument()
  })
})
