import json
from pathlib import Path

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
    saved = json.loads((tmp_path / "dal-tadka.json").read_text())
    assert saved["recipe"]["source_url"] == "https://www.instagram.com/p/abc/"
    assert saved["content_source"] == "caption"
    assert "completa" in capsys.readouterr().out
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


def test_partial_recipe_is_saved_and_reported(tmp_path, capsys):
    partial = valid_recipe(
        title="Pasta zucchine e menta",
        ingredients=[{"canonical_name": "pasta", "original_text": "pasta corta"}],
    )
    code = main(
        ["--caption-file", str(CAPTIONS / "quantita_mancanti.txt")],
        client=FakeClient(partial),
        output_dir=tmp_path,
    )
    assert code == 0
    saved = json.loads((tmp_path / "pasta-zucchine-e-menta.json").read_text())
    assert saved["recipe"]["completeness"]["status"] == "partial"
    assert "parziale, manca: quantità di pasta" in capsys.readouterr().out


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
