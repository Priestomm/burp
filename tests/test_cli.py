import json
from pathlib import Path

from burp.structure import ExtractedRecipe
from import_recipe import main
from tests.test_structure import FakeClient, valid_recipe

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"


def test_caption_file_is_imported_and_saved(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    client = FakeClient(valid_recipe())
    code = main(
        [
            "--caption-file",
            str(CAPTIONS / "completa.txt"),
            "--url",
            "https://www.instagram.com/p/abc/",
        ],
        client=client,
        output_dir=tmp_path,
    )
    assert code == 0
    saved = json.loads((tmp_path / "in-dal-tadka.json").read_text())
    assert saved["status"] == "ready"
    assert saved["draft"]["country_code"] == "356"
    assert saved["draft"]["source"] == "https://www.instagram.com/p/abc/"
    assert saved["provenance"]["source"] == "caption"
    assert "ready" in capsys.readouterr().out
    # the caption reached the model
    assert "guanciale" in client.calls[0]["messages"][0]["content"]


def test_dry_run_saves_nothing(tmp_path, capsys):
    code = main(
        ["--caption", (CAPTIONS / "completa.txt").read_text(), "--dry-run"],
        client=FakeClient(valid_recipe()),
        output_dir=tmp_path,
    )
    assert code == 0
    assert list(tmp_path.iterdir()) == []
    assert "dry run" in capsys.readouterr().out


def test_low_confidence_recipe_is_saved_as_needs_review(tmp_path, capsys):
    fusion = ExtractedRecipe.model_validate(
        valid_recipe().model_dump()
        | {
            "title": "Bibimbap tacos",
            "origin": {
                "country_iso2": "KR",
                "cuisine": "Korean-Mexican fusion",
                "confidence": 0.35,
                "reasoning": "Two cuisines mixed.",
            },
        }
    )
    code = main(
        ["--caption-file", str(CAPTIONS / "quantita_mancanti.txt")],
        client=FakeClient(fusion),
        output_dir=tmp_path,
    )
    assert code == 0
    saved = json.loads((tmp_path / "kr-bibimbap-tacos.json").read_text())
    assert saved["status"] == "needs_review"
    assert "needs_review" in capsys.readouterr().out


def test_empty_caption_without_fallback_asks_for_manual_input(tmp_path, capsys):
    code = main(
        ["--caption-file", str(CAPTIONS / "vuota.txt")],
        client=FakeClient(),
        output_dir=tmp_path,
    )
    assert code == 1
    assert "Paste the full caption" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_missing_api_key_is_reported(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("import_recipe.load_env", lambda: None)
    assert main(["--caption", "x"], output_dir=tmp_path) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
