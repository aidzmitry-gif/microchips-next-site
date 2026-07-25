import { describe, expect, it } from "vitest";
import nextConfig from "../next.config";

describe("frontend security headers", () => {
  it("applies non-breaking baseline headers to every storefront route", async () => {
    const rules = await nextConfig.headers?.();

    expect(rules).toEqual([
      {
        source: "/(.*)",
        headers: expect.arrayContaining([
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ]),
      },
    ]);
  });
});
