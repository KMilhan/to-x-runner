from __future__ import annotations

import doctest

import unirun.api


def test_unirun_api_doctests() -> None:
    failure_count, _ = doctest.testmod(
        unirun.api,
        optionflags=doctest.NORMALIZE_WHITESPACE,
    )
    assert failure_count == 0
