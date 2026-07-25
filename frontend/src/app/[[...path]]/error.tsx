"use client";

import Link from "next/link";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="route-state">
      <div className="route-state__panel" role="alert">
        <p className="catalog-eyebrow">Ошибка загрузки</p>
        <h1>Не удалось открыть страницу</h1>
        <p>Опубликованные данные не были показаны, чтобы не подменять их неподтверждённой информацией.</p>
        <div className="route-state__actions">
          <button className="catalog-button" type="button" onClick={reset}>Попробовать ещё раз</button>
          <Link className="catalog-button catalog-button--light" href="/">На главную</Link>
        </div>
      </div>
    </main>
  );
}
