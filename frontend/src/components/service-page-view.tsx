import Link from "next/link";
import { CommercialProfile } from "@/components/commercial-profile";
import { QuoteForm } from "@/components/quote-form";
import type { ServicePageDefinition } from "@/data/service-pages";
import type { SitePagePayload } from "@/lib/site-api";

export function ServicePageView({ page, definition }: { page: SitePagePayload; definition: ServicePageDefinition }) {
  return (
    <article className="product-page service-page">
      <nav className="catalog-breadcrumbs" aria-label="Хлебные крошки">
        <Link href="/">Главная</Link>
        <span aria-hidden="true">/</span>
        <span>Услуги</span>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{page.page.h1}</span>
      </nav>

      <section className="service-page__hero">
        <div>
          <p className="catalog-eyebrow">{definition.eyebrow}</p>
          <h1>{page.page.h1}</h1>
          {page.page.content && <p className="product-page__lead">{page.page.content}</p>}
          <div className="home-actions">
            <a className="catalog-button" href="#service-request">Запросить расчёт</a>
            <Link className="catalog-button catalog-button--secondary" href="/contacts">Контакты</Link>
          </div>
        </div>
        <aside className="service-page__summary" aria-label="Условия расчёта">
          <strong>Цена и срок — после проверки данных</strong>
          <p>Не публикуем неподтверждённую стоимость. Менеджер рассчитает работы для конкретной батареи и задачи.</p>
        </aside>
      </section>

      <section className="service-page__details" aria-labelledby="service-details-title">
        <div>
          <p className="catalog-eyebrow">Для предварительной оценки</p>
          <h2 id="service-details-title">Что приложить к запросу</h2>
        </div>
        <ul>
          {definition.requiredDetails.map((detail) => <li key={detail}>{detail}</li>)}
        </ul>
      </section>

      <section className="home-process service-page__process" aria-labelledby="service-process-title">
        <div><p className="catalog-eyebrow">Порядок работы</p><h2 id="service-process-title">От диагностики до согласованного решения</h2></div>
        <ol>
          {definition.workItems.map((item, index) => (
            <li key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{["Исходные данные", "Решение", "Выполнение"][index]}</strong><p>{item}</p></li>
          ))}
        </ol>
      </section>

      <section className="catalog-quote" id="service-request" aria-labelledby="service-quote-title">
        <div>
          <p className="catalog-eyebrow">Запрос по услуге</p>
          <h2 id="service-quote-title">Рассчитать работы для {definition.equipment}</h2>
          <p>Укажите параметры и симптомы. Если данных недостаточно, менеджер уточнит, что потребуется для диагностики.</p>
        </div>
        <QuoteForm site={page.site} subject={`Услуга: ${definition.subject}`} />
      </section>

      <CommercialProfile site={page.site} />
    </article>
  );
}
