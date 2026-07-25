"use client";

import { FormEvent, useId, useState } from "react";
import type { SiteProfile } from "@/lib/site-api";

type QuoteFormProps = {
  site: SiteProfile;
  subject: string;
  cart?: unknown[];
};

type FormStatus = "idle" | "submitting" | "success" | "error";

export function QuoteForm({ site, subject, cart = [] }: QuoteFormProps) {
  const id = useId();
  const [status, setStatus] = useState<FormStatus>("idle");
  const [feedback, setFeedback] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const email = String(data.get("email") ?? "").trim();
    const phone = String(data.get("phone") ?? "").trim();

    if (!email && !phone) {
      setStatus("error");
      setFeedback("Укажите телефон или электронную почту.");
      return;
    }

    setStatus("submitting");
    setFeedback("");

    const message = String(data.get("message") ?? "").trim();
    const payload = {
      site_key: site.key,
      locale: site.defaultLocale,
      company: String(data.get("company") ?? "").trim(),
      contact_name: String(data.get("contact_name") ?? "").trim(),
      email: email || null,
      phone: phone || null,
      message: message ? `${subject}\n${message}` : subject,
      page_url: window.location.href,
      utm: currentUtm(),
      ...(cart.length > 0 ? { cart } : {}),
    };

    try {
      const response = await fetch("/api/leads/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error("Lead request failed");

      form.reset();
      setStatus("success");
      setFeedback("Запрос принят. Менеджер свяжется с вами по указанному контакту.");
    } catch {
      setStatus("error");
      setFeedback("Не удалось отправить запрос. Попробуйте ещё раз позднее или используйте контакты компании.");
    }
  }

  return (
    <form className="quote-form" onSubmit={submit} aria-busy={status === "submitting"}>
      <div className="quote-form__fields">
        <label htmlFor={`${id}-company`}>Организация</label>
        <input id={`${id}-company`} name="company" autoComplete="organization" required maxLength={255} />

        <label htmlFor={`${id}-name`}>Контактное лицо</label>
        <input id={`${id}-name`} name="contact_name" autoComplete="name" required maxLength={255} />

        <div className="quote-form__split">
          <div>
            <label htmlFor={`${id}-phone`}>Телефон</label>
            <input id={`${id}-phone`} name="phone" type="tel" autoComplete="tel" maxLength={50} />
          </div>
          <div>
            <label htmlFor={`${id}-email`}>Эл. почта</label>
            <input id={`${id}-email`} name="email" type="email" autoComplete="email" maxLength={255} />
          </div>
        </div>
        <p className="quote-form__hint">Укажите телефон или электронную почту.</p>

        <label htmlFor={`${id}-message`}>Комментарий</label>
        <textarea id={`${id}-message`} name="message" rows={3} maxLength={4800} />
      </div>
      <button className="catalog-button catalog-button--light" type="submit" disabled={status === "submitting"}>
        {status === "submitting" ? "Отправляем…" : "Отправить запрос"}
      </button>
      {feedback && (
        <p className={`quote-form__status quote-form__status--${status}`} role={status === "error" ? "alert" : "status"}>
          {feedback}
        </p>
      )}
    </form>
  );
}

function currentUtm(): Record<string, string> {
  const params = new URLSearchParams(window.location.search);
  const utm: Record<string, string> = {};
  for (const key of ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]) {
    const value = params.get(key)?.trim();
    if (value) utm[key] = value;
  }

  return utm;
}
