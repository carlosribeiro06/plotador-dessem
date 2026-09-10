"""Tests for dessem_dashboard.data.discovery."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.errors import DiscoveryError


def _add_deck(scenario_dir: Path, deck_name: str, *, dirname: str = "sintese") -> Path:
    """Create scenario_dir/deck_name/dirname as a directory and return the deck directory."""
    deck_dir = scenario_dir / deck_name
    (deck_dir / dirname).mkdir(parents=True)
    return deck_dir


def test_discover_scenarios_scenario_tree_fixture_returns_ordered_scenarios_with_decks(
    scenario_tree: dict[str, Path],
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])

    assert [scenario.label for scenario in scenarios] == ["caso_a", "caso_b"]
    for scenario in scenarios:
        assert len(scenario.decks) == 2
        assert [deck.name for deck in scenario.decks] == ["deck_dois", "deck_um"]
        for deck in scenario.decks:
            assert deck.sintese_dir.name == "sintese"
            assert deck.sintese_dir.is_dir()


def test_discover_scenarios_sorts_decks_by_name_regardless_of_creation_order(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "cenario_ordem"
    _add_deck(scenario_dir, "zulu")
    _add_deck(scenario_dir, "alfa")

    (scenario,) = discover_scenarios([scenario_dir])

    assert [deck.name for deck in scenario.decks] == ["alfa", "zulu"]


def test_discover_scenarios_nonexistent_path_raises_naming_path(tmp_path: Path) -> None:
    missing = tmp_path / "inexistente"

    with pytest.raises(DiscoveryError, match=re.escape("inexistente")):
        discover_scenarios([missing])


def test_discover_scenarios_file_instead_of_directory_raises_naming_path(tmp_path: Path) -> None:
    file_path = tmp_path / "arquivo_cenario.txt"
    file_path.write_text("não é um diretório", encoding="utf-8")

    with pytest.raises(DiscoveryError, match=re.escape("arquivo_cenario.txt")):
        discover_scenarios([file_path])


def test_discover_scenarios_zero_deck_scenario_raises_naming_label_and_sintese_dirname(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "vazio"
    (scenario_dir / "sub").mkdir(parents=True)

    with pytest.raises(DiscoveryError) as exc_info:
        discover_scenarios([scenario_dir])

    message = str(exc_info.value)
    assert "vazio" in message
    assert "sintese" in message


def test_discover_scenarios_scenario_dir_directly_containing_sintese_raises_zero_deck_error(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "plano_flat"
    (scenario_dir / "sintese").mkdir(parents=True)

    with pytest.raises(DiscoveryError) as exc_info:
        discover_scenarios([scenario_dir])

    message = str(exc_info.value)
    assert "plano_flat" in message
    assert "sintese" in message


def test_discover_scenarios_duplicate_basenames_raise_naming_label(tmp_path: Path) -> None:
    scenario_a = tmp_path / "a" / "caso_x"
    scenario_b = tmp_path / "b" / "caso_x"
    _add_deck(scenario_a, "deck1")
    _add_deck(scenario_b, "deck1")

    with pytest.raises(DiscoveryError, match=re.escape("caso_x")):
        discover_scenarios([scenario_a, scenario_b])


def test_discover_scenarios_empty_paths_raises() -> None:
    with pytest.raises(DiscoveryError):
        discover_scenarios([])


def test_discover_scenarios_custom_sintese_dirname_is_honoured(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "cenario_custom"
    _add_deck(scenario_dir, "deck1", dirname="resultados")

    (scenario,) = discover_scenarios([scenario_dir], sintese_dirname="resultados")

    assert len(scenario.decks) == 1
    assert scenario.decks[0].sintese_dir.name == "resultados"


def test_discover_scenarios_deck_subdir_with_sintese_file_is_not_a_deck(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "cenario_misto"
    _add_deck(scenario_dir, "deck_valido")
    deck_arquivo = scenario_dir / "deck_arquivo"
    deck_arquivo.mkdir(parents=True)
    (deck_arquivo / "sintese").write_text("não é um diretório", encoding="utf-8")

    (scenario,) = discover_scenarios([scenario_dir])

    assert [deck.name for deck in scenario.decks] == ["deck_valido"]


def test_discover_scenarios_logs_per_scenario_info_line(
    scenario_tree: dict[str, Path], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])

    per_scenario = [
        record.getMessage() for record in caplog.records if "cenario=caso_a" in record.getMessage()
    ]
    assert per_scenario
    assert "decks=2" in per_scenario[0]


def test_discover_scenarios_logs_summary_info_line(
    scenario_tree: dict[str, Path], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])

    summary = [
        record.getMessage() for record in caplog.records if "cenarios=2" in record.getMessage()
    ]
    assert summary
    assert "decks=4" in summary[0]
