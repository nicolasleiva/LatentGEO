import type { Metadata, Viewport } from "next";
import { Manrope, Sora, JetBrains_Mono } from "next/font/google";
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

const metadataBase = (() => {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL?.trim() || APP_METADATA.siteUrl.trim();
  try {
    return new URL(raw);
  } catch {
    return new URL(APP_METADATA.siteUrl);
  }
})();

export const metadata: Metadata = {
  metadataBase,
  title: {
    default: APP_METADATA.title,
    template: `%s | ${APP_METADATA.siteName}`,
  },
  description: APP_METADATA.description,
  applicationName: APP_METADATA.siteName,
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: APP_METADATA.locale,
    siteName: APP_METADATA.siteName,
    title: APP_METADATA.title,
    description: APP_METADATA.description,
    url: "/en",
  },
  twitter: {
    card: "summary_large_image",
    title: APP_METADATA.title,
    description: APP_METADATA.description,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f766e",
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
            {children}
          </ThemeProvider>
        </QueryProvider>
        <AnalyticsProvider />
      </body>
    </html>
  );
}
