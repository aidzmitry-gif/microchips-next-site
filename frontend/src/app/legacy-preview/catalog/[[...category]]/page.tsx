import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LegacyPreviewCatalogView } from "@/components/legacy-preview-catalog";
import {
  fetchLegacyPreviewCatalog,
  fetchLegacyPreviewCategories,
  isLegacyPreviewRequestAllowed,
} from "@/lib/legacy-preview-api";

type PageProps = {
  params: Promise<{ category?: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Предпросмотр каталога Bitrix | Microchips",
  robots: { index: false, follow: false, nocache: true },
};

export default async function LegacyPreviewCatalogPage({ params, searchParams }: PageProps) {
  if (!(await isLegacyPreviewRequestAllowed())) notFound();
  const category = (await params).category?.map(decodeURIComponent).join("/");
  const values = await searchParams;
  const query = first(values.q).slice(0, 100);
  const status = allowed(first(values.status), [
    "strict_mapped_evidence", "candidate_mapped_evidence", "candidate_duplicate_group",
    "hold_missing_1c_identity", "hold_missing_rb_site_product",
  ]);
  const sort = allowed(first(values.sort), ["legacy_id", "name_asc", "name_desc"]);
  const page = Math.max(1, Number.parseInt(first(values.page) || "1", 10) || 1);
  const [catalog, categories] = await Promise.all([
    fetchLegacyPreviewCatalog({ page, query, category, status, sort, perPage: 24 }),
    fetchLegacyPreviewCategories(),
  ]);

  return <LegacyPreviewCatalogView catalog={catalog} categories={categories} currentCategory={category} query={query} status={status} sort={sort} />;
}

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value ?? "").trim();
}

function allowed<T extends string>(value: string, values: readonly T[]): T | undefined {
  return values.includes(value as T) ? value as T : undefined;
}
