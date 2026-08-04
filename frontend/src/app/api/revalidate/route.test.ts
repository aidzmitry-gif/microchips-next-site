import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const revalidatePathMock = vi.fn();
const revalidateTagMock = vi.fn();

vi.mock("next/cache", () => ({
  revalidatePath: (path: string) => revalidatePathMock(path),
  revalidateTag: (tag: string, profile: { expire: number }) => revalidateTagMock(tag, profile),
}));

const ORIGINAL_SECRET = process.env.NEXT_REVALIDATE_SECRET;
const TEST_SECRET = "test-secret-value";

function makeRequest(options: { body?: unknown; rawBody?: string; authorization?: string | null }) {
  const headers = new Headers();
  if (options.authorization !== undefined && options.authorization !== null) {
    headers.set("authorization", options.authorization);
  }
  headers.set("content-type", "application/json");

  const body =
    options.rawBody !== undefined
      ? options.rawBody
      : options.body !== undefined
        ? JSON.stringify(options.body)
        : undefined;

  return new Request("https://example.test/api/revalidate", {
    method: "POST",
    headers,
    body,
  });
}

describe("POST /api/revalidate", () => {
  beforeEach(() => {
    revalidatePathMock.mockClear();
    revalidateTagMock.mockClear();
    process.env.NEXT_REVALIDATE_SECRET = TEST_SECRET;
  });

  afterEach(() => {
    if (ORIGINAL_SECRET === undefined) {
      delete process.env.NEXT_REVALIDATE_SECRET;
    } else {
      process.env.NEXT_REVALIDATE_SECRET = ORIGINAL_SECRET;
    }
  });

  it("returns 401 when the authorization header is missing", async () => {
    const { POST } = await import("./route");
    const request = makeRequest({ body: { paths: ["/foo"] }, authorization: null });

    const response = await POST(request);

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Unauthorized" });
    expect(revalidatePathMock).not.toHaveBeenCalled();
  });

  it("returns 401 when the bearer secret is wrong", async () => {
    const { POST } = await import("./route");
    const request = makeRequest({ body: { paths: ["/foo"] }, authorization: "Bearer wrong-secret" });

    const response = await POST(request);

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Unauthorized" });
    expect(revalidatePathMock).not.toHaveBeenCalled();
  });

  it("returns 401 when NEXT_REVALIDATE_SECRET is not configured, even if the header matches the interpolated empty secret", async () => {
    delete process.env.NEXT_REVALIDATE_SECRET;
    const { POST } = await import("./route");
    // With the secret unset, `Bearer ${secret}` interpolates to "Bearer undefined".
    // Sending exactly that satisfies the equality check, so only the `!secret`
    // guard can produce the 401 — this fails if that guard is ever removed.
    const request = makeRequest({ body: { paths: ["/foo"] }, authorization: "Bearer undefined" });

    const response = await POST(request);

    expect(response.status).toBe(401);
    expect(revalidatePathMock).not.toHaveBeenCalled();
  });

  it("rejects with a malformed (non-JSON) body once authorized", async () => {
    const { POST } = await import("./route");
    const request = makeRequest({ rawBody: "{not valid json", authorization: `Bearer ${TEST_SECRET}` });

    await expect(POST(request)).rejects.toThrow();
    expect(revalidatePathMock).not.toHaveBeenCalled();
  });

  it("filters out paths that do not start with '/'", async () => {
    const { POST } = await import("./route");
    const request = makeRequest({
      body: { paths: ["relative/path", "/valid", 42, null, "", "/another-valid"] },
      authorization: `Bearer ${TEST_SECRET}`,
    });

    const response = await POST(request);
    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json).toEqual({ revalidated: ["/valid", "/another-valid"], tags: [] });
    expect(revalidatePathMock).toHaveBeenCalledTimes(2);
    expect(revalidatePathMock).toHaveBeenNthCalledWith(1, "/valid");
    expect(revalidatePathMock).toHaveBeenNthCalledWith(2, "/another-valid");
  });

  it("treats a missing or non-array paths field as an empty list", async () => {
    const { POST } = await import("./route");
    const request = makeRequest({ body: {}, authorization: `Bearer ${TEST_SECRET}` });

    const response = await POST(request);
    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json).toEqual({ revalidated: [], tags: [] });
    expect(revalidatePathMock).not.toHaveBeenCalled();
  });

  it("revalidates successfully with a valid bearer secret and valid paths", async () => {
    const { POST } = await import("./route");
    const request = makeRequest({
      body: {
        paths: ["/catalog", "/catalog/battery"],
        site_key: "microchips-by",
        site_domain: "microchips-by.test",
      },
      authorization: `Bearer ${TEST_SECRET}`,
    });

    const response = await POST(request);
    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json).toEqual({
      revalidated: ["/catalog", "/catalog/battery"],
      tags: ["site:microchips-by", "catalog:microchips-by", "site:microchips-by.test"],
    });
    expect(revalidatePathMock).toHaveBeenCalledTimes(2);
    expect(revalidatePathMock).toHaveBeenCalledWith("/catalog");
    expect(revalidatePathMock).toHaveBeenCalledWith("/catalog/battery");
    expect(revalidateTagMock).toHaveBeenCalledTimes(3);
    expect(revalidateTagMock).toHaveBeenCalledWith("catalog:microchips-by", { expire: 0 });
  });

  it("ignores unsafe cache tag values", async () => {
    const { POST } = await import("./route");
    const request = makeRequest({
      body: { paths: ["/catalog"], site_key: "../../unsafe", site_domain: "bad value" },
      authorization: `Bearer ${TEST_SECRET}`,
    });

    const response = await POST(request);

    await expect(response.json()).resolves.toEqual({ revalidated: ["/catalog"], tags: [] });
    expect(revalidateTagMock).not.toHaveBeenCalled();
  });
});
