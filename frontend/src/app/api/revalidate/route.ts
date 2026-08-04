import { NextResponse } from "next/server";
import { revalidatePath, revalidateTag } from "next/cache";

type RevalidateRequest = { paths?: unknown; site_key?: unknown; site_domain?: unknown };

function validSiteToken(value: unknown): value is string {
  return typeof value === "string"
    && value.length > 0
    && value.length <= 253
    && /^[a-z0-9.-]+$/i.test(value);
}

export async function POST(request: Request) {
  const secret = process.env.NEXT_REVALIDATE_SECRET;
  const authorization = request.headers.get("authorization");

  if (!secret || authorization !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as RevalidateRequest;
  const paths = Array.isArray(body.paths)
    ? body.paths.filter((path): path is string => typeof path === "string" && path.startsWith("/"))
    : [];
  const tags = [
    validSiteToken(body.site_key) ? `site:${body.site_key}` : null,
    validSiteToken(body.site_key) ? `catalog:${body.site_key}` : null,
    validSiteToken(body.site_domain) ? `site:${body.site_domain}` : null,
  ].filter((tag): tag is string => tag !== null);

  for (const path of paths) revalidatePath(path);
  for (const tag of tags) revalidateTag(tag, { expire: 0 });

  return NextResponse.json({ revalidated: paths, tags });
}
