import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Microchips platform",
  description: "Multi-market B2B catalogue platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ru"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
