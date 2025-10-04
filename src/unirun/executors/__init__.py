"""Thin wrappers around stdlib executors.

The modules under this package intentionally mirror the naming of
`concurrent.futures` components so documentation can reference the stdlib
verbatim.
"""

from . import async_bridge, process, subinterpreter, threading

__all__ = [
    "async_bridge",
    "process",
    "subinterpreter",
    "threading",
]
