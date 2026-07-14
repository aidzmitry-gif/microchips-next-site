import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { getCurrentHost, resolveSitePath, type ResolvedPayload } from "@/lib/site-api";

type PageProps = { params: Promise<{ path?: string[] }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const path = toPath((await params).path);
  const resolved = await resolveForCurrentHost(path);

  if (!("seo" in resolved)) {
    return { title: "Microchips" };
  }

  return {
    title: resolved.seo.title,
    description: resolved.seo.description ?? undefined,
    robots: resolved.seo.isIndexable ? { index: true, follow: true } : { index: false, follow: false },
    alternates: {
      canonical: new URL(resolved.seo.canonicalPath, `https://${resolved.site.domain}`).toString(),
      languages: resolved.seo.hreflang,
    },
  };
}

export default async function SitePage({ params }: PageProps) {
  const path = toPath((await params).path);
  const resolved = await resolveForCurrentHost(path);

  if (resolved.kind === "redirect") {
    redirect(resolved.redirect.to);
  }

  if (resolved.kind === "not_found") {
    notFound();
  }

  if (resolved.kind === "unavailable") {
    return <Unavailable />;
  }

  const { site } = resolved;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-6 px-6 py-5">
          <a className="text-lg font-bold tracking-tight" href="/">{site.name}</a>
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span>{site.countryCode}</span>
            <span className="rounded-full bg-slate-100 px-3 py-1">{site.defaultLocale}</span>
          </div>
        </div>
      </header>
      <section className="mx-auto w-full max-w-6xl px-6 py-14">
        <p className="mb-4 text-sm font-medium uppercase tracking-[0.16em] text-cyan-700">B2B supply platform</p>
        <Content resolved={resolved} />
      </section>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap gap-4 px-6 py-6 text-sm text-slate-500">
          <span>Регион определяется доменом, без IP-переадресации.</span>
          <span>{site.currencyCode}</span>
        </div>
      </footer>
    </main>
  );
}

function Content({ resolved }: { resolved: Exclude<ResolvedPayload, { kind: "redirect" | "not_found" | "unavailable" }> }) {
  if (resolved.kind === "product") {
    return (
      <article className="grid gap-10 lg:grid-cols-[1fr_20rem]">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{resolved.product.name}</h1>
          {resolved.product.description && <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-600">{resolved.product.description}</p>}
          {resolved.product.attributes && (
            <dl className="mt-10 grid max-w-3xl divide-y divide-slate-200 border-y border-slate-200">
              {Object.entries(resolved.product.attributes).map(([name, value]) => (
                <div className="grid grid-cols-2 gap-6 py-3 text-sm" key={name}>
                  <dt className="text-slate-500">{name}</dt><dd className="font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
        <aside className="h-fit rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">Наличие</p><p className="mt-1 font-semibold">{resolved.product.availability}</p>
          {resolved.product.price ? <p className="mt-6 text-2xl font-semibold">{resolved.product.price} {resolved.product.currency}</p> : <p className="mt-6 text-sm text-slate-600">Цена — по запросу</p>}
          <button className="mt-6 w-full rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white" type="button">Запросить КП</button>
        </aside>
      </article>
    );
  }

  if (resolved.kind === "category") {
    return <article><h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{resolved.category.name}</h1><p className="mt-6 text-lg text-slate-600">Региональная витрина категории. Товары и коммерческие условия выводятся только после проверки для этого рынка.</p></article>;
  }

  return (
    <article className="max-w-4xl">
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{resolved.page.h1}</h1>
      {resolved.page.content && <p className="mt-7 text-lg leading-8 text-slate-600">{resolved.page.content}</p>}
      <div className="mt-10 rounded-2xl border border-cyan-100 bg-cyan-50 p-6 text-sm leading-6 text-cyan-950">До запуска заполните для этого домена реальные контакты, юридическое лицо, оплату, доставку, документы и локальные кейсы. Это обязательное условие для индексации коммерческих страниц.</div>
    </article>
  );
}

function Unavailable() {
  return <main className="grid min-h-screen place-items-center bg-slate-950 p-6 text-white"><div className="max-w-md"><p className="text-sm font-medium uppercase tracking-[0.16em] text-cyan-300">Microchips platform</p><h1 className="mt-4 text-3xl font-semibold">Витрина ожидает подключения каталога</h1><p className="mt-4 leading-7 text-slate-300">Запустите Laravel API и укажите LARAVEL_API_URL. Публичные страницы не должны индексироваться до прохождения регионального SEO-чеклиста.</p></div></main>;
}

async function resolveForCurrentHost(path: string) {
  return resolveSitePath(await getCurrentHost(), path);
}

function toPath(segments?: string[]): string {
  return segments?.length ? `/${segments.join("/")}` : "/";
}
