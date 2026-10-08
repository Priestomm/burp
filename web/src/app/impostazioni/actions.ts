"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { THEME_COOKIE, isTheme } from "@/lib/theme";

/** Save the chosen theme for a year; the data and the logic are the same in every theme. */
export async function chooseTheme(formData: FormData): Promise<void> {
  const theme = formData.get("theme");
  if (isTheme(theme)) {
    (await cookies()).set(THEME_COOKIE, theme, {
      maxAge: 60 * 60 * 24 * 365,
      path: "/",
      sameSite: "lax",
    });
  }
  redirect("/impostazioni?salvato=1");
}
