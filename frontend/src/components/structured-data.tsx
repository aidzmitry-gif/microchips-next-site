export function StructuredData({ value }: { value: unknown }) {
  if (!isStructuredData(value)) return null;

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: serializeStructuredData(value) }}
    />
  );
}

export function isStructuredData(value: unknown): value is Record<string, unknown> | unknown[] {
  return value !== null && typeof value === "object";
}

export function serializeStructuredData(value: Record<string, unknown> | unknown[]) {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
