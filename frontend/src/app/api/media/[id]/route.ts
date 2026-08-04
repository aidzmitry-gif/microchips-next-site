import { NextResponse } from "next/server";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) return new NextResponse(null, { status: 404 });

  const apiBase = (process.env.LARAVEL_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${apiBase}/api/v1/media/${id}`, { cache: "no-store" });
  if (!response.ok || response.body === null) return new NextResponse(null, { status: response.status });

  return new NextResponse(response.body, {
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/octet-stream",
      "cache-control": response.headers.get("cache-control") ?? "public, max-age=31536000, immutable",
      "x-robots-tag": response.headers.get("x-robots-tag") ?? "noindex, noarchive",
      "x-content-type-options": "nosniff",
    },
  });
}
