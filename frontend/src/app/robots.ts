import type { MetadataRoute } from "next";
import { getCurrentHost, resolveSitePath } from "@/lib/site-api";

export const dynamic = "force-dynamic";

export default async function robots(): Promise<MetadataRoute.Robots> {
  const host = await getCurrentHost();
  const resolved = await resolveSitePath(host, "/");

  if (!("seo" in resolved) || !resolved.seo.isIndexable) {
    return { rules: { userAgent: "*", disallow: "/" } };
  }

  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/search", "/filter"] },
    sitemap: `https://${host}/sitemap.xml`,
  };
}
