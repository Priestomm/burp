import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { StickerSheet } from "@/components/library/StickerSheet";
import { AdesiviRecipe } from "@/components/recipe/AdesiviRecipe";
import { SiteHeader } from "@/components/SiteHeader";
import { Loading } from "@/components/Loading";
import { ZineRecipe } from "@/components/zine/ZineRecipe";
import { ApiError, type LibraryItem, type RecipeDetail, api } from "@/lib/api/server";
import { type Theme, getTheme } from "@/lib/theme";

export const metadata: Metadata = { title: "Ricetta" };

export default function RecipePage(props: PageProps<"/ricette/[id]">) {
  // The theme is only a cookie, read at once; then the wait looks like the page to come.
  return (
    <Suspense fallback={null}>
      <Themed params={props.params} />
    </Suspense>
  );
}

async function Themed({ params }: { params: Promise<{ id: string }> }) {
  const theme = await getTheme();
  return (
    <Suspense fallback={<Loading theme={theme} label="apro la ricetta…" />}>
      <Recipe params={params} theme={theme} />
    </Suspense>
  );
}

async function Recipe({ params, theme }: { params: Promise<{ id: string }>; theme: Theme }) {
  const { id } = await params;
  const recipeId = Number(id);
  if (!Number.isInteger(recipeId)) notFound();
  let recipe: RecipeDetail;
  let library: LibraryItem[];
  try {
    [recipe, library] = await Promise.all([api.getRecipe(recipeId), api.listRecipes()]);
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
