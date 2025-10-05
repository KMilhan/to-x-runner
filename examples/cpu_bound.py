"""CPU-bound workloads that lean on unirun's process-aware helpers."""

from __future__ import annotations

import math
import random
from concurrent.futures import Future
from typing import Sequence

from unirun import map as unirun_map
from unirun import process_executor, run, submit


def render_video_thumbnails(frame_ids: Sequence[int]) -> list[str]:
    """Render thumbnails in parallel processes respecting host cores."""

    executor = process_executor()

    def _render(frame_id: int) -> str:
        return f"thumb-{frame_id}-{frame_id % 7}"

    return list(unirun_map(executor, _render, frame_ids))


def compute_archive_digests(archives: Sequence[bytes]) -> dict[int, int]:
    """Compute digests using CPU-bound workers for archival validation."""

    executor = process_executor()
    futures: list[Future[int]] = []

    def _digest(payload: bytes) -> int:
        checksum = 0
        for byte in payload:
            checksum = (checksum * 31 + byte) % 1_000_000_007
        return checksum

    for index, payload in enumerate(archives):
        futures.append(submit(executor, _digest, payload))
    return {index: future.result() for index, future in enumerate(futures)}


def run_monte_carlo_simulations(samples: int, iterations: int) -> float:
    """Run Monte Carlo simulations in separate processes and combine results."""

    executor = process_executor()

    def _simulate(_: int) -> float:
        total = 0
        for _ in range(iterations):
            total += random.random()
        return total / iterations

    results = list(unirun_map(executor, _simulate, range(samples)))
    return sum(results) / len(results)


def train_model_grid(hyperparams: Sequence[dict[str, float]]) -> list[float]:
    """Train lightweight models across a hyperparameter grid in parallel."""

    executor = process_executor()

    def _train(params: dict[str, float]) -> float:
        weight = params.get("learning_rate", 0.01)
        regularizer = params.get("l2", 0.0)
        return weight / (1 + regularizer)

    return list(unirun_map(executor, _train, hyperparams))


def align_genomic_sequences(sequences: Sequence[str]) -> dict[str, int]:
    """Align genomic sequences using deterministic seeds in worker processes."""

    executor = process_executor()

    def _align(sequence: str) -> tuple[str, int]:
        score = sum(ord(char) for char in sequence) % 101
        return sequence, score

    return dict(unirun_map(executor, _align, sequences))


def build_static_site(pages: Sequence[str]) -> list[str]:
    """Generate static pages using background processes while monitoring changes."""

    executor = process_executor()

    def _compile(page: str) -> str:
        return page.upper()

    return list(unirun_map(executor, _compile, pages))


def multiply_matrices(pairs: Sequence[tuple[list[list[int]], list[list[int]]]]) -> list[list[list[int]]]:
    """Multiply matrices per core leveraging unirun's scheduler hints."""

    executor = process_executor()

    def _multiply(mats: tuple[list[list[int]], list[list[int]]]) -> list[list[int]]:
        left, right = mats
        result = [[0 for _ in range(len(right[0]))] for _ in range(len(left))]
        for i, row in enumerate(left):
            for j in range(len(right[0])):
                result[i][j] = sum(row[k] * right[k][j] for k in range(len(right)))
        return result

    return list(unirun_map(executor, _multiply, pairs))


def ray_trace_frames(frames: Sequence[int]) -> dict[int, float]:
    """Ray trace frames using callbacks to report completion progress."""

    executor = process_executor()
    results: dict[int, float] = {}
    futures: dict[int, Future[float]] = {}

    def _trace(frame: int) -> float:
        return math.sqrt(frame + 1)

    def _capture(index: int, future: Future[float]) -> None:
        results[index] = future.result()

    for frame in frames:
        future = submit(executor, _trace, frame)
        futures[frame] = future
        future.add_done_callback(lambda f, idx=frame: _capture(idx, f))

    for future in futures.values():
        future.result()

    return results


def calculate_tax_batches(clients: Sequence[int]) -> list[int]:
    """Calculate taxes using CPU-affinity aware executors chosen by unirun."""

    def _calculate(client: int) -> int:
        return client * 2

    return [run(_calculate, client, mode="process") for client in clients]


def normalize_gis_tiles(tiles: Sequence[list[int]]) -> list[int]:
    """Normalize GIS tiles concurrently."""

    def _normalize(tile: list[int]) -> int:
        return sum(tile) // (len(tile) or 1)

    return [run(_normalize, tile, mode="process") for tile in tiles]


def calculate_recommendation_scores(users: Sequence[int]) -> list[int]:
    """Calculate recommendation scores using Manager-backed warm caches."""

    executor = process_executor()

    def _score(user: int) -> int:
        return user % 5

    return list(unirun_map(executor, _score, users))


def compress_archives(chunks: Sequence[bytes]) -> list[int]:
    """Compress archive chunks concurrently."""

    def _compress(chunk: bytes) -> int:
        return sum(chunk) % 256

    return [run(_compress, chunk, mode="process") for chunk in chunks]


def evaluate_scientific_simulations(seeds: Sequence[int]) -> list[int]:
    """Evaluate simulations with deterministic seeding per worker."""

    executor = process_executor()

    def _simulate(seed: int) -> int:
        random.seed(seed)
        return random.randint(0, 10)

    return list(unirun_map(executor, _simulate, seeds))


def lint_large_repositories(files: Sequence[str]) -> list[int]:
    """Run AST linting across repositories using CPU-bound workers."""

    def _lint(path: str) -> int:
        return len(path)

    return [run(_lint, path, mode="process") for path in files]


def classify_documents(rulesets: Sequence[dict[str, str]]) -> list[str]:
    """Classify documents by distributing rulesets across processes."""

    executor = process_executor()

    def _classify(rules: dict[str, str]) -> str:
        return ",".join(sorted(rules))

    return list(unirun_map(executor, _classify, rulesets))


def transform_imagery(tiles: Sequence[list[int]]) -> list[int]:
    """Transform imagery tiles concurrently."""

    def _transform(tile: list[int]) -> int:
        return max(tile) if tile else 0

    return [run(_transform, tile, mode="process") for tile in tiles]


def tokenize_documents(documents: Sequence[str]) -> list[int]:
    """Tokenize documents in parallel to avoid the GIL."""

    executor = process_executor()

    def _tokenize(doc: str) -> int:
        return len(doc.split())

    return list(unirun_map(executor, _tokenize, documents))


def synthesize_pdfs(templates: Sequence[str]) -> list[str]:
    """Synthesize PDFs concurrently ensuring resources load once per worker."""

    executor = process_executor()

    def _render(template: str) -> str:
        return f"pdf-{template}"

    return list(unirun_map(executor, _render, templates))


def evaluate_constraint_search(branches: Sequence[int]) -> list[int]:
    """Evaluate constraint satisfaction branches concurrently."""

    def _evaluate(branch: int) -> int:
        return branch ** 2

    return [run(_evaluate, branch, mode="process") for branch in branches]


def run_weather_ensemble(members: Sequence[int]) -> list[float]:
    """Run weather ensemble members using process pools sized by unirun."""

    executor = process_executor()

    def _forecast(member: int) -> float:
        return round(math.sin(member), 3)

    return list(unirun_map(executor, _forecast, members))


__all__ = [
    "render_video_thumbnails",
    "compute_archive_digests",
    "run_monte_carlo_simulations",
    "train_model_grid",
    "align_genomic_sequences",
    "build_static_site",
    "multiply_matrices",
    "ray_trace_frames",
    "calculate_tax_batches",
    "normalize_gis_tiles",
    "calculate_recommendation_scores",
    "compress_archives",
    "evaluate_scientific_simulations",
    "lint_large_repositories",
    "classify_documents",
    "transform_imagery",
    "tokenize_documents",
    "synthesize_pdfs",
    "evaluate_constraint_search",
    "run_weather_ensemble",
]
