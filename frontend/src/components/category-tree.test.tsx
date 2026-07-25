import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CategoryTree } from "./category-tree";

const categories = [
  {
    slug: "batteries",
    name: "Аккумуляторы",
    path: "/catalog/akkumulyatory",
    children: [{
      slug: "ups",
      name: "Для резервного питания",
      path: "/catalog/akkumulyatory/dlya_ibp",
      children: [{
        slug: "gel",
        name: "GEL",
        path: "/catalog/akkumulyatory/dlya_ibp/gelevye",
        children: [],
      }],
    }],
  },
];

describe("CategoryTree", () => {
  it("uses the site-scoped API tree and canonical paths", () => {
    render(<CategoryTree categories={categories} currentPath="/catalog/akkumulyatory/dlya_ibp/gelevye" />);

    const gel = screen.getByRole("link", { name: "GEL" });
    expect(gel.getAttribute("href")).toBe("/catalog/akkumulyatory/dlya_ibp/gelevye");
    expect(gel.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: /Для резервного питания/ })).toBeTruthy();
  });

  it("renders the same hierarchy as a mobile accordion", () => {
    const { container } = render(<CategoryTree categories={categories} mobile />);

    expect(container.querySelector(".category-tree--mobile")).toBeTruthy();
    expect(container.querySelectorAll("details").length).toBeGreaterThanOrEqual(1);
  });

  it("does not render a category without a published URL as a link", () => {
    render(<CategoryTree categories={[{ slug: "draft", name: "Черновик", path: null, children: [] }]} />);

    expect(screen.getByText("Черновик")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Черновик" })).toBeNull();
  });
});
