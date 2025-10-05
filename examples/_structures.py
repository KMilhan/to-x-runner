"""Shared data structures for runnable example scenarios."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T_co = TypeVar("T_co", covariant=True)


@dataclass(frozen=True)
class ExampleResult(Generic[T_co]):  # noqa: UP046
    """Holds the outcome of a single example invocation.

    Attributes:
        name: Human-readable title for the example result.
        output: Concrete payload returned by the example runner.
        tags: Lightweight labels used by reporters and filters.
    """

    name: str
    output: T_co
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExampleScenario(Generic[T_co]):  # noqa: UP046
    """Describes a runnable example, including the callable and its context.

    Attributes:
        name: Title rendered in human-facing reports and README tables.
        summary: One-line explanation of the real-world workflow represented.
        details: Multi-line paragraph outlining assumptions and data flow.
        entrypoint: Callable that performs the concurrency workflow.
        args: Positional arguments to pass to ``entrypoint``.
        kwargs: Keyword arguments passed to ``entrypoint``.
        tags: Topic labels such as ``("cpu", "process")``.
    """

    name: str
    summary: str
    details: str
    entrypoint: Callable[..., T_co]
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    def execute(self) -> ExampleResult[T_co]:
        """Invoke the example callable and package the output.

        Returns:
            ExampleResult: Wrapper pairing the scenario metadata with output.
        """

        result = self.entrypoint(*self.args, **self.kwargs)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        return ExampleResult(name=self.name, output=result, tags=self.tags)


def format_result(result: ExampleResult[Any]) -> str:
    """Serialize a result into a human-readable string for CLI demos.

    Args:
        result: Scenario output paired with metadata.

    Returns:
        str: Pretty-printed payload description.
    """

    tag_suffix = f" [{' '.join(result.tags)}]" if result.tags else ""
    return f"{result.name}{tag_suffix}: {result.output}"
