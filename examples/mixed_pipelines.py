"""Mixed I/O and CPU pipelines showcasing unirun orchestration patterns."""

from __future__ import annotations

import asyncio
import random
from typing import Sequence

from unirun import to_process


async def convert_camera_feeds(feeds: Sequence[str]) -> dict[str, str]:
    """Convert camera feeds by reading asynchronously and encoding in processes."""

    async def _convert(feed: str) -> tuple[str, str]:
        frame = await _read_frame(feed)
        encoded = await to_process(_encode_frame, frame)
        return feed, encoded

    return dict(await asyncio.gather(*(_convert(feed) for feed in feeds)))


async def _read_frame(feed: str) -> bytes:
    await asyncio.sleep(0.01)
    return feed.encode()


def _encode_frame(frame: bytes) -> str:
    return frame.hex()


async def execute_etl_jobs(keys: Sequence[str]) -> dict[str, int]:
    """Run ETL jobs with async downloads and CPU-bound validation."""

    async def _job(key: str) -> tuple[str, int]:
        payload = await _download_object(key)
        checksum = await to_process(_validate_payload, payload)
        return key, checksum

    return dict(await asyncio.gather(*(_job(key) for key in keys)))


async def _download_object(key: str) -> bytes:
    await asyncio.sleep(0.01)
    return key.encode()


def _validate_payload(payload: bytes) -> int:
    return sum(payload)


async def provide_pdf_generation(requests: Sequence[str]) -> dict[str, str]:
    """Handle async API requests while rasterizing PDFs in subprocesses."""

    async def _handle(request: str) -> tuple[str, str]:
        await asyncio.sleep(0.005)
        pdf = await to_process(_render_pdf, request)
        return request, pdf

    return dict(await asyncio.gather(*(_handle(request) for request in requests)))


def _render_pdf(name: str) -> str:
    return f"pdf-{name}"


async def orchestrate_speech_to_text(chunks: Sequence[bytes]) -> dict[int, str]:
    """Upload audio asynchronously while transcription runs in processes."""

    async def _transcribe(index: int, chunk: bytes) -> tuple[int, str]:
        await asyncio.sleep(0.005)
        text = await to_process(_transcribe_chunk, chunk)
        return index, text

    tasks = [
        asyncio.create_task(_transcribe(index, chunk))
        for index, chunk in enumerate(chunks)
    ]
    return dict(await asyncio.gather(*tasks))


def _transcribe_chunk(chunk: bytes) -> str:
    return chunk.decode(errors="ignore")[::-1]


async def coordinate_geospatial_tiles(tiles: Sequence[str]) -> dict[str, float]:
    """Download tiles asynchronously and process reprojection concurrently."""

    async def _coordinate(tile: str) -> tuple[str, float]:
        blob = await _download_tile(tile)
        area = await to_process(_reproject_tile, blob)
        return tile, area

    return dict(await asyncio.gather(*(_coordinate(tile) for tile in tiles)))


async def _download_tile(tile: str) -> bytes:
    await asyncio.sleep(0.008)
    return tile.encode()


def _reproject_tile(blob: bytes) -> float:
    return round(len(blob) * 0.42, 2)


async def run_ci_pipeline(revisions: Sequence[str]) -> dict[str, bool]:
    """Download dependencies asynchronously and run tests in isolated interpreters."""

    async def _ci(revision: str) -> tuple[str, bool]:
        await asyncio.sleep(0.005)
        result = await to_process(_run_tests, revision)
        return revision, result

    return dict(await asyncio.gather(*(_ci(revision) for revision in revisions)))


def _run_tests(revision: str) -> bool:
    return len(revision) % 2 == 0


async def manage_iot_telemetry(devices: Sequence[str]) -> dict[str, float]:
    """Ingest telemetry via async brokers and run anomaly detection in processes."""

    async def _handle(device: str) -> tuple[str, float]:
        payload = await _pull_telemetry(device)
        score = await to_process(_detect_anomaly, payload)
        return device, score

    return dict(await asyncio.gather(*(_handle(device) for device in devices)))


async def _pull_telemetry(device: str) -> list[int]:
    await asyncio.sleep(0.004)
    return [len(device), random.randint(0, 10)]


def _detect_anomaly(metrics: list[int]) -> float:
    return sum(metrics) / (len(metrics) or 1)


async def execute_financial_settlements(batches: Sequence[str]) -> dict[str, float]:
    """Fetch ledger data asynchronously and reconcile in multiprocessing pools."""

    async def _settle(batch: str) -> tuple[str, float]:
        ledger = await _fetch_ledger(batch)
        amount = await to_process(_reconcile_ledger, ledger)
        return batch, amount

    return dict(await asyncio.gather(*(_settle(batch) for batch in batches)))


async def _fetch_ledger(batch: str) -> list[int]:
    await asyncio.sleep(0.006)
    return [ord(char) for char in batch]


def _reconcile_ledger(entries: list[int]) -> float:
    return float(sum(entries))


async def implement_cloud_backups(resources: Sequence[str]) -> dict[str, str]:
    """Upload asynchronously while computing deduplication hashes in processes."""

    async def _backup(resource: str) -> tuple[str, str]:
        data = await _stream_block(resource)
        digest = await to_process(_hash_block, data)
        return resource, digest

    return dict(await asyncio.gather(*(_backup(resource) for resource in resources)))


async def _stream_block(resource: str) -> bytes:
    await asyncio.sleep(0.004)
    return resource.encode()


def _hash_block(data: bytes) -> str:
    return hex(sum(data) % 65535)


async def drive_content_moderation(items: Sequence[str]) -> dict[str, int]:
    """Fetch items asynchronously and score them with CPU-bound inference."""

    async def _moderate(item: str) -> tuple[str, int]:
        await asyncio.sleep(0.003)
        score = await to_process(_score_item, item)
        return item, score

    return dict(await asyncio.gather(*(_moderate(item) for item in items)))


def _score_item(item: str) -> int:
    return len(item) % 7


async def deliver_recommendation_feeds(users: Sequence[str]) -> dict[str, float]:
    """Fetch personalized data asynchronously and compute scores in processes."""

    async def _deliver(user: str) -> tuple[str, float]:
        await asyncio.sleep(0.004)
        score = await to_process(_score_user, user)
        return user, score

    return dict(await asyncio.gather(*(_deliver(user) for user in users)))


def _score_user(user: str) -> float:
    return round(len(user) * 0.3, 2)


async def maintain_multiplayer_state(players: Sequence[str]) -> dict[str, dict[str, int]]:
    """Handle sockets asynchronously and offload physics calculations."""

    async def _maintain(player: str) -> tuple[str, dict[str, int]]:
        await asyncio.sleep(0.003)
        physics = await to_process(_simulate_physics, player)
        return player, physics

    return dict(await asyncio.gather(*(_maintain(player) for player in players)))


def _simulate_physics(player: str) -> dict[str, int]:
    return {"energy": len(player) ** 2}


async def support_remote_rendering(jobs: Sequence[str]) -> dict[str, str]:
    """Fetch assets asynchronously and convert them in separate processes."""

    async def _render(job: str) -> tuple[str, str]:
        manifest = await _fetch_manifest(job)
        output = await to_process(_convert_asset, manifest)
        return job, output

    return dict(await asyncio.gather(*(_render(job) for job in jobs)))


async def _fetch_manifest(job: str) -> bytes:
    await asyncio.sleep(0.005)
    return job.encode()


def _convert_asset(blob: bytes) -> str:
    return blob.decode()[::-1]


async def operate_trading_bots(strategies: Sequence[str]) -> dict[str, float]:
    """Stream market data asynchronously while evaluating strategies in processes."""

    async def _operate(strategy: str) -> tuple[str, float]:
        await asyncio.sleep(0.004)
        value = await to_process(_evaluate_strategy, strategy)
        return strategy, value

    return dict(await asyncio.gather(*(_operate(strategy) for strategy in strategies)))


def _evaluate_strategy(name: str) -> float:
    return round(len(name) * random.random(), 3)


async def run_e_discovery(cases: Sequence[str]) -> dict[str, int]:
    """Crawl documents asynchronously and run OCR in processes."""

    async def _process(case: str) -> tuple[str, int]:
        await asyncio.sleep(0.004)
        pages = await to_process(_ocr_case, case)
        return case, pages

    return dict(await asyncio.gather(*(_process(case) for case in cases)))


def _ocr_case(case: str) -> int:
    return len(case) * 2


async def coordinate_factory_telemetry(lines: Sequence[str]) -> dict[str, float]:
    """Ingest MQTT data asynchronously while running predictive analytics."""

    async def _coordinate(line: str) -> tuple[str, float]:
        payload = await _pull_factory_data(line)
        result = await to_process(_predict_failure, payload)
        return line, result

    return dict(await asyncio.gather(*(_coordinate(line) for line in lines)))


async def _pull_factory_data(line: str) -> list[int]:
    await asyncio.sleep(0.003)
    return [len(line), random.randint(1, 5)]


def _predict_failure(series: list[int]) -> float:
    return max(series) * 1.5


async def manage_support_workflows(chats: Sequence[str]) -> dict[str, int]:
    """Handle chat asynchronously while using multiprocessing for NLU."""

    async def _manage(chat: str) -> tuple[str, int]:
        await asyncio.sleep(0.002)
        intent = await to_process(_infer_intent, chat)
        return chat, intent

    return dict(await asyncio.gather(*(_manage(chat) for chat in chats)))


def _infer_intent(chat: str) -> int:
    return len(chat.split())


async def ingest_satellite_imagery(paths: Sequence[str]) -> dict[str, float]:
    """Download imagery asynchronously and orthorectify in processes."""

    async def _ingest(path: str) -> tuple[str, float]:
        await asyncio.sleep(0.004)
        result = await to_process(_orthorectify, path)
        return path, result

    return dict(await asyncio.gather(*(_ingest(path) for path in paths)))


def _orthorectify(path: str) -> float:
    return float(len(path))


async def reduce_scientific_data(streams: Sequence[str]) -> dict[str, float]:
    """Stream experiment output asynchronously while computing statistics."""

    async def _reduce(stream: str) -> tuple[str, float]:
        await asyncio.sleep(0.003)
        statistic = await to_process(_analyze_stream, stream)
        return stream, statistic

    return dict(await asyncio.gather(*(_reduce(stream) for stream in streams)))


def _analyze_stream(stream: str) -> float:
    return round(len(stream) / 3, 2)


async def rebuild_search_indices(sources: Sequence[str]) -> dict[str, int]:
    """Crawl sources with coroutines while tokenization happens in processes."""

    async def _rebuild(source: str) -> tuple[str, int]:
        await asyncio.sleep(0.003)
        tokens = await to_process(_tokenize_source, source)
        return source, tokens

    return dict(await asyncio.gather(*(_rebuild(source) for source in sources)))


def _tokenize_source(source: str) -> int:
    return len(source.split("/"))


__all__ = [
    "convert_camera_feeds",
    "execute_etl_jobs",
    "provide_pdf_generation",
    "orchestrate_speech_to_text",
    "coordinate_geospatial_tiles",
    "run_ci_pipeline",
    "manage_iot_telemetry",
    "execute_financial_settlements",
    "implement_cloud_backups",
    "drive_content_moderation",
    "deliver_recommendation_feeds",
    "maintain_multiplayer_state",
    "support_remote_rendering",
    "operate_trading_bots",
    "run_e_discovery",
    "coordinate_factory_telemetry",
    "manage_support_workflows",
    "ingest_satellite_imagery",
    "reduce_scientific_data",
    "rebuild_search_indices",
]
