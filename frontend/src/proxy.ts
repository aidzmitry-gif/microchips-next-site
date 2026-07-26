import { NextResponse, type NextRequest } from "next/server";

type RedirectLookup =
  | { kind: "redirect"; to: string; status: 301 | 302 | 307 | 308; locale: string }
  | { kind: "not_found"; locale: string };

const apiBaseUrl = (process.env.LARAVEL_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const redirectLookupTimeoutMs = 1_500;

export async function proxy(request: NextRequest) {
  const host = (request.headers.get("x-forwarded-host")?.split(",")[0] ?? request.headers.get("host") ?? request.nextUrl.hostname)
    .toLowerCase()
    .replace(/^www\./, "")
    .replace(/:\d+$/, "");

  if (!host) return NextResponse.next();

  try {
    const lookup = await fetch(
      `${apiBaseUrl}/api/v1/sites/${encodeURIComponent(host)}/redirect?path=${encodeURIComponent(request.nextUrl.pathname)}`,
      { cache: "no-store", signal: AbortSignal.timeout(redirectLookupTimeoutMs) },
    );
    if (!lookup.ok) {
      // A legacy redirect may be a permanent 301. Passing this request on
      // would let the page resolver emit Next's temporary redirect instead,
      // silently changing the migration contract during an API outage.
      if (lookup.status >= 500) return redirectServiceUnavailable();

      return NextResponse.next();
    }

    const redirect = (await lookup.json()) as RedirectLookup;
    if (redirect.kind === "redirect" && isSafeLocalTarget(redirect.to)) {
      return NextResponse.redirect(new URL(redirect.to, request.url), { status: redirect.status });
    }

    return withSiteLocale(request, redirect.locale);
  } catch {
    return redirectServiceUnavailable();
  }
}

function redirectServiceUnavailable(): NextResponse {
  return new NextResponse("Redirect lookup temporarily unavailable.", {
    status: 503,
    headers: {
      "Cache-Control": "no-store",
      "Retry-After": "30",
    },
  });
}

function isSafeLocalTarget(target: string): boolean {
  return target.startsWith("/") && !target.startsWith("//");
}

function withSiteLocale(request: NextRequest, locale: string): NextResponse {
  const language = locale.split("-")[0]?.toLowerCase();
  if (!language || !/^[a-z]{2,3}$/.test(language)) return NextResponse.next();

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-site-language", language);

  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  matcher: ["/((?!api|_next|favicon.ico|robots.txt|sitemap.xml).*)"],
};
