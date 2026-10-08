import Link from "next/link";
import { Suspense } from "react";
import { Logo } from "@/components/stickers/Logo";
import { ApiError, type LibraryItem, api } from "@/lib/api/server";

/** Temporary home: proves the wiring to the API. The sticker-sheet library replaces it. */
export default function Home() {
  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: "32px 16px", display: "grid", gap: 16 }}>
      <Logo className="" />
      <Suspense fallback={<p>Carico la libreria…</p>}>
        <RecipeList />
      </Suspense>
      <Link href="/adesivi">Foglio adesivi</Link>
    </main>
  );
}

async function RecipeList() {
  let recipes: LibraryItem[];
  try {
    recipes = await api.listRecipes();
  } catch (error) {
    const message = error instanceof ApiError ? error.message : "Errore imprevisto.";
    return <p role="alert">{message}</p>;
  }
  return (
    <ul>
      {recipes.map((r) => (
        <li key={r.id}>
          #{r.id} {r.title} · {r.to_clarify} da chiarire
        </li>
      ))}
    </ul>
  );
}
