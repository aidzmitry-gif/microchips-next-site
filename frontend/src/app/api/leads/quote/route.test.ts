import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("quote lead proxy", () => {
  it("forwards the current backend contract and response status", async () => {
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
    expect(response.headers.get("set-cookie")).toMatch(/^lead_rate_key=/);
  });

  it("reuses the server-issued lead rate key", async () => {
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
    const unavailable = await POST(new Request("http://localhost/api/leads/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }));
    expect(unavailable.status).toBe(503);
  });
});
