import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LLMVisibilityPage from '@/app/[locale]/audits/[id]/llm-visibility/page'
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
    getLLMVisibility: jest.fn(),
    checkLLMVisibility: jest.fn(),
  },
}))

describe('LLMVisibilityPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useParams as jest.Mock).mockReturnValue({ id: '1' })
    ;(api.getLLMVisibility as jest.Mock).mockResolvedValue([])
  })

  it('shows Kimi detail errors for visibility checks', async () => {
    const user = userEvent.setup()
    ;(api.checkLLMVisibility as jest.Mock).mockRejectedValue(
      new Error('Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY.')
    )

    render(<LLMVisibilityPage />)

    await waitFor(() => {
      expect(api.getLLMVisibility).toHaveBeenCalledWith('1')
    })

    await user.type(screen.getByPlaceholderText(/acme corp/i), 'Example')
    await user.type(screen.getByPlaceholderText(/best seo tools, top marketing agencies/i), 'best ai tools')
    await user.click(screen.getByRole('button', { name: /check visibility/i }))

    expect(
      await screen.findByText(/Kimi provider is not configured/i)
    ).toBeInTheDocument()
    expect(screen.queryByText(/OpenAI\/Gemini/i)).not.toBeInTheDocument()
  })
})
