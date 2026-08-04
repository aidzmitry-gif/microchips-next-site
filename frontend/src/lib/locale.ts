/**
 * Produces a safe HTML language tag from the locale marker set by the site
 * resolver. Keep this outside Next.js entry modules: layouts may only export
 * framework-recognised fields.
 */
export function languageForLocale(value: string | null): string {
  return value && /^[a-z]{2,3}$/i.test(value) ? value.toLowerCase() : "ru";
}
