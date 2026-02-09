import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import { Auth0Provider } from '@auth0/nextjs-auth0/client'
import { ThemeProvider } from '@/components/theme-provider'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'AI Audit Studio - GEO & SEO Intelligence',
  description: 'Enterprise-grade AI auditing platform.',
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
    <html lang={validLocale} className={inter.variable} suppressHydrationWarning>
      <body className="font-sans antialiased min-h-screen">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange={false}
        >
          <Auth0Provider>{children}</Auth0Provider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
