import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StructuredData, serializeStructuredData } from "./structured-data";

describe("StructuredData", () => {
  it("renders an object supplied by the SEO API as JSON-LD", () => {
    const { container } = render(<StructuredData value={{ "@type": "Product", name: "FIAMM" }} />);
    const script = container.querySelector('script[type="application/ld+json"]');

    expect(script?.textContent).toContain('"@type":"Product"');
    expect(script?.textContent).toContain('"name":"FIAMM"');
  });

  it("does not render primitive values and escapes closing script markup", () => {
    const { container } = render(<StructuredData value="Product" />);

    expect(container.querySelector("script")).toBeNull();
    expect(serializeStructuredData({ name: "</script><script>alert(1)</script>" })).not.toContain("<");
  });
});
