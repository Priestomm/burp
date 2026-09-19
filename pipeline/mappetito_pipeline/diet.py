"""Computes the `diet` of a recipe from the flags of its ingredients."""

from collections.abc import Mapping

from mappetito_pipeline.models import Diet, Ingredient, Recipe, RecipeBase, RecipeDraft


class DietError(ValueError):
    """Base class for recipe validation errors raised while computing the diet."""


class UnknownIngredientError(DietError):
    pass


class NonVegetarianIngredientError(DietError):
    pass


def compute_diet(recipe: RecipeBase, ingredients: Mapping[str, Ingredient]) -> Diet:
    """Return "vegan" or "vegetarian"; raise if any ingredient is not even vegetarian."""
    resolved: list[Ingredient] = []
    for item in recipe.ingredients:
        ingredient = ingredients.get(item.ingredient_id)
        if ingredient is None:
            raise UnknownIngredientError(f"{recipe.id}: unknown ingredient '{item.ingredient_id}'")
        resolved.append(ingredient)

    non_vegetarian = [i.id for i in resolved if not i.is_vegetarian]
    if non_vegetarian:
        raise NonVegetarianIngredientError(
            f"{recipe.id}: contains non-vegetarian ingredient(s): {', '.join(non_vegetarian)}"
        )
    return "vegan" if all(i.is_vegan for i in resolved) else "vegetarian"


def to_recipe(draft: RecipeDraft, ingredients: Mapping[str, Ingredient]) -> Recipe:
    return Recipe(**draft.model_dump(), diet=compute_diet(draft, ingredients))
