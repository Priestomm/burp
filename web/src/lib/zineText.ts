/** Small Italian phrases for the Zine page, built from the recipe's data. */

const FEMININE_COURSES = new Set(["colazione", "salsa", "bevanda"]);
const DIET = { vegan: "vegano", vegetarian: "vegetariano", neither: null } as const;

/** "gommosi e glassati. Antipasto giapponese, vegano." */
export function subtitle(
  descriptor: string | null,
  course: string | null,
  cuisine: string | null,
  diet: keyof typeof DIET,
): string {
  const feminine = course ? FEMININE_COURSES.has(course) : false;
  // Cuisines come from the model as "italiana" (la cucina): agree them with the course.
  const agreed = cuisine && !feminine && cuisine.endsWith("a") ? `${cuisine.slice(0, -1)}o` : cuisine;
  const dietWord = DIET[diet] && feminine ? `${DIET[diet]!.slice(0, -1)}a` : DIET[diet];
  const kind = [course, agreed].filter(Boolean).join(" ");
  const facts = [kind, dietWord].filter(Boolean).join(", ");
  const parts = [descriptor, facts ? capitalize(facts) : null].filter(Boolean);
  return parts.length ? `${parts.join(". ")}.` : "";
}

/** Plural of a course for the menu: "primo" -> "primi", "piatto unico" -> "piatti unici". */
export function coursePlural(course: string): string {
  const special: Record<string, string> = {
    "piatto unico": "piatti unici",
    colazione: "colazioni",
    salsa: "salse",
    bevanda: "bevande",
    dolce: "dolci",
    snack: "snack",
  };
  if (special[course]) return special[course];
  return course.endsWith("o") ? `${course.slice(0, -1)}i` : course;
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
