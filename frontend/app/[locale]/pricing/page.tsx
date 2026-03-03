import type { Metadata } from "next";
import { resolveLocale } from "@/lib/locales";
import PricingPageClient from "./pricing-page-client";

type PricingPageMetadataProps = {
  params: Promise<{ locale?: string }>;
};

export async function generateMetadata({
  params,
}: PricingPageMetadataProps): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);

  return {
    alternates: {
      canonical: `/${locale}/pricing`,
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default function PricingPage() {
  return <PricingPageClient />;
}
