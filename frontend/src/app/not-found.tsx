import Link from "next/link";

export default function NotFound() {
  return (
    <main className="route-state">
      <div className="route-state__panel">
        <p className="catalog-eyebrow">Ошибка 404</p>
        <h1>Страница не найдена</h1>
        <p>Адрес мог измениться, либо эта позиция ещё не опубликована для регионального сайта.</p>
        <div className="route-state__actions">
          <Link className="catalog-button" href="/catalog">Перейти в каталог</Link>
          <Link className="catalog-button catalog-button--light" href="/">На главную</Link>
        </div>
      </div>
    </main>
  );
}
