import type { SiteProfile } from "@/lib/site-api";

export function CommercialProfile({ site }: { site: SiteProfile }) {
  const profile = site.commercialProfile;
  if (!profile) return null;

  return (
    <section className="commercial-profile" aria-labelledby="commercial-profile-title">
      <p className="catalog-eyebrow">Условия для {site.countryCode === "BY" ? "Беларуси" : "этого региона"}</p>
      <h2 id="commercial-profile-title">Реквизиты и порядок работы</h2>
      <dl>
        <div><dt>Юрлицо</dt><dd>{profile.legalName}</dd></div>
        <div><dt>Адрес</dt><dd>{profile.legalAddress}</dd></div>
        <div><dt>Телефоны</dt><dd>{profile.phones.join("; ")}</dd></div>
        <div><dt>E-mail</dt><dd><a href={`mailto:${profile.email}`}>{profile.email}</a></dd></div>
        {profile.workingHours && <div><dt>Режим</dt><dd>{profile.workingHours}</dd></div>}
        {profile.pickupAddress && <div><dt>Самовывоз</dt><dd>{profile.pickupAddress}</dd></div>}
      </dl>
      <p><strong>Оплата:</strong> {profile.paymentTerms}</p>
      <p><strong>Доставка:</strong> {profile.deliveryTerms}</p>
      <p><strong>Гарантия:</strong> {profile.warrantyTerms}</p>
    </section>
  );
}
