export function availabilityLabel(availability: string) {
  const labels: Record<string, string> = {
    in_stock: "В наличии",
    out_of_stock: "Нет в наличии",
    on_request: "Поставка по запросу",
    preorder: "Под заказ",
  };

  return labels[availability] ?? "Наличие требует подтверждения";
}

export function priceLabel(price: string | null, currency: string) {
  const value = price?.trim();

  return value ? `${value} ${currency}`.trim() : "Цена по запросу";
}
