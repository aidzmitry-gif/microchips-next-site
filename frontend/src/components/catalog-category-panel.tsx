"use client";

import { useId, useState } from "react";
import { CategoryTree } from "@/components/category-tree";
import type { CatalogCategory } from "@/lib/site-api";

type CatalogCategoryPanelProps = {
  categories: CatalogCategory[];
  currentPath: string;
};

export function CatalogCategoryPanel({ categories, currentPath }: CatalogCategoryPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();

  return (
    <aside className="catalog-layout__tree">
      <button
        className="catalog-layout__tree-toggle"
        type="button"
        aria-controls={panelId}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((value) => !value)}
      >
        <span>Разделы каталога</span>
        <span aria-hidden="true">{isOpen ? "Скрыть" : "Показать"}</span>
      </button>
      <div
        id={panelId}
        className={`catalog-layout__tree-body${isOpen ? " is-open" : ""}`}
      >
        <CategoryTree categories={categories} currentPath={currentPath} />
      </div>
    </aside>
  );
}
