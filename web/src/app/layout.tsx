import type { Metadata, Viewport } from "next";
import { body, cond, serif } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "burp!", template: "%s · burp!" },
  description: "Le ricette dei reel che salvi, in una libreria tutta tua.",
};

export const viewport: Viewport = {
  themeColor: "#f1eee8",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="it" className={`${cond.variable} ${serif.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
