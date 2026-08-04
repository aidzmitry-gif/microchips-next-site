export function availabilityLabel(availability: string) {
  const labels: Record<string, string> = {
    in_stock: "В наличии",
    out_of_stock: "Нет в наличии",
    on_request: "Поставка по запросу",
    preorder: "Под заказ",
  };

  return labels[availability] ?? "Наличие требует подтверждения";
}

export function priceEvidenceLabel(price: string | null, observedAt?: string | null) {
  if (!price?.trim() || !observedAt) {
    return null;
  }

  const date = /^(\d{4})-(\d{2})-(\d{2})(?:T|$)/.exec(observedAt);
  if (!date) {
    return null;
  }

  return `Цена по данным на ${date[3]}.${date[2]}.${date[1]} · уточняйте`;
}

export function priceLabel(price: string | null, currency: string) {
  const value = price?.trim();

  return value ? `${value} ${currency}`.trim() : "Цена по запросу";
}
