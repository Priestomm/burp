"use client";

import { type PointerEvent, type RefObject, useEffect, useRef, useState } from "react";
import { saveDrawing } from "@/app/ricette/[id]/actions";
import type { Stroke } from "@/lib/api/server";
import { MAX_STROKES, type Point, livePath, middle, placement, thin, toPath } from "@/lib/drawing";
import styles from "./zine.module.css";

/**
 * The marker mode of the Zine page (phase 2): draw by hand on the recipe. Each stroke is saved
 * against the element it starts on, marked in the page with `data-anchor`, so it stays on its
 * ingredient or step at any screen width. The whole drawing is saved after every stroke.
 */
export function useDrawing(recipeId: number, initial: Stroke[], sheet: RefObject<HTMLElement | null>) {
  const [strokes, setStrokes] = useState(initial);
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState("");
  // Where each anchor is now, measured after layout changes: anchor -> SVG transform.
  const [places, setPlaces] = useState<Record<string, string>>({});
  const saving = useRef<Promise<void>>(Promise.resolve());

  const measure = () => {
    if (sheet.current) setPlaces(anchorPlaces(sheet.current));
  };

  useEffect(() => {
    const page = sheet.current;
    if (!page) return;
    const update = () => setPlaces(anchorPlaces(page));
    // Fires once at once, then whenever the page changes size: images loading, text wrapping.
    const observer = new ResizeObserver(update);
    observer.observe(page);
    document.fonts?.ready.then(update);
    return () => observer.disconnect();
  }, [sheet]);

  useEffect(() => {
    if (!active) return;
    const leave = (event: KeyboardEvent) => event.key === "Escape" && setActive(false);
    window.addEventListener("keydown", leave);
    return () => window.removeEventListener("keydown", leave);
  }, [active]);

  function change(next: Stroke[], done: string) {
    setStrokes(next);
    measure();
    // One save after the other, so a slow request never overwrites a newer drawing.
    saving.current = saving.current.then(async () => {
      try {
        const result = await saveDrawing(recipeId, next);
        setMessage(result.ok ? done : `Disegno non salvato: ${result.error}`);
      } catch {
        // The server restarted since this page was opened, or is off: the action is gone.
        setMessage("Disegno non salvato: ricarica la pagina e riprova.");
      }
    });
  }

  return {
    /** Only failures: the rest is said to screen readers by the page. */
    problem: message.startsWith("Disegno non salvato") || message.startsWith("Troppi") ? message : "",
    strokes,
    places,
    active,
    message,
    toggle: () => setActive((on) => !on),
    add: (stroke: Stroke) => {
      if (strokes.length >= MAX_STROKES) {
        setMessage("Troppi tratti su questa ricetta: cancellane qualcuno.");
        return;
      }
      change([...strokes, stroke], "Tratto salvato.");
    },
    undo: () => change(strokes.slice(0, -1), "Ultimo tratto tolto."),
    clear: () => change([], "Disegno cancellato."),
  };
}

/** Where each anchor of the page is now, as the SVG transform of its strokes. */
function anchorPlaces(page: HTMLElement): Record<string, string> {
  const box = page.getBoundingClientRect();
  const places: Record<string, string> = {};
  for (const el of [page, ...page.querySelectorAll<HTMLElement>("[data-anchor]")]) {
    places[el.dataset.anchor!] = placement(el.getBoundingClientRect(), box);
  }
  return places;
}

type Drawing = ReturnType<typeof useDrawing>;

/** The strokes over the page; in marker mode it also catches the pen. Decorative. */
export function DrawingLayer({ drawing, sheet }: { drawing: Drawing; sheet: RefObject<HTMLElement | null> }) {
  const [live, setLive] = useState<string | null>(null);
  const pen = useRef<{ layer: Element; points: Point[] } | null>(null);

  function anchorAt(x: number, y: number, layer: Element): HTMLElement {
    for (const el of document.elementsFromPoint(x, y)) {
      if (layer.contains(el)) continue;
      const anchor = el.closest<HTMLElement>("[data-anchor]");
      if (anchor && sheet.current?.contains(anchor)) return anchor;
    }
    return sheet.current!;
  }

  function down(event: PointerEvent<SVGSVGElement>) {
    if (!drawing.active || event.button > 0) return;
    event.preventDefault(); // no text selection or image drag while drawing
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = { x: event.clientX, y: event.clientY };
    pen.current = { layer: event.currentTarget, points: [point] };
    setLive(livePath([point, point], sheet.current!.getBoundingClientRect()));
  }

  function move(event: PointerEvent<SVGSVGElement>) {
    if (!pen.current) return;
    const events = event.nativeEvent.getCoalescedEvents?.() ?? [event.nativeEvent];
    for (const e of events) pen.current.points.push({ x: e.clientX, y: e.clientY });
    setLive(livePath(thin(pen.current.points), sheet.current!.getBoundingClientRect()));
  }

  function up() {
    const stroke = pen.current;
    pen.current = null;
    setLive(null);
    if (!stroke) return;
    // What the stroke is about: the element under its middle. A ring drawn around an
    // ingredient starts outside it, but its middle is the ingredient.
    const { x, y } = middle(stroke.points);
    const anchor = anchorAt(x, y, stroke.layer);
    drawing.add({
      anchor: anchor.dataset.anchor ?? "sheet",
      d: toPath(thin(stroke.points), anchor.getBoundingClientRect()),
    });
  }

  return (
    <svg
      className={`${styles.drawing} ${drawing.active ? styles.drawingOn : ""}`}
      aria-hidden="true"
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
    >
      {drawing.strokes.map((stroke, i) =>
        // A stroke whose element is not on the page now (a step of the other version) waits.
        drawing.places[stroke.anchor] ? (
          <path key={i} d={stroke.d} transform={drawing.places[stroke.anchor]} />
        ) : null,
      )}
      {live && <path d={live} />}
    </svg>
  );
}
