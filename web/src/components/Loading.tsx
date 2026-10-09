import { SiteHeader } from "@/components/SiteHeader";
import { BURP } from "@/components/marker/paths";
import { Marker } from "@/components/marker/Marker";
import type { Theme } from "@/lib/theme";
import styles from "./zine/zine.module.css";

/** What a page shows while the library answers, in the look the user chose. */
export function Loading({ theme, label }: { theme: Theme; label: string }) {
  if (theme === "zine") {
    return (
      <div className={styles.sheet} role="status">
        <div className={styles.top}>
          <div className={styles.copy}>
            <div className={styles.blank} />
            <span className={`${styles.tape} ${styles.t1}`} aria-hidden="true" />
            <span className={`${styles.tape} ${styles.t2}`} aria-hidden="true" />
            <Marker drawing={BURP} width={13} draw className={`${styles.scrawl} ${styles.again}`} />
          </div>
        </div>
        <p className={styles.waiting}>{label}</p>
      </div>
    );
  }
  return (
    <>
      <SiteHeader />
      <p className="cond" role="status" style={{ padding: "48px 24px", fontSize: 40, textAlign: "center" }}>
        {label}
      </p>
    </>
  );
}
