"use client";

import type { CatalogCategory } from "@/lib/site-api";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

export function CatalogMegaMenu({
  categories = [],
  currentPath,
}: {
  categories?: CatalogCategory[];
  currentPath?: string;
}) {
  const initialCategory = useMemo(
    () => categories.find((category) => containsPath(category, currentPath))
      ?? categories.find((category) => category.children.length > 0)
      ?? categories[0],
    [categories, currentPath],
  );
  const [selectedSlug, setSelectedSlug] = useState(initialCategory?.slug ?? "");
  const menuRef = useRef<HTMLElement>(null);
  const rootRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selected = categories.find((category) => category.slug === selectedSlug) ?? initialCategory;

  useEffect(() => {
    if (initialCategory && !categories.some((category) => category.slug === selectedSlug)) {
      setSelectedSlug(initialCategory.slug);
    }
  }, [categories, initialCategory, selectedSlug]);

  useEffect(() => {
    const closeOnOutsidePointer = (event: globalThis.PointerEvent) => {
      const menu = menuRef.current;
      const details = menu?.closest("details");
      if (menu && details?.open && !details.contains(event.target as Node)) details.open = false;
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);

    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, []);

  if (categories.length === 0 || !selected) {
    return (
      <nav ref={menuRef} className="catalog-mega catalog-mega--empty" aria-label="Разделы каталога">
        <p>Разделы каталога проходят проверку.</p>
      </nav>
    );
  }

  const selectByIndex = (index: number) => {
    const next = categories[index];
    if (!next) return;
    setSelectedSlug(next.slug);
    rootRefs.current[index]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const lastIndex = categories.length - 1;
    const targetIndex = event.key === "ArrowDown" ? (index + 1) % categories.length
      : event.key === "ArrowUp" ? (index - 1 + categories.length) % categories.length
        : event.key === "Home" ? 0
          : event.key === "End" ? lastIndex
            : null;
    if (targetIndex !== null) {
      event.preventDefault();
      selectByIndex(targetIndex);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      const details = menuRef.current?.closest("details");
      if (details) {
        details.open = false;
        details.querySelector<HTMLElement>(":scope > summary")?.focus();
      }
    }
  };

  const handlePointerEnter = (event: PointerEvent<HTMLButtonElement>, slug: string) => {
    if (event.pointerType === "mouse") setSelectedSlug(slug);
  };

  return (
    <nav ref={menuRef} className="catalog-mega" aria-label="Разделы каталога">
      <div className="catalog-mega__roots" role="tablist" aria-orientation="vertical">
        {categories.map((category, index) => {
          const isSelected = category.slug === selected.slug;
          return (
            <button
              key={category.slug}
              ref={(element) => { rootRefs.current[index] = element; }}
              type="button"
              role="tab"
              id={`catalog-root-${category.slug}`}
              aria-selected={isSelected}
              aria-controls="catalog-mega-panel"
              tabIndex={isSelected ? 0 : -1}
              className="catalog-mega__root"
              onClick={() => setSelectedSlug(category.slug)}
              onFocus={() => setSelectedSlug(category.slug)}
              onPointerEnter={(event) => handlePointerEnter(event, category.slug)}
              onKeyDown={(event) => handleKeyDown(event, index)}
            >
              <span>{category.name}</span>
              <span aria-hidden="true">›</span>
            </button>
          );
        })}
      </div>

      <section
        id="catalog-mega-panel"
        className="catalog-mega__panel"
        role="tabpanel"
        aria-labelledby={`catalog-root-${selected.slug}`}
      >
        <header className="catalog-mega__panel-header">
          <div>
            <p>Каталог</p>
            <h2>{selected.name}</h2>
          </div>
          {selected.path && <a href={selected.path}>Все товары раздела</a>}
        </header>

        {selected.children.length > 0 ? (
          <ul className="catalog-mega__tiles">
            {selected.children.map((child) => (
              <li key={child.slug} className="catalog-mega__tile">
                <span className="catalog-mega__icon" aria-hidden="true">{categoryMonogram(child.name)}</span>
                <div>
                  {child.path
                    ? <a className="catalog-mega__tile-title" href={child.path} aria-current={samePath(currentPath, child.path) ? "page" : undefined}>{child.name}</a>
                    : <span className="catalog-mega__tile-title">{child.name}</span>}
                  {child.children.length > 0 && (
                    <ul className="catalog-mega__children">
                      {child.children.slice(0, 8).map((grandchild) => (
                        <li key={grandchild.slug}>
                          {grandchild.path ? <a href={grandchild.path}>{grandchild.name}</a> : <span>{grandchild.name}</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="catalog-mega__single">
            <span className="catalog-mega__icon" aria-hidden="true">{categoryMonogram(selected.name)}</span>
            <p>В разделе доступны проверенные товары. Перейдите по ссылке, чтобы открыть подбор и фильтры.</p>
          </div>
        )}
      </section>
    </nav>
  );
}

function normalizePath(path?: string | null): string {
  if (!path) return "";
  return path === "/" ? path : path.replace(/\/+$/, "");
}

function samePath(left?: string | null, right?: string | null): boolean {
  return normalizePath(left) === normalizePath(right);
}

function containsPath(category: CatalogCategory, currentPath?: string): boolean {
  const path = normalizePath(currentPath);
  const categoryPath = normalizePath(category.path);
  if (categoryPath && (path === categoryPath || path.startsWith(`${categoryPath}/`))) return true;

  return category.children.some((child) => containsPath(child, currentPath));
}

function categoryMonogram(name: string): string {
  const initials = name.trim().split(/\s+/u).filter(Boolean).slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");

  return initials || "•";
}
