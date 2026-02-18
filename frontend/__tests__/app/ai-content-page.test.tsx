import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AIContentPage from '@/app/[locale]/audits/[id]/ai-content/page'
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
    getAIContent: jest.fn(),
    getAudit: jest.fn(),
    generateAIContent: jest.fn(),
  },
}))

describe('AIContentPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useParams as jest.Mock).mockReturnValue({ id: '1' })
    ;(api.getAIContent as jest.Mock).mockResolvedValue([])
    ;(api.getAudit as jest.Mock).mockResolvedValue({ url: 'https://example.com' })
  })

  it('shows Kimi backend detail errors and not legacy OpenAI/Gemini message', async () => {
    const user = userEvent.setup()
    ;(api.generateAIContent as jest.Mock).mockRejectedValue(
      new Error('Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY.')
    )

    render(<AIContentPage />)

    await waitFor(() => {
      expect(api.getAIContent).toHaveBeenCalledWith('1')
    })

    const topicsInput = screen.getByPlaceholderText(/cloud computing, devops/i)
    await user.type(topicsInput, 'AI')
    await user.click(screen.getByRole('button', { name: /generate strategy/i }))

    expect(
      await screen.findByText(/Kimi provider is not configured/i)
    ).toBeInTheDocument()
    expect(screen.queryByText(/OpenAI\/Gemini/i)).not.toBeInTheDocument()
  })
})
