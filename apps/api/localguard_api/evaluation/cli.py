"""Command-line entrypoint for real, reproducible LocalGuard evaluations."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import Annotated, Literal

import typer

from .adapter import EvaluationAdapterUnavailable, build_application_system
from .dataset import DatasetValidationError, load_dataset, repository_root
from .reporting import write_run_artifacts
from .runner import run_evaluation


class ProviderOption(StrEnum):
    FAKE = "fake"
    OLLAMA = "ollama"


app = typer.Typer(
    add_completion=False,
    help="Run LocalGuard's exact, hash-verified 25-case evaluation suite.",
)


@app.callback()
def evaluation_cli() -> None:
    """Expose explicit subcommands so PowerShell and CI share the same invocation."""


@app.command("run")
def run_command(
    provider: Annotated[
        ProviderOption,
        typer.Option(
            "--provider",
            help="Use the deterministic CI adapter or the pinned local Ollama model.",
        ),
    ] = ProviderOption.FAKE,
) -> None:
    """Run all cases sequentially, then write raw JSON and a generated report."""

    root = repository_root()
    runtime_provider: Literal["deterministic", "ollama"] = (
        "deterministic" if provider is ProviderOption.FAKE else "ollama"
    )
    try:
        dataset = load_dataset(root, verify=True)
        system = build_application_system(
            provider=runtime_provider,
            repository_root=root,
        )
        evaluation = asyncio.run(
            run_evaluation(
                dataset,
                system,
                requested_provider=provider.value,
                runtime_provider=runtime_provider,
            )
        )
        artifacts = write_run_artifacts(evaluation, root / "evals" / "results")
    except DatasetValidationError as exc:
        typer.echo(f"Dataset validation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except EvaluationAdapterUnavailable as exc:
        typer.echo(f"Application evaluation adapter unavailable: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        typer.echo(f"Evaluation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Evaluation run: {evaluation.run_id}")
    typer.echo(
        f"Cases: {evaluation.aggregate.completed_case_count}/{evaluation.aggregate.case_count}"
    )
    typer.echo(f"Raw results: {artifacts.raw_json}")
    typer.echo(f"Report: {artifacts.markdown}")
    typer.echo(f"Safety gates: {'PASS' if evaluation.gates.safety_passed else 'FAIL'}")
    if evaluation.gates.quality_passed is not None:
        typer.echo(f"Quality gates: {'PASS' if evaluation.gates.quality_passed else 'FAIL'}")
    if not evaluation.gates.run_passed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
