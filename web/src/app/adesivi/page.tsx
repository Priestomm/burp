import type { Metadata } from "next";
import { Logo } from "@/components/stickers/Logo";
import { Mascot } from "@/components/stickers/Mascot";
import { BurpStamp, CookedFace, DietStar, RecipeSticker, ServingsBadge } from "@/components/stickers/named";
import styles from "./page.module.css";

export const metadata: Metadata = { title: "Adesivi" };

const SAMPLE = [
  { id: 1, line1: "Gnocchi", line2: "alla zucca", toClarify: 12, cooked: false },
  { id: 2, line1: "Gnocchi", line2: "di tofu", toClarify: 2, cooked: true },
  { id: 3, line1: "Curry", line2: "di spinaci e ceci con tofu", toClarify: 4, cooked: false },
  { id: 4, line1: "French toast", line2: "alla mela", toClarify: 6, cooked: false },
  { id: 5, line1: "Bistecca", line2: "di cardoncelli con crema di cannellini", toClarify: 9, cooked: false },
];

/** Every sticker component on one sheet, to check them by eye (examples, not your data). */
export default function StickersPage() {
  return (
    <main className={styles.page}>
      <h1 className="cond">Foglio adesivi</h1>
      <p>Tutti gli adesivi di burp! come componenti SVG, con dati di esempio.</p>
      <div className={styles.row}>
        <Logo className={styles.logo} />
        <Mascot className={styles.mascot} />
        <div className={styles.m}><DietStar diet="VEGANA" lines={["antipasto", "giapponese"]} /></div>
        <div className={styles.s}><ServingsBadge n={1} /></div>
        <div className={styles.s}><ServingsBadge n={3} /></div>
        <div className={styles.s}><CookedFace count={0} /></div>
        <div className={styles.m}><BurpStamp date="8 ottobre" /></div>
      </div>
      <div className={styles.sheet}>
        {SAMPLE.map((r) => (
          <div key={r.id} className={styles.stk}>
            <RecipeSticker id={r.id} line1={r.line1} line2={r.line2} toClarify={r.toClarify} cooked={r.cooked} />
          </div>
        ))}
      </div>
    </main>
  );
}
