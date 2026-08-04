import type { Metadata } from "next";
import { headers } from "next/headers";
import { languageForLocale } from "@/lib/locale";
import "./globals.css";

export const metadata: Metadata = {
  title: "Microchips platform",
  description: "Multi-market B2B catalogue platform",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const language = languageForLocale((await headers()).get("x-site-language"));

  return (
    <html
      lang={language}
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
