import type { Metadata } from 'next'
import { Manrope, Sora, JetBrains_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import { Auth0Provider } from '@auth0/nextjs-auth0/client'
import { ThemeProvider } from '@/components/theme-provider'
import './globals.css'

const sora = Sora({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
})

const manrope = Manrope({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'LatentGEO.ai — AI & Generative Search Readiness',
  description:
    'Autonomous code remediation and AI-native content creation for growth and visibility.',
}

// Supported locales (used for runtime validation)
const locales = ['en', 'es']

export default function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params?: { locale?: string }
}) {
  const locale = params?.locale
  const validLocale = locale && locales.includes(locale) ? locale : 'en'

  return (
    <html
      lang={validLocale}
      className={`${sora.variable} ${manrope.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body className="font-sans antialiased min-h-screen bg-background text-foreground">
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem={false}
          storageKey="latentgeo-theme-v2"
          disableTransitionOnChange={false}
        >
          <Auth0Provider>{children}</Auth0Provider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
