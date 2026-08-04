import { createServer } from "node:http";

const site = {
  key: "microchips-by",
  domain: "microchips.by",
  countryCode: "BY",
  currencyCode: "BYN",
  defaultLocale: "ru-BY",
  name: "Microchips",
  availablePagePaths: ["/contacts"],
  availablePages: { contacts: "/contacts" },
  commercialProfile: {
    legalName: "ООО «Аккумуляторные решения»",
    legalAddress: "220035, г. Минск, ул. Тимирязева, 65А, пом. 407",
    phones: ["+375 (33) 347-75-10", "+375 (17) 396-23-02"],
    email: "order@microchips.by",
    workingHours: "Пн–Пт: 9:00–17:00",
    pickupAddress: "г. Минск, ул. Тимирязева, 65А, офис 408",
    deliveryTerms: "Самовывоз по предварительному согласованию; условия доставки согласуются по заявке.",
    paymentTerms: "Оплата по счёту для организаций.",
    warrantyTerms: "Гарантийные условия подтверждаются в коммерческом предложении.",
  },
  locales: [{ locale: "ru-BY", language: "ru", isDefault: true }],
};

const categories = [{
  slug: "akkumulyatory",
  name: "Аккумуляторы",
  path: "/catalog/akkumulyatory",
  children: [{ slug: "gel", name: "GEL аккумуляторы", path: "/catalog/akkumulyatory/gel", children: [] }],
}];

const product = {
  name: "Аккумулятор Sonnenschein Dryfit Solar Block SB 12/130 A для ИБП (GEL, 130Ah)",
  sku: "TEST-SB-12130",
  mpn: "SB 12/130 A",
  manufacturer: "Sonnenschein",
  description: null,
  attributes: { "Технология": "GEL", "Ёмкость": "130 А·ч" },
  availability: "on_request",
  price: null,
  currency: "BYN",
};

const seo = (path) => ({
  locale: "ru-BY",
  title: "Тестовая карточка — Microchips",
  description: null,
  canonicalPath: path,
  isIndexable: false,
  schema: { "@context": "https://schema.org", "@type": "Product", name: product.name },
  hreflang: { "ru-BY": `https://microchips.by${path}` },
});

const legacyPreviewProduct = {
  legacy_id: 742,
  name: "Аккумулятор EnerSys Cyclon X Cell (AGM, 5 Ah, 2V)",
  preview_path: "/legacy-preview/product/742",
  legacy_url_candidate: "/catalog/akkumulyatory/promyshlennye/742/",
  primary_section_path: "akkumulyatory/promyshlennye",
  matched_section_paths: ["akkumulyatory/promyshlennye", "akkumulyatory/promyshlennye/dlya_rezervnogo_pitaniya"],
  description: "Исходное описание из снимка Bitrix. Данные требуют проверки.",
  one_c: { external_id: "КА-00005195", name: null, article: null },
  transfer_status: "candidate_duplicate_group",
  has_staging_image: true,
  image_path: "/api/v1/sites/microchips-by/legacy-preview/media/742",
  source_notice: "Legacy Bitrix snapshot evidence. Not published; facts require review before canonical use.",
};

const legacyPreviewMeta = {
  snapshot_run_id: 742,
  current_page: 1,
  last_page: 1,
  per_page: 24,
  total: 1,
  snapshot_total: 1569,
  visible_scope_total: 1562,
  excluded_total: 7,
  status_counts: { candidate_duplicate_group: 430 },
  filters: { q: null, category: null, status: null, sort: "legacy_id" },
};

function send(response, status, body) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(body));
}

const server = createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:3101");
  if (request.method === "POST" && url.pathname === "/api/v1/leads/quote") {
    let data = "";
    request.on("data", (chunk) => { data += chunk; });
    request.on("end", () => {
      const body = JSON.parse(data || "{}");
      const valid = body.company && body.contact_name && (body.email || body.phone) && /^https:\/\/microchips\.by\//.test(body.page_url ?? "");
      send(response, valid ? 201 : 422, valid ? { id: 1001, status: "new" } : { message: "Invalid test lead" });
    });
    return;
  }

  if (request.method !== "GET") return send(response, 405, { message: "Method not allowed" });
  if (url.pathname === "/api/v1/sites/microchips-by/legacy-preview/categories") {
    return send(response, 200, { data: [{
      external_id: "427", name: "Промышленные аккумуляторы", source_path: "akkumulyatory/promyshlennye",
      path: "/legacy-preview/catalog/akkumulyatory/promyshlennye", count: 1, children: [],
    }], meta: { snapshot_run_id: 742, categories_total: 220 } });
  }
  if (url.pathname === "/api/v1/sites/microchips-by/legacy-preview/products") {
    return send(response, 200, { data: [legacyPreviewProduct], meta: legacyPreviewMeta });
  }
  if (url.pathname === "/api/v1/sites/microchips-by/legacy-preview/products/742") {
    return send(response, 200, { data: legacyPreviewProduct, meta: { snapshot_run_id: 742 } });
  }
  if (url.pathname === "/api/v1/sites/microchips-by/legacy-preview/media/742") {
    const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg==", "base64");
    response.writeHead(200, { "content-type": "image/png", "cache-control": "private, no-store" });
    response.end(png);
    return;
  }
  if (url.pathname === "/api/v1/sites/microchips-by/catalog/categories") return send(response, 200, { data: categories });
  if (url.pathname === "/api/v1/sites/microchips-by/catalog/products") {
    return send(response, 200, {
      data: [{ slug: "sonnenschein-sb-12-130", path: "/catalog/akkumulyatory/sonnenschein-sb-12-130", ...product }],
      meta: { current_page: 1, last_page: 1, total: 1 },
    });
  }

  const match = url.pathname.match(/^\/api\/v1\/sites\/microchips\.by\/resolve$/);
  if (!match) return send(response, 404, { message: "Not found" });
  const path = url.searchParams.get("path") ?? "/";
  if (path === "/catalog/akkumulyatory") return send(response, 200, { kind: "category", site, path, category: { name: "Аккумуляторы", slug: "akkumulyatory" }, seo: seo(path) });
  if (path === "/catalog/akkumulyatory/sonnenschein-sb-12-130") return send(response, 200, { kind: "product", site, path, product, seo: seo(path) });
  if (path === "/") return send(response, 200, { kind: "page", site, path, page: { title: "Главная", h1: "Промышленные аккумуляторы", content: "Тестовая витрина.", locale: "ru-BY" }, seo: seo(path) });
  return send(response, 404, { message: "Not found" });
});

server.listen(3101, "127.0.0.1");
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.close(() => process.exit(0)));
