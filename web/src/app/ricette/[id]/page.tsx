import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { StickerSheet } from "@/components/library/StickerSheet";
import { RecipeView } from "@/components/recipe/RecipeView";
import { SiteHeader } from "@/components/SiteHeader";
import { ApiError, type RecipeDetail, api } from "@/lib/api/server";

export const metadata: Metadata = { title: "Ricetta" };

export default function RecipePage(props: PageProps<"/ricette/[id]">) {
  return (
    <>
      <SiteHeader />
      <Suspense fallback={null}>
        <Sheet params={props.params} />
      </Suspense>
      <Suspense fallback={<p style={{ padding: 24 }}>Apro la ricetta…</p>}>
        <Recipe params={props.params} />
      </Suspense>
    </>
  );
}

async function Recipe({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const recipeId = Number(id);
  if (!Number.isInteger(recipeId)) notFound();
  let recipe: RecipeDetail;
  try {
    recipe = await api.getRecipe(recipeId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    const message = error instanceof ApiError ? error.message : "Errore imprevisto.";
    return (
      <p role="alert" style={{ padding: 24 }}>
        {message}
      </p>
    );
  }
  return <RecipeView recipe={recipe} />;
}

async function Sheet({ params }: { params: Promise<{ id: string }> }) {
  const [{ id }, items] = await Promise.all([params, api.listRecipes().catch(() => null)]);
  if (!items) return null; // the recipe below reports the API error
  return <StickerSheet items={items} openId={Number(id)} />;
}
