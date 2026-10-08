import Link from "next/link";
import { RecipeSticker } from "@/components/stickers/named";
import type { LibraryItem } from "@/lib/api/server";
import styles from "./StickerSheet.module.css";

function describe(item: LibraryItem, open: boolean): string {
  const parts = [
    item.title,
    item.to_clarify === 0 ? "tutto chiaro" : `${item.to_clarify} da chiarire`,
  ];
  if (item.cooked.count > 0) parts.push(`cucinata ${item.cooked.count === 1 ? "1 volta" : `${item.cooked.count} volte`}`);
  if (open) parts.push("aperta");
  return parts.join(", ");
}

/** The library as a sheet of stickers; the open recipe is the one peeled off. */
export function StickerSheet({
  items,
  openId,
  layout = "strip",
}: {
  items: LibraryItem[];
  openId?: number;
  layout?: "strip" | "grid";
}) {
  return (
    <nav className={`${styles.sheet} ${styles[layout]}`} aria-label="La tua libreria">
      <span className={styles.label} aria-hidden="true">
        la tua libreria
      </span>
      <ul>
        {items.map((item) => {
          const open = item.id === openId;
          return (
            <li key={item.id}>
              <Link
                href={`/ricette/${item.id}`}
                className={styles.sticker}
                aria-label={describe(item, open)}
                aria-current={open ? "page" : undefined}
              >
                <RecipeSticker
                  id={item.id}
                  line1={item.nome_riga_1}
                  line2={item.nome_riga_2}
                  toClarify={item.to_clarify}
                  cooked={item.cooked.count > 0}
                  lifted={open}
                />
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
