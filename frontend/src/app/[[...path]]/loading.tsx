export default function Loading() {
  return (
    <main className="route-state route-state--loading" aria-busy="true" aria-live="polite">
      <div className="route-state__panel">
        <p className="catalog-eyebrow">Каталог</p>
        <h1>Загружаем страницу</h1>
        <p>Получаем опубликованные данные региональной витрины.</p>
        <div className="loading-lines" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
    </main>
  );
}
