import type { MetadataRoute } from "next";
import { fetchSitemap, getCurrentHost } from "@/lib/site-api";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const host = await getCurrentHost();
  const urls = await fetchSitemap(host);

  return urls.map((item) => ({
    url: new URL(item.path, `https://${host}`).toString(),
    lastModified: new Date(item.lastModified),
  }));
}
