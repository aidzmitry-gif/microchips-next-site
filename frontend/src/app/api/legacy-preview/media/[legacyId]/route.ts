import { NextRequest, NextResponse } from "next/server";
import { isLocalOrTestHost, legacyPreviewSiteKey } from "@/lib/legacy-preview-api";

const apiBaseUrl = (process.env.LARAVEL_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function GET(request: NextRequest, { params }: { params: Promise<{ legacyId: string }> }) {
  const requestHost = request.headers.get("x-forwarded-host")?.split(",")[0] ?? request.headers.get("host");
  if (!isLocalOrTestHost(requestHost)) return new NextResponse("Not found", { status: 404 });
  const legacyId = (await params).legacyId;
  if (!/^\d+$/.test(legacyId)) return new NextResponse("Not found", { status: 404 });

  const upstream = await fetch(
    `${apiBaseUrl}/api/v1/sites/${encodeURIComponent(legacyPreviewSiteKey())}/legacy-preview/media/${legacyId}`,
    { cache: "no-store" },
  );
  if (!upstream.ok || !upstream.body) return new NextResponse("Not found", { status: upstream.status === 404 ? 404 : 502 });

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, no-store, max-age=0",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
