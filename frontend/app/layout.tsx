import type { Metadata } from "next";
import { Manrope, Sora, JetBrains_Mono } from "next/font/google";
import { Auth0Provider } from "@auth0/nextjs-auth0/client";
import { ThemeProvider } from "@/components/theme-provider";
import { AnalyticsProvider } from "@/components/providers/analytics-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { APP_METADATA } from "@/lib/brand";
import { resolveLocale } from "@/lib/locales";
import "./globals.css";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: APP_METADATA.title,
  description: APP_METADATA.description,
};

export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params?: Promise<{ locale?: string }>;
}) {
  const resolvedParams = params ? await params : undefined;
  const locale = resolvedParams?.locale;
  const validLocale = resolveLocale(locale);

  return (
    <html
      lang={validLocale}
      className={`${sora.variable} ${manrope.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body className="font-sans antialiased min-h-screen bg-background text-foreground">
        <QueryProvider>
          <ThemeProvider
            attribute="class"
            defaultTheme="light"
            enableSystem={false}
            storageKey="latentgeo-theme-v2"
            disableTransitionOnChange={false}
          >
            <Auth0Provider>{children}</Auth0Provider>
          </ThemeProvider>
        </QueryProvider>
        <AnalyticsProvider />
      </body>
    </html>
  );
}
