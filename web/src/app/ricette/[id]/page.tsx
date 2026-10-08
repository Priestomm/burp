import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { StickerSheet } from "@/components/library/StickerSheet";
import { AdesiviRecipe } from "@/components/recipe/AdesiviRecipe";
import { SiteHeader } from "@/components/SiteHeader";
import { ZineRecipe } from "@/components/zine/ZineRecipe";
import { ApiError, type LibraryItem, type RecipeDetail, api } from "@/lib/api/server";
import { getTheme } from "@/lib/theme";

export const metadata: Metadata = { title: "Ricetta" };

export default function RecipePage(props: PageProps<"/ricette/[id]">) {
  return (
    <Suspense fallback={<p style={{ padding: 24 }}>Apro la ricetta…</p>}>
      <Recipe params={props.params} />
    </Suspense>
  );
}

async function Recipe({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const recipeId = Number(id);
  if (!Number.isInteger(recipeId)) notFound();
  let recipe: RecipeDetail;
  let library: LibraryItem[];
  let theme: Awaited<ReturnType<typeof getTheme>>;
  try {
    [recipe, library, theme] = await Promise.all([api.getRecipe(recipeId), api.listRecipes(), getTheme()]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    const message = error instanceof ApiError ? error.message : "Errore imprevisto.";
    return (
      <p role="alert" style={{ padding: 24 }}>
        {message}
      </p>
    );
  }
  if (theme === "zine") return <ZineRecipe recipe={recipe} library={library} />;
  return (
    <>
      <SiteHeader />
      <StickerSheet items={library} openId={recipeId} />
      <AdesiviRecipe recipe={recipe} />
    </>
  );
}
