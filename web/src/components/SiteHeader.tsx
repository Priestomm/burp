import Link from "next/link";
import { Logo } from "@/components/stickers/Logo";
import styles from "./SiteHeader.module.css";

export function SiteHeader() {
  return (
    <header className={styles.nav}>
      <nav className={`${styles.links} cond`} aria-label="Sezioni">
        <Link href="/">Libreria</Link>
      </nav>
      <Link href="/" className={styles.logo} aria-label="burp!, torna alla libreria">
        <Logo />
      </Link>
      <div className={styles.right} />
    </header>
  );
}
