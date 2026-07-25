import { afterEach, describe, expect, it, vi } from "vitest";

const { headersMock } = vi.hoisted(() => ({ headersMock: vi.fn() }));

vi.mock("next/headers", () => ({ headers: headersMock }));

const { default: RootLayout, languageForLocale } = await import("./layout");

afterEach(() => headersMock.mockReset());

describe("root document language", () => {
  it("uses the validated language supplied by the hostname-aware proxy", async () => {
    headersMock.mockResolvedValue(new Headers([["x-site-language", "uz"]]));

    const document = await RootLayout({ children: <main /> });

    expect(document.props.lang).toBe("uz");
  });

  it("falls back to Russian when the forwarding header is absent or invalid", () => {
    expect(languageForLocale(null)).toBe("ru");
    expect(languageForLocale("ru-UZ")).toBe("ru");
    expect(languageForLocale("<script>")).toBe("ru");
  });
});
