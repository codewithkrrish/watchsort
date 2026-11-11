"""Tests for rules loading and category lookup."""

from pathlib import Path

import pytest

from watchsort.rules import Rules, is_skippable, load_rules
from watchsort.errors import RulesError


def test_default_categories_cover_common_types():
    rules = Rules()
    assert rules.category_for("photo.JPG") == "Images"  # case-insensitive
    assert rules.category_for("report.pdf") == "Documents"
    assert rules.category_for("song.mp3") == "Audio"
    assert rules.category_for("clip.mp4") == "Videos"
    assert rules.category_for("data.zip") == "Archives"
    assert rules.category_for("app.py") == "Code"
    assert rules.category_for("sheet.xlsx") == "Spreadsheets"
    assert rules.category_for("deck.pptx") == "Presentations"
    assert rules.category_for("setup.dmg") == "Installers"


def test_unknown_extension_goes_to_other():
    assert Rules().category_for("weird.xyz") == "Other"
    assert Rules().category_for("noextension") == "Other"


def test_custom_toml_rules(tmp_path: Path):
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text(
        '[settings]\ndate_folders = false\n\n[Photos]\nextensions = [".png", ".jpg"]\n',
        encoding="utf-8",
    )
    rules = load_rules(rules_file)
    assert rules.category_for("a.png") == "Photos"
    assert rules.category_for("b.pdf") == "Other"
    assert rules.date_folders is False


def test_load_rules_none_gives_defaults():
    rules = load_rules(None)
    assert rules.category_for("x.png") == "Images"
    assert rules.date_folders is True


def test_missing_rules_file_is_an_error(tmp_path: Path):
    with pytest.raises(RulesError, match="can't read"):
        load_rules(tmp_path / "nope.toml")


def test_corrupt_toml_is_an_error(tmp_path: Path):
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text("[not valid toml", encoding="utf-8")
    with pytest.raises(RulesError, match="not valid TOML"):
        load_rules(rules_file)


def test_category_without_extensions_is_an_error(tmp_path: Path):
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text("[Images]\nfoo = 1\n", encoding="utf-8")
    with pytest.raises(RulesError, match="extensions"):
        load_rules(rules_file)


def test_extension_without_dot_is_an_error(tmp_path: Path):
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text('[Images]\nextensions = ["png"]\n', encoding="utf-8")
    with pytest.raises(RulesError, match="starting with '.'"):
        load_rules(rules_file)


def test_no_categories_is_an_error(tmp_path: Path):
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text("[settings]\ndate_folders = true\n", encoding="utf-8")
    with pytest.raises(RulesError, match="no categories"):
        load_rules(rules_file)


def test_skippable_files():
    assert is_skippable(".hidden") is True
    assert is_skippable("movie.mp4.crdownload") is True
    assert is_skippable("archive.zip.part") is True
    assert is_skippable("normal.pdf") is False


def test_rules_roundtrip_to_toml(tmp_path: Path):
    # init writes TOML that loads back to the same rules.
    rules = Rules()
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text(rules.to_toml(), encoding="utf-8")
    loaded = load_rules(rules_file)
    assert loaded.category_for("a.png") == rules.category_for("a.png")
    assert loaded.date_folders == rules.date_folders
