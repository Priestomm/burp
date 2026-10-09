import type { Metadata, Viewport } from "next";
import { grot, wide } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "burp!", template: "%s · burp!" },
  description: "Le ricette dei reel che salvi, in una libreria tutta tua.",
};

export const viewport: Viewport = {
  themeColor: "#ffd13b",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="it"
      className={`${wide.variable} ${grot.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
