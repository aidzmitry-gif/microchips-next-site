import { describe, expect, it } from "vitest";
import { isLocalOrTestHost } from "./legacy-preview-api";

describe("legacy preview host gate", () => {
  it.each(["localhost:3000", "127.0.0.1:3000", "microchips-by.test", "www.rb.test"])(
    "allows only a local or .test preview host: %s",
    (host) => expect(isLocalOrTestHost(host)).toBe(true),
  );

  it.each(["microchips.by", "preview.microchips.by", "evil.test.example", ""])(
    "denies a public or malformed host: %s",
    (host) => expect(isLocalOrTestHost(host)).toBe(false),
  );
});
