"""How recipes are shown to people: shared by the CLI and the Telegram bot."""

from burp.library import SavedRecipe
from burp.models import ImportedRecipe

DIET_LABELS = {
    "vegan": "vegana",
    "vegetarian": "vegetariana",
    "neither": "né vegana né vegetariana",
}


def summarize(imported: ImportedRecipe) -> str:
    """Short human-readable outcome, used by the CLI and the bot."""
    recipe = imported.recipe
    lines = [recipe.title]
    if recipe.author_handle:
        lines.append(f"di @{recipe.author_handle}")
    tags = [recipe.tags.cuisine, recipe.tags.course, DIET_LABELS[recipe.tags.diet]]
    lines.append(" · ".join(t for t in tags if t))
    lines.append(f"{len(recipe.ingredients)} ingredienti, {len(recipe.steps)} passaggi")
    if recipe.completeness.status == "complete":
        lines.append("completa")
    else:
        lines.append("parziale, manca: " + "; ".join(recipe.completeness.missing))
    lines.append(f"fonte: {imported.content_source}")
    return "\n".join(lines)


def one_line(saved: SavedRecipe, pad: bool = True) -> str:
    """One recipe per line; `pad` aligns titles in a terminal (not in Telegram)."""
    recipe = saved.recipe
    tags = [recipe.tags.cuisine, recipe.tags.course, DIET_LABELS[recipe.tags.diet]]
    if recipe.completeness.status == "partial":
        tags.append("parziale")
    number = f"#{saved.id:<4}" if pad else f"#{saved.id}"
    return f"{number} {recipe.title}  ({', '.join(t for t in tags if t)})"


def full_text(saved: SavedRecipe) -> str:
    recipe = saved.recipe
    lines = [f"#{saved.id} {recipe.title}"]
    if recipe.author_handle:
        lines.append(f"di @{recipe.author_handle}")
    if recipe.source_url:
        lines.append(recipe.source_url)
    facts = []
    if recipe.servings:
        facts.append(f"{recipe.servings} porzioni")
    if recipe.time_minutes:
        facts.append(f"{recipe.time_minutes} minuti")
    tags = [recipe.tags.cuisine, recipe.tags.course, DIET_LABELS[recipe.tags.diet]]
    lines.append(" · ".join([*facts, *(t for t in tags if t)]))

    lines += ["", "Ingredienti:"]
    for item in recipe.ingredients:
        amount = (
            " ".join(part for part in (_number(item.quantity), item.unit) if part)
            or "quantità non indicata"
        )
        lines.append(f"- {item.canonical_name}: {amount}  [{item.original_text}]")
    lines += ["", "Procedimento:"]
    lines += [f"{n}. {step}" for n, step in enumerate(recipe.steps, 1)] or ["(non indicato)"]
    if recipe.completeness.status == "partial":
        lines += ["", "Ricetta parziale, manca: " + "; ".join(recipe.completeness.missing)]
    lines += ["", f"fonte del testo: {saved.imported.content_source}"]
    return "\n".join(lines)


def _number(value: float | None) -> str | None:
    if value is None:
        return None
    return str(int(value)) if value == int(value) else f"{value:g}"
