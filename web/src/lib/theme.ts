import { cookies } from "next/headers";

export const THEMES = ["adesivi", "zine"] as const;
export type Theme = (typeof THEMES)[number];
export const THEME_COOKIE = "burp-theme";

export function isTheme(value: unknown): value is Theme {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

/** The chosen look. A runtime read: call it inside a Suspense boundary. */
export async function getTheme(): Promise<Theme> {
  const value = (await cookies()).get(THEME_COOKIE)?.value;
  return isTheme(value) ? value : "adesivi";
}
