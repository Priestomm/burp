import { Suspense } from "react";
import { Loading } from "@/components/Loading";
import { ZineLibrary } from "@/components/zine/ZineLibrary";
import { ApiError, type LibraryItem, api } from "@/lib/api/server";

export default function LibraryPage(props: PageProps<"/">) {
  return (
    <Suspense fallback={<Loading label="apro la libreria…" />}>
      <Library searchParams={props.searchParams} />
    </Suspense>
  );
}

async function Library({ searchParams }: { searchParams: PageProps<"/">["searchParams"] }) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";
  const toCook = params["da-cucinare"] === "1";
  let items: LibraryItem[];
  try {
    items = await api.listRecipes(query || undefined);
  } catch (error) {
    return <p role="alert" style={{ padding: 24 }}>{error instanceof ApiError ? error.message : "Errore imprevisto."}</p>;
  }
  if (toCook) items = items.filter((item) => item.cooked.count === 0);
  return (
    <ZineLibrary
      items={items}
      query={query}
      heading={toCook ? "Da cucinare" : "La tua libreria"}
      empty={
        query
          ? `Nessuna ricetta per «${query}».`
          : toCook
            ? "Le hai cucinate tutte. Burp!"
            : "Ancora nessun numero: inoltra un reel al bot per cominciare."
      }
    />
  );
}
