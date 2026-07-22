import { rbLegacyCategoryRows, type LegacyCategoryRow } from "@/data/rb-legacy-categories";

type CategoryNode = LegacyCategoryRow & { children: CategoryNode[] };

export function CategoryTree({ currentPath, mobile = false }: { currentPath?: string; mobile?: boolean }) {
  const roots = buildCategoryForest(rbLegacyCategoryRows);

  return (
    <nav className={mobile ? "category-tree category-tree--mobile" : "category-tree"} aria-label="Разделы каталога">
      <p className="category-tree__title">Разделы каталога</p>
      <ul>
        {roots.map((node) => (
          <CategoryBranch key={node.id} node={node} currentPath={currentPath} depth={0} mobile={mobile} />
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
  const isActiveBranch = currentPath ? normalizePath(currentPath).startsWith(`${normalizePath(node.path)}/`) : false;
  const hasChildren = node.children.length > 0;

  return (
    <li>
      {hasChildren ? (
        <details open={isCurrent || isActiveBranch || (!mobile && depth === 0)}>
          <summary>
            <a href={node.path} aria-current={isCurrent ? "page" : undefined}>{node.name}</a>
            <span aria-hidden="true">{node.children.length}</span>
          </summary>
          <ul>
            {node.children.map((child) => (
              <CategoryBranch
                key={child.id}
                node={child}
                currentPath={currentPath}
                depth={depth + 1}
                mobile={mobile}
              />
            ))}
          </ul>
        </details>
      ) : (
        <a href={node.path} aria-current={isCurrent ? "page" : undefined}>{node.name}</a>
      )}
    </li>
  );
}

export function buildCategoryForest(rows: LegacyCategoryRow[]): CategoryNode[] {
  const nodes = new Map(rows.map((row) => [row.id, { ...row, children: [] as CategoryNode[] }]));
  const roots: CategoryNode[] = [];

  nodes.forEach((node) => {
    const parent = nodes.get(node.parentId);
    if (parent) parent.children.push(node);
    else roots.push(node);
  });

  return roots;
}

function normalizePath(path?: string) {
  if (!path) return "";
  return path === "/" ? path : path.replace(/\/+$/, "");
}
