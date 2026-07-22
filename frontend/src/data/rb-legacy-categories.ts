export type LegacyCategoryRow = {
  id: string;
  parentId: string;
  name: string;
  path: string;
};

// Curated first-focus taxonomy from docs/imports/site-catalog-full-categories.csv.
// Thin medical/scanner/device-brand branches are intentionally excluded until review.
export const rbLegacyCategoryRows: LegacyCategoryRow[] = [
  {
    id: "409",
    parentId: "372",
    name: "Для ИБП",
    path: "/catalog/akkumulyatory/dlya_ibp",
  },
  {
    id: "410",
    parentId: "409",
    name: "AGM",
    path: "/catalog/akkumulyatory/dlya_ibp/agm",
  },
  {
    id: "411",
    parentId: "409",
    name: "GEL",
    path: "/catalog/akkumulyatory/dlya_ibp/gelevye",
  },
  {
    id: "415",
    parentId: "409",
    name: "OPzS",
    path: "/catalog/akkumulyatory/dlya_ibp/opzs",
  },
  {
    id: "414",
    parentId: "427",
    name: "Для резервного питания",
    path: "/catalog/akkumulyatory/promyshlennye/dlya_rezervnogo_pitaniya",
  },
  {
    id: "425",
    parentId: "489",
    name: "Источники бесперебойного питания",
    path: "/catalog/istochniki-pitaniya/ibp",
  },
];
