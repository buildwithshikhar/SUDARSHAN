"""The production API image must carry the sim core and the packs it reads (Q-19)."""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import cli
from app.contracts.paths import packs_root
from app.simcheck import run_sim_check

REPO = Path(__file__).resolve().parents[3]
DOCKERFILE = (REPO / "infra" / "Dockerfile.api").read_text(encoding="utf-8")
PROD_CHECK = (REPO / "infra" / "prod-check.sh").read_text(encoding="utf-8")


def copied_sources() -> set[str]:
    return {
        m.group(1) for m in re.finditer(r"^COPY\s+(?:--\S+\s+)*(\S+)\s+\S+\s*$", DOCKERFILE, re.M)
    }


@pytest.mark.parametrize("source", ["services/api/app", "services/api/sim", "packs"])
def test_the_api_image_copies_the_source_it_runs(source: str) -> None:
    assert source in copied_sources()


def test_the_dockerfile_does_not_copy_sim_by_a_path_that_does_not_exist() -> None:
    for source in copied_sources():
        if source.startswith(("services/", "packs", "brand")):
            assert (REPO / source).exists(), source


def test_prod_check_runs_the_sim_check_inside_the_api_container() -> None:
    assert "exec -T api python -m app.cli sim-check" in PROD_CHECK


def test_the_sim_check_runs_a_scenario_with_a_picture() -> None:
    assert run_sim_check(20).startswith("sim ok: ")


def test_the_cli_command_reports_success() -> None:
    result = CliRunner().invoke(cli, ["sim-check"])
    assert result.exit_code == 0
    assert "sim ok" in result.output


def test_the_cli_command_fails_when_the_packs_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PACKS_DIR", str(tmp_path))
    result = CliRunner().invoke(cli, ["sim-check"])
    assert result.exit_code == 4


def test_packs_dir_overrides_the_search(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACKS_DIR", str(tmp_path))
    assert packs_root() == tmp_path
    monkeypatch.delenv("PACKS_DIR")
    assert packs_root() == REPO / "packs"
