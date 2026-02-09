"use client"

import HubSpotApplyRecommendations from '@/components/hubspot-apply-recommendations'
import { useParams } from 'next/navigation'

export default function HubSpotApplyPage() {
    const params = useParams()
    const id = params.id as string

    return (
        <div className="container mx-auto py-8">
            <HubSpotApplyRecommendations auditId={id} />
        </div>
    )
}
