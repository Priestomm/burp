"""What the app shows for a recipe: the model's answer, the user's edits on top, and the
state of each quantity. Computed on read, never stored, so it always follows the rules here."""

from typing import Literal

from pydantic import BaseModel

from burp.models import ImportedRecipe, RecipeIngredient
from burp.structure import TO_TASTE
from burp.units import BaseUnit, to_base

QuantityStatus = Literal["given", "to_taste", "missing", "by_eye"]


class IngredientView(BaseModel):
    index: int
    name: str
    original_text: str
    quantity: float | None
    unit: str | None
    status: QuantityStatus
    base_unit: BaseUnit | None  # set only when the amount can be scaled
    base_quantity: float | None
    edited: bool  # the quantity comes from the user, not from the post


def ingredient_views(imported: ImportedRecipe) -> list[IngredientView]:
    return [_view(index, item, imported) for index, item in enumerate(imported.recipe.ingredients)]


def _view(index: int, item: RecipeIngredient, imported: ImportedRecipe) -> IngredientView:
    edit = imported.edits.get(index)
    edited = edit is not None and edit.quantity is not None
    quantity = edit.quantity if edited else item.quantity
    unit = edit.unit if edited else item.unit
    if quantity is not None:
        status: QuantityStatus = "given"
    elif unit == "q.b." or TO_TASTE.search(item.original_text):
        status = "to_taste"
    elif edit is not None and edit.by_eye:
        status = "by_eye"
    else:
        status = "missing"
    base = to_base(quantity, unit)
    return IngredientView(
        index=index,
        name=item.canonical_name,
        original_text=item.original_text,
        quantity=quantity,
        unit=unit,
        status=status,
        base_unit=base[0] if base else None,
        base_quantity=base[1] if base else None,
        edited=edited,
    )


def missing_names(imported: ImportedRecipe) -> list[str]:
    """Ingredients whose quantity is still unknown (not given, not q.b., not "a occhio")."""
    return [view.name for view in ingredient_views(imported) if view.status == "missing"]
