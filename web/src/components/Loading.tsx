import { BURP } from "@/components/marker/paths";
import { Marker } from "@/components/marker/Marker";
import styles from "./zine/zine.module.css";

/** What a page shows while the library answers: a blank sheet, the marker writing burp! */
export function Loading({ label }: { label: string }) {
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
