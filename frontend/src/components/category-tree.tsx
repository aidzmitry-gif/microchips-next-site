import type { CatalogCategory } from "@/lib/site-api";

export type CategoryNode = CatalogCategory;

export function CategoryTree({
  categories = [],
  currentPath,
  mobile = false,
}: {
  categories?: CategoryNode[];
  currentPath?: string;
  mobile?: boolean;
}) {
  if (categories.length === 0) {
    return (
      <nav className={mobile ? "category-tree category-tree--mobile" : "category-tree"} aria-label="Разделы каталога">
        <p className="category-tree__title">Разделы каталога</p>
        <p className="category-tree__empty">Разделы проходят проверку.</p>
      </nav>
    );
  }

  return (
    <nav className={mobile ? "category-tree category-tree--mobile" : "category-tree"} aria-label="Разделы каталога">
      <p className="category-tree__title">Разделы каталога</p>
      <ul>
        {categories.map((node) => (
          <CategoryBranch key={node.slug} node={node} currentPath={currentPath} depth={0} mobile={mobile} />
        ))}
      </ul>
    </nav>
  );
}

function CategoryBranch({
  node,
  currentPath,
  depth,
  mobile,
}: {
  node: CategoryNode;
  currentPath?: string;
  depth: number;
  mobile: boolean;
}) {
  const isCurrent = normalizePath(currentPath) === normalizePath(node.path);
  const isActiveBranch = Boolean(node.path && currentPath && normalizePath(currentPath).startsWith(`${normalizePath(node.path)}/`));
  const hasChildren = node.children.length > 0;

  return (
    <li>
      {hasChildren ? (
        <details open={isCurrent || isActiveBranch || (!mobile && depth === 0)}>
          <summary>
            <span>{node.name}</span>
            <span aria-hidden="true">{node.children.length}</span>
          </summary>
          <ul>
            <li>
              {node.path ? (
                <a href={node.path} aria-current={isCurrent ? "page" : undefined}>
                  Все в разделе
                  <span className="sr-only"> {node.name}</span>
                </a>
              ) : <span>Все в разделе</span>}
            </li>
            {node.children.map((child) => (
              <CategoryBranch
                key={child.slug}
                node={child}
                currentPath={currentPath}
                depth={depth + 1}
                mobile={mobile}
              />
            ))}
          </ul>
        </details>
      ) : (
        node.path ? <a href={node.path} aria-current={isCurrent ? "page" : undefined}>{node.name}</a> : <span>{node.name}</span>
      )}
    </li>
  );
}

function normalizePath(path?: string | null) {
  if (!path) return "";
  return path === "/" ? path : path.replace(/\/+$/, "");
}
