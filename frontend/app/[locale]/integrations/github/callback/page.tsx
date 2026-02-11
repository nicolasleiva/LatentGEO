'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, CheckCircle2, XCircle } from "lucide-react"
import { API_URL } from '@/lib/api'

function CallbackContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
    const [message, setMessage] = useState('Conectando con GitHub...')

    useEffect(() => {
        const code = searchParams.get('code')
        const error = searchParams.get('error')

        if (error) {
            setStatus('error')
            setMessage('GitHub authorization error')
            return
        }

        if (!code) {
            setStatus('error')
            setMessage('Authorization code not received')
            return
        }

        const exchangeCode = async () => {
            try {
                const response = await fetch(`${API_URL}/api/github/callback`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ code }),
                })

                if (!response.ok) {
                    throw new Error('Error exchanging authorization code')
                }

                const data = await response.json()
                setStatus('success')
                setMessage('Connection successful! Redirecting...')

                // Guardar connection_id si es necesario o simplemente redirigir
                setTimeout(() => {
                    router.push('/audits')
                }, 2000)

            } catch (err) {
                console.error(err)
                setStatus('error')
                setMessage('Error al conectar con el servidor')
            }
        }

        exchangeCode()
    }, [searchParams, router])

    return (
        <Card className="w-[400px]">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    {status === 'loading' && <Loader2 className="h-6 w-6 animate-spin" />}
                    {status === 'success' && <CheckCircle2 className="h-6 w-6 text-green-500" />}
                    {status === 'error' && <XCircle className="h-6 w-6 text-red-500" />}
                    GitHub connection
                </CardTitle>
            </CardHeader>
            <CardContent>
                <p className="text-muted-foreground mb-4">{message}</p>
                {status === 'error' && (
                    <div className="bg-red-50 p-2 rounded text-xs text-red-800 break-all">
                        <p>If the error persists, copy this code and send it to support:</p>
                        <code className="font-mono font-bold mt-2 block">{searchParams.get('code')}</code>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default function GitHubCallback() {
    return (
        <div className="flex h-screen w-full items-center justify-center bg-gray-50">
            <Suspense fallback={<div>Loading...</div>}>
                <CallbackContent />
            </Suspense>
        </div>
    )
}
