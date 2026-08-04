import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LegacyPreviewProductView } from "@/components/legacy-preview-product";
import { fetchLegacyPreviewProduct, isLegacyPreviewRequestAllowed } from "@/lib/legacy-preview-api";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Карточка Bitrix — предпросмотр | Microchips",
  robots: { index: false, follow: false, nocache: true },
};

export default async function LegacyPreviewProductPage({ params }: { params: Promise<{ legacyId: string }> }) {
  if (!(await isLegacyPreviewRequestAllowed())) notFound();
  const legacyId = Number.parseInt((await params).legacyId, 10);
  if (!Number.isSafeInteger(legacyId) || legacyId < 1) notFound();
  const product = await fetchLegacyPreviewProduct(legacyId);
  if (product === null) notFound();

  return <LegacyPreviewProductView product={product} />;
}
