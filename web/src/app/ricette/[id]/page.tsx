import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { Loading } from "@/components/Loading";
import { ZineRecipe } from "@/components/zine/ZineRecipe";
import { ApiError, type LibraryItem, type RecipeDetail, api } from "@/lib/api/server";

export const metadata: Metadata = { title: "Ricetta" };

export default function RecipePage(props: PageProps<"/ricette/[id]">) {
  return (
    <Suspense fallback={<Loading label="apro la ricetta…" />}>
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
  return <ZineRecipe recipe={recipe} library={library} />;
}
