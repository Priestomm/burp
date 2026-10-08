import { describe, expect, it } from "vitest";
import { markTimes } from "./annotate";

const marked = (step: string) => markTimes(step).filter((s) => s.mark).map((s) => s.text);

describe("markTimes", () => {
  it.each([
    ["Cuoci in acqua bollente salata per 7-8 minuti, finché vengono a galla.", ["7-8 minuti"]],
    ["Inforna a 180° per 25 min.", ["180°", "25 min"]],
    ["Preriscalda il forno a 200 °C.", ["200 °C"]],
    ["Lascia riposare 1 ora, poi altri 30 secondi.", ["1 ora", "30 secondi"]],
    ["Fai lievitare mezz'ora, oppure una notte in frigo.", ["mezz'ora", "una notte"]],
    ["Cuoci 2 o 3 minuti per lato.", ["2 o 3 minuti"]],
    ["Scalda 1,5 ore a 90 gradi.", ["1,5 ore", "90 gradi"]],
  ])("%s", (step, expected) => {
    expect(marked(step)).toEqual(expected);
  });

  it("leaves quantities and plain numbers alone", () => {
    expect(marked("Aggiungi 200 g di farina e 2 uova, poi mescola.")).toEqual([]);
    expect(marked("Forma 12 palline.")).toEqual([]);
  });

  it("keeps all the text, in order", () => {
    const step = "Cuoci 7-8 minuti e servi.";
    expect(markTimes(step).map((s) => s.text).join("")).toBe(step);
  });
});
