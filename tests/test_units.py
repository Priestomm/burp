import pytest

from burp.units import to_base


@pytest.mark.parametrize(
    ("quantity", "unit", "expected"),
    [
        (400, "g", ("g", 400)),
        (1, "kg", ("g", 1000)),
        (50, "ml", ("ml", 50)),
        (1.5, "l", ("ml", 1500)),
        (2, "dl", ("ml", 200)),
        (0.25, "tazza", ("ml", 60)),
        (3, "cucchiai", ("tsp", 9)),
        (1, "Cucchiaio", ("tsp", 3)),
        (0.5, "cucchiaino", ("tsp", 0.5)),
        (5, "spicchio", ("piece", 5)),
        (2, None, ("piece", 2)),
    ],
)
def test_scalable_units(quantity, unit, expected):
    assert to_base(quantity, unit) == expected


@pytest.mark.parametrize("unit", ["lattina da 15 oz", "mazzetto", "q.b."])
def test_units_that_cannot_be_scaled(unit):
    assert to_base(2, unit) is None


def test_no_quantity_means_nothing_to_scale():
    assert to_base(None, "g") is None
