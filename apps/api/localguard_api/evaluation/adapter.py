"""Load the application's evaluation adapter without coupling the scorer to agent internals."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import cast

from .contracts import EvaluationSystem, EvaluationSystemFactory


class EvaluationAdapterUnavailable(RuntimeError):
    """The real application evaluation boundary is absent or invalid."""


def build_application_system(*, provider: str, repository_root: Path) -> EvaluationSystem:
    try:
        module = import_module("localguard_api.agent.evaluation_adapter")
    except ImportError as exc:
        raise EvaluationAdapterUnavailable(
            "the application evaluation adapter is not installed"
        ) from exc
    candidate = getattr(module, "build_evaluation_system", None)
    if not callable(candidate):
        raise EvaluationAdapterUnavailable(
            "the application evaluation adapter has no callable factory"
        )
    factory = cast(EvaluationSystemFactory, candidate)
    return factory(provider=provider, repository_root=repository_root)
