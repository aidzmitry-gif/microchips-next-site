import type { MetadataRoute } from "next";
import { getCurrentHost } from "@/lib/site-api";

export const dynamic = "force-dynamic";

export default async function robots(): Promise<MetadataRoute.Robots> {
  const host = await getCurrentHost();

  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/search", "/filter"] },
    sitemap: `https://${host}/sitemap.xml`,
  };
}
