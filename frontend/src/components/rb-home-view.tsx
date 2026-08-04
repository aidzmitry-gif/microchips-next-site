import Link from "next/link";
import { CommercialProfile } from "@/components/commercial-profile";
import { QuoteForm } from "@/components/quote-form";
import type { CatalogCategory, SitePagePayload } from "@/lib/site-api";

export function RbHomeView({ page, categories }: { page: SitePagePayload; categories: CatalogCategory[] }) {
  const visibleCategories = categories.filter((category) => category.path).slice(0, 8);
  const pages = page.site.availablePages ?? {};
  const lead = page.page.content?.split("Продавец:", 1)[0].trim();

  return (
    <>
      <section className="home-hero">
        <div>
          <p className="catalog-eyebrow">B2B-каталог для Беларуси</p>
          <h1>{page.page.h1}</h1>
          {lead && <p className="home-hero__lead">{lead}</p>}
          <div className="home-actions">
            <Link className="catalog-button" href="/catalog">Перейти в каталог</Link>
            <a className="catalog-button catalog-button--secondary" href="#engineering-request">Отправить техническое задание</a>
          </div>
        </div>
        <ul className="home-hero__facts" aria-label="Преимущества работы">
          <li><strong>Подбор по параметрам</strong><span>Напряжение, ёмкость, технология, габариты и режим эксплуатации.</span></li>
          <li><strong>Коммерческое предложение</strong><span>Цена и наличие подтверждаются для конкретной заявки.</span></li>
          <li><strong>Проверяемые данные</strong><span>Характеристики и документы публикуются после сверки с источником.</span></li>
        </ul>
      </section>

      {visibleCategories.length > 0 && (
        <section className="home-section" aria-labelledby="home-catalog-title">
          <div className="home-section__heading">
            <div><p className="catalog-eyebrow">Основные направления</p><h2 id="home-catalog-title">Каталог оборудования</h2></div>
            <Link href="/catalog">Смотреть всё</Link>
          </div>
          <div className="home-category-grid">
            {visibleCategories.map((category) => (
              <Link key={category.slug} href={category.path!}>
                <span>{category.name}</span>
                <small>{category.children.length > 0 ? `${category.children.length} подразделов` : "Открыть раздел"}</small>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="home-process" aria-labelledby="home-process-title">
        <div><p className="catalog-eyebrow">Работа с организациями</p><h2 id="home-process-title">От задачи до поставки</h2></div>
        <ol>
          <li><span>01</span><strong>Получаем требования</strong><p>Модель оборудования, параметры батареи, количество и условия эксплуатации.</p></li>
          <li><span>02</span><strong>Проверяем номенклатуру</strong><p>Сверяем точную модель, совместимость, документы, цену и доступность.</p></li>
          <li><span>03</span><strong>Готовим предложение</strong><p>Фиксируем согласованные позиции и коммерческие условия в счёте или КП.</p></li>
        </ol>
      </section>

      <section className="catalog-quote" id="engineering-request" aria-labelledby="home-quote-title">
        <div>
          <p className="catalog-eyebrow">Инженерный запрос</p>
          <h2 id="home-quote-title">Нужен подбор аккумулятора или системы питания?</h2>
          <p>Приложите модель оборудования или укажите напряжение, ёмкость, мощность, габариты и режим работы. Мы проверим доступные решения и вернёмся с уточнениями.</p>
          <nav className="home-commercial-links" aria-label="Коммерческие условия">
            {pages.delivery && <Link href={pages.delivery}>Доставка</Link>}
            {pages.payment && <Link href={pages.payment}>Оплата</Link>}
            {pages.warranty && <Link href={pages.warranty}>Гарантия</Link>}
            {pages.contacts && <Link href={pages.contacts}>Контакты</Link>}
          </nav>
        </div>
        <QuoteForm site={page.site} subject="Подбор аккумулятора или системы питания" />
      </section>

      <CommercialProfile site={page.site} />
    </>
  );
}
