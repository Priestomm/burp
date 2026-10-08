"""'Completa con l'AI': on request, a model fills what the post did not say.

The import stays faithful to the post; this runs only when the user asks, and what it adds is
kept apart as an `Enrichment` (see models.py) so the page can mark it as an estimate and the
user can take it back. The model only fills gaps: quantities that are still missing, servings
and time when unknown, and a clearer version of the steps.
"""

from datetime import UTC, datetime
from typing import Protocol

import anthropic
from pydantic import BaseModel, ConfigDict, Field

from burp.models import Enrichment, Estimate, ImportedRecipe
from burp.view import ingredient_views


class QuantityGuess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(description="Il numero dell'ingrediente nell'elenco")
    quantity: float = Field(gt=0)
    unit: str | None = Field(description="g, ml, cucchiaio, cucchiaino, spicchio, null = pezzi")
    reason: str = Field(description="Perché questa dose, max 60 caratteri")


class Fill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantities: list[QuantityGuess] = Field(description="Solo per gli ingredienti segnati ?")
    servings: int | None = Field(description="Per quante persone, se la ricetta non lo dice")
    time_minutes: int | None = Field(description="Tempo totale, se la ricetta non lo dice")
    steps: list[str] = Field(description="Il procedimento riscritto")
    steps_note: str | None = Field(
        description="Cosa hai aggiunto rispetto ai passaggi originali; null se niente"
    )


SYSTEM = """\
Sei un cuoco che completa le ricette salvate da un reel di cucina, per una persona che cucina \
a casa. La ricetta che ricevi è stata trascritta fedelmente dal reel; tu riempi i buchi.

- Quantità: stima solo quelle degli ingredienti segnati con "?", per le porzioni della \
ricetta (o per quelle che stimi tu se la ricetta non le dice). Dosi da cucina di casa, \
coerenti con le altre quantità della ricetta. Unità: g, ml, cucchiaio, cucchiaino, spicchio, \
oppure null per i pezzi (1 cipolla). Motivo in pochissime parole, es. "guarnizione per 3".
- servings e time_minutes: stimali solo se la ricetta li segna come non noti, altrimenti null.
- steps: riscrivi il procedimento in italiano, alla seconda persona ("taglia", "cuoci"), un \
gesto per passaggio, chiaro e completo. Tieni tutto quello che dice l'originale. Non scrivere \
le quantità nei passaggi (sono già negli ingredienti e cambiano con le porzioni). Non \
aggiungere ingredienti che non sono nell'elenco. Puoi aggiungere passaggi ovvi che mancano \
(scolare la pasta, preriscaldare il forno): in quel caso dillo in steps_note. Se il \
procedimento manca del tutto, ricostruiscilo dagli ingredienti e dal titolo e dillo in \
steps_note."""


class Filler(Protocol):
    def fill(self, imported: ImportedRecipe) -> Enrichment: ...


def describe(imported: ImportedRecipe) -> str:
    """The recipe as the model sees it: numbered ingredients, '?' where the amount is unknown."""
    recipe = imported.recipe
    lines = [f"Titolo: {recipe.title}"]
    lines.append(f"Porzioni: {recipe.servings or 'non note'}")
    lines.append(f"Tempo: {f'{recipe.time_minutes} minuti' if recipe.time_minutes else 'non noto'}")
    lines.append("Ingredienti:")
    for view in ingredient_views(imported):
        if view.status == "missing":
            amount = "?"
        elif view.status in ("to_taste", "by_eye"):
            amount = "q.b."
        else:
            amount = " ".join(x for x in (_number(view.quantity), view.unit) if x)
        lines.append(f"{view.index}. {view.name}: {amount} ({view.original_text})")
    lines.append("Procedimento originale:")
    lines += [f"- {step}" for step in recipe.steps] or ["(non c'è)"]
    return "\n".join(lines)


def _number(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if value == int(value) else f"{value:g}"


class ClaudeFiller:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client = client
        self.model = model

    def fill(self, imported: ImportedRecipe) -> Enrichment:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": describe(imported)}],
            output_format=Fill,
        )
        if response.parsed_output is None:
            raise RuntimeError(f"il modello non ha completato la ricetta ({response.stop_reason})")
        return to_enrichment(imported, response.parsed_output, self.model)


def to_enrichment(imported: ImportedRecipe, fill: Fill, model: str) -> Enrichment:
    """Keep only what fills a real gap: the model may not overwrite what the post says."""
    missing = {v.index for v in ingredient_views(imported) if v.status == "missing"}
    recipe = imported.recipe
    return Enrichment(
        model=model,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        quantities={
            guess.index: Estimate(
                quantity=guess.quantity, unit=guess.unit, reason=guess.reason[:80]
            )
            for guess in fill.quantities
            if guess.index in missing
        },
        servings=fill.servings if recipe.servings is None else None,
        time_minutes=fill.time_minutes if recipe.time_minutes is None else None,
        steps=[step.strip() for step in fill.steps if step.strip()],
        steps_note=fill.steps_note or None,
    )
