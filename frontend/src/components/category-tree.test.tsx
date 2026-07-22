import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { buildCategoryForest, CategoryTree } from "./category-tree";

describe("buildCategoryForest", () => {
  it("builds category, subcategory and series levels from parent ids", () => {
    const forest = buildCategoryForest([
      { id: "1", parentId: "0", name: "Category", path: "/catalog/category" },
      { id: "2", parentId: "1", name: "Subcategory", path: "/catalog/category/subcategory" },
      { id: "3", parentId: "2", name: "Series", path: "/catalog/category/subcategory/series" },
    ]);

    expect(forest).toHaveLength(1);
    expect(forest[0].children[0].children[0].name).toBe("Series");
  });
});

describe("CategoryTree", () => {
  it("uses real legacy names and canonical paths", () => {
    render(<CategoryTree currentPath="/catalog/akkumulyatory/dlya_ibp/gelevye" />);

    const gel = screen.getByRole("link", { name: "GEL" });
    expect(gel.getAttribute("href")).toBe("/catalog/akkumulyatory/dlya_ibp/gelevye");
    expect(gel.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Для резервного питания" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Для медицинской техники" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Для сканеров штрих-кодов и терминалов" })).toBeNull();
  });

  it("renders the same hierarchy as a mobile accordion", () => {
    const { container } = render(<CategoryTree mobile />);

    expect(container.querySelector(".category-tree--mobile")).toBeTruthy();
    expect(container.querySelectorAll("details").length).toBeGreaterThanOrEqual(1);
  });
});
