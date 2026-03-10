import { redirect } from "next/navigation";

export default async function LegacyOdooPageSpeedPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  redirect(`/${locale}/audits/${id}/odoo-delivery`);
}
