"""Finding decks, from inside one or from the root of a repository holding several."""

import pytest
import yaml

from _lib.config import ConfigError, find_deck, find_decks, resolve_deck


def make_deck(root, name, anki_name=None):
    directory = root / name
    (directory / "cards").mkdir(parents=True)
    (directory / "deck.yaml").write_text(
        yaml.safe_dump({"name": anki_name or name.title(), "tag_root": name.replace("-", "")})
    )
    return directory


def test_find_decks_at_a_repository_root(tmp_path):
    make_deck(tmp_path, "agentic-ai")
    make_deck(tmp_path, "quebec-french")
    assert [d.root.name for d in find_decks(tmp_path)] == ["agentic-ai", "quebec-french"]


def test_find_decks_inside_a_deck_returns_that_deck(tmp_path):
    directory = make_deck(tmp_path, "agentic-ai")
    assert [d.root.name for d in find_decks(directory)] == ["agentic-ai"]


def test_resolve_deck_by_name_from_the_root(tmp_path):
    make_deck(tmp_path, "agentic-ai")
    make_deck(tmp_path, "quebec-french")
    assert resolve_deck("quebec-french", tmp_path).config.name == "Quebec-French"


def test_resolve_deck_by_path(tmp_path):
    directory = make_deck(tmp_path, "agentic-ai")
    assert resolve_deck(str(directory), tmp_path).root.name == "agentic-ai"


def test_resolve_deck_names_the_decks_it_did_find(tmp_path):
    make_deck(tmp_path, "agentic-ai")
    with pytest.raises(ConfigError, match="agentic-ai"):
        resolve_deck("nope", tmp_path)


def test_standing_at_a_root_with_no_deck_lists_them(tmp_path):
    make_deck(tmp_path, "agentic-ai")
    make_deck(tmp_path, "quebec-french")
    with pytest.raises(ConfigError, match="agentic-ai, quebec-french"):
        find_deck(tmp_path)


def test_prose_fields_are_optional_and_inherited(tmp_path):
    (tmp_path / "ancci.yaml").write_text(
        yaml.safe_dump({"avoid": "prices and model numbers", "limits": {"back_chars": 400}})
    )
    directory = make_deck(tmp_path, "coffee")
    (directory / "deck.yaml").write_text(
        yaml.safe_dump({"name": "Coffee", "tag_root": "coffee", "audience": "makes coffee daily"})
    )
    config = resolve_deck("coffee", tmp_path).config
    assert config.audience == "makes coffee daily"   # the deck's own
    assert config.avoid == "prices and model numbers"  # inherited from the root
    assert config.scope is None  # nobody set one, and that is allowed
    assert config.limits.back_chars == 400


def test_a_deck_found_by_walking_up(tmp_path):
    directory = make_deck(tmp_path, "agentic-ai")
    deep = directory / "cards"
    assert find_deck(deep).root.name == "agentic-ai"
