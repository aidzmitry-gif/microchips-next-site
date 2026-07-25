const apiBaseUrl = (process.env.LARAVEL_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return Response.json({ message: "Invalid JSON body." }, { status: 400 });
  }

  try {
    const { key: rateKey, isNew } = leadRateKey(request.headers.get("cookie"));
    const response = await fetch(`${apiBaseUrl}/api/v1/leads/quote`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Lead-Rate-Key": rateKey,
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const responseBody = await response.text();

    const headers = new Headers({ "Content-Type": response.headers.get("content-type") ?? "application/json" });
    if (isNew) {
      headers.set("Set-Cookie", `lead_rate_key=${rateKey}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax`);
    }

    return new Response(responseBody, {
      status: response.status,
      headers,
    });
  } catch {
    return Response.json({ message: "Lead service unavailable." }, { status: 503 });
  }
}

function leadRateKey(cookieHeader: string | null): { key: string; isNew: boolean } {
  const existing = cookieHeader
    ?.split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("lead_rate_key="))
    ?.slice("lead_rate_key=".length);

  if (existing && /^[a-f0-9-]{36}$/i.test(existing)) {
    return { key: existing, isNew: false };
  }

  return { key: crypto.randomUUID(), isNew: true };
}
