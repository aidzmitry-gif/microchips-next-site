import { StructuredData } from "@/components/structured-data";
import type { SiteProfile } from "@/lib/site-api";

/**
 * Local organization markup is derived only from the complete verified
 * commercial profile returned by Laravel. It deliberately has no fallback to
 * a generic site name or old-catalog data: absent verification means no
 * structured business claim is emitted.
 */
export function OrganizationStructuredData({ site }: { site: SiteProfile }) {
  const profile = site.commercialProfile;
  if (!profile) return null;

  return (
    <StructuredData
      value={{
        "@context": "https://schema.org",
        "@type": "Organization",
        name: profile.legalName,
        url: `https://${site.domain}/`,
        email: profile.email,
        telephone: profile.phones,
        address: {
          "@type": "PostalAddress",
          streetAddress: profile.legalAddress,
          addressCountry: site.countryCode,
        },
        ...(profile.workingHours ? { openingHours: profile.workingHours } : {}),
      }}
    />
  );
}
