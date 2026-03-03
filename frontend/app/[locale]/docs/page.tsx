import type { Metadata } from "next";
import { resolveLocale } from "@/lib/locales";
import DocsPageClient from "./docs-page-client";

type DocsPageMetadataProps = {
  params: Promise<{ locale?: string }>;
};

export async function generateMetadata({
  params,
}: DocsPageMetadataProps): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);

  return {
    alternates: {
      canonical: `/${locale}/docs`,
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default function DocsPage() {
  return <DocsPageClient />;
}
