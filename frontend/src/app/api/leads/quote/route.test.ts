import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

const ORIGINAL_LEAD_PROXY_SECRET = process.env.LEAD_PROXY_SECRET;

afterEach(() => {
  vi.unstubAllGlobals();
  process.env.LEAD_PROXY_SECRET = ORIGINAL_LEAD_PROXY_SECRET;
});

describe("quote lead proxy", () => {
  it("forwards the current backend contract and response status", async () => {
    process.env.LEAD_PROXY_SECRET = "testing-lead-proxy-secret-32-characters";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 7, status: "accepted" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const body = { site_key: "microchips-by", company: "ООО Тест" };

    const response = await POST(new Request("http://localhost/api/leads/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Forwarded-For": "203.0.113.5" },
      body: JSON.stringify(body),
    }));

    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ id: 7, status: "accepted" });
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/leads/quote");
    expect(JSON.parse(String(options.body))).toEqual(body);
    // The browser-controlled header must not affect Laravel's rate-limit identity.
    expect(new Headers(options.headers).get("X-Forwarded-For")).toBeNull();
    expect(new Headers(options.headers).get("X-Lead-Rate-Key")).toMatch(/^[a-f0-9-]{36}$/i);
    expect(new Headers(options.headers).get("X-Lead-Proxy-Secret")).toBe("testing-lead-proxy-secret-32-characters");
    expect(response.headers.get("set-cookie")).toMatch(/^lead_rate_key=/);
  });

  it("reuses the server-issued lead rate key", async () => {
    process.env.LEAD_PROXY_SECRET = "testing-lead-proxy-secret-32-characters";
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const rateKey = "a1111111-1111-4111-8111-111111111111";

    const response = await POST(new Request("http://localhost/api/leads/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: `lead_rate_key=${rateKey}` },
      body: "{}",
    }));

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(options.headers).get("X-Lead-Rate-Key")).toBe(rateKey);
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("returns 400 for invalid JSON and 503 when Laravel is unavailable", async () => {
    const invalid = await POST(new Request("http://localhost/api/leads/quote", { method: "POST", body: "{" }));
    expect(invalid.status).toBe(400);

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    process.env.LEAD_PROXY_SECRET = "testing-lead-proxy-secret-32-characters";
    const unavailable = await POST(new Request("http://localhost/api/leads/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }));
    expect(unavailable.status).toBe(503);
  });

  it("fails closed when the server-only proxy secret is missing", async () => {
    delete process.env.LEAD_PROXY_SECRET;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(new Request("http://localhost/api/leads/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }));

    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
