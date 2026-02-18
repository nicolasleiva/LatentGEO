import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import CommerceCampaign from '@/app/[locale]/audits/[id]/geo/components/CommerceCampaign'
import { fetchWithBackendAuth } from '@/lib/backend-auth'

jest.mock('@/lib/backend-auth', () => ({
  fetchWithBackendAuth: jest.fn(),
}))

describe('Commerce query analyzer', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('sends query+market payload and renders why_not_first/action_plan output', async () => {
    ;(fetchWithBackendAuth as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ has_data: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            analysis_id: 77,
            query: 'zapatilla nike',
            market: 'AR',
            audited_domain: 'store.example.com',
            target_position: 4,
            top_result: {
              position: 1,
              title: 'Mercado Libre - Zapatillas',
              url: 'https://www.mercadolibre.com.ar/zapatillas',
              domain: 'mercadolibre.com.ar',
              snippet: 'Top listing',
            },
            results: [
              {
                position: 1,
                title: 'Mercado Libre - Zapatillas',
                url: 'https://www.mercadolibre.com.ar/zapatillas',
                domain: 'mercadolibre.com.ar',
                snippet: 'Top listing',
              },
            ],
            why_not_first: ['Low schema coverage on product pages.'],
            disadvantages_vs_top1: [
              {
                area: 'Structured Data',
                gap: 'Missing Product schema',
                impact: 'Lower citation eligibility',
              },
            ],
            action_plan: [
              {
                priority: 'P1',
                action: 'Deploy Product + FAQ schema on top PDPs',
                expected_impact: 'High',
                evidence: 'Audit signals',
              },
            ],
            evidence: [{ title: 'SERP #1', url: 'https://www.mercadolibre.com.ar/zapatillas' }],
            provider: 'kimi-2.5-search',
          }),
      })

    const user = userEvent.setup()
    render(<CommerceCampaign auditId={3} backendUrl="http://localhost:8000" />)

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledWith(
        'http://localhost:8000/api/geo/commerce-query/latest/3'
      )
    })

    const queryInput = screen.getByPlaceholderText('zapatilla nike')
    const marketInput = screen.getByPlaceholderText('AR, US, MX')

    await user.clear(queryInput)
    await user.type(queryInput, 'zapatilla nike')
    await user.clear(marketInput)
    await user.type(marketInput, 'AR')
    await user.click(screen.getByRole('button', { name: /analyze query position/i }))

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledTimes(2)
    })

    const secondCall = (fetchWithBackendAuth as jest.Mock).mock.calls[1]
    const requestBody = JSON.parse(secondCall[1].body as string)
    expect(requestBody).toMatchObject({
      audit_id: 3,
      query: 'zapatilla nike',
      market: 'AR',
    })

    expect(await screen.findByText(/low schema coverage on product pages/i)).toBeInTheDocument()
    expect(screen.getByText(/deploy product \+ faq schema on top pdps/i)).toBeInTheDocument()
  })
})
