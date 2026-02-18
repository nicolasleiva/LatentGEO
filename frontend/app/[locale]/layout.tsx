// Force dynamic rendering to avoid static export path issues with [locale]
// This is required because Auth0 SDK v4 uses the crypto module which isn't available in Edge runtime during static generation
export const dynamic = "force-dynamic";

// Allow any locale parameter without static pre-generation
export const dynamicParams = true;

// Supported locales (used for runtime validation)
const locales = ["en", "es"];

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  // Validate locale at runtime to guard against invalid segment values.
  if (!locales.includes(locale)) {
    // Fall back to rendering without throwing; middleware handles redirects.
    return <>{children}</>;
  }

  return <>{children}</>;
}
