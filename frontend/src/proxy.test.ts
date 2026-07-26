import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { proxy } from "./proxy";

afterEach(() => vi.unstubAllGlobals());

describe("dynamic redirect proxy", () => {
  it("preserves a legacy 301 from Laravel", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ kind: "redirect", to: "/catalog/new", status: 301, locale: "ru-BY" })));

    const response = await proxy(new NextRequest("https://microchips.by/catalog/old", { headers: { host: "microchips.by" } }));

    expect(response.status).toBe(301);
    expect(response.headers.get("location")).toBe("https://microchips.by/catalog/new");
  });

  it("does not turn an unsafe destination into an external redirect", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ kind: "redirect", to: "//evil.test", status: 301, locale: "ru-BY" })));

    const response = await proxy(new NextRequest("https://microchips.by/catalog/old", { headers: { host: "microchips.by" } }));

    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("passes a validated page language to the root server layout", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ kind: "not_found", locale: "uz-UZ" })));

    const response = await proxy(new NextRequest("https://microchips.uz/uz/catalog", { headers: { host: "microchips.uz" } }));

    expect(response.headers.get("x-middleware-request-x-site-language")).toBe("uz");
  });

  it("fails closed when the redirect lookup is unavailable or times out so a legacy 301 cannot degrade to a temporary redirect", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("Timed out", "AbortError")));

    const response = await proxy(new NextRequest("https://microchips.by/catalog/old", { headers: { host: "microchips.by" } }));

    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("retry-after")).toBe("30");
    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ cache: "no-store", signal: expect.any(AbortSignal) }),
    );
  });

  it("fails closed for a backend 5xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("down", { status: 503 })));

    const response = await proxy(new NextRequest("https://microchips.by/catalog/old", { headers: { host: "microchips.by" } }));

    expect(response.status).toBe(503);
    expect(response.headers.get("x-middleware-next")).toBeNull();
  });
});
