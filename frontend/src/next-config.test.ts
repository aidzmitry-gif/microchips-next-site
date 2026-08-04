import { describe, expect, it } from "vitest";
import nextConfig from "../next.config";

describe("frontend security headers", () => {
  it("lets the application resolve legacy trailing-slash URLs without a framework 308 chain", () => {
    expect(nextConfig.skipTrailingSlashRedirect).toBe(true);
  });

  it("applies non-breaking baseline headers to every storefront route", async () => {
    const rules = await nextConfig.headers?.();

    expect(rules).toEqual(expect.arrayContaining([
      {
        source: "/(.*)",
        headers: expect.arrayContaining([
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ]),
      },
    ]));
  });

  it.each(["/legacy-preview/:path*", "/api/legacy-preview/:path*"])(
    "keeps legacy preview route %s private and out of search indexes",
    async (source) => {
      const rules = await nextConfig.headers?.();

      expect(rules).toEqual(expect.arrayContaining([
        {
          source,
          headers: expect.arrayContaining([
            { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
            { key: "Cache-Control", value: "private, no-store, max-age=0" },
          ]),
        },
      ]));
    },
  );
});
