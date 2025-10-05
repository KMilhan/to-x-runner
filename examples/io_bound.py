"""I/O-bound integration scenarios implemented with unirun primitives."""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

from unirun import map as unirun_map
from unirun import thread_executor, to_thread


async def poll_regional_shards(shards: Sequence[str]) -> dict[str, str]:
    """Poll API shards concurrently using asyncio tasks orchestrated by unirun."""

    async def _poll(shard: str) -> tuple[str, str]:
        await asyncio.sleep(random.uniform(0.01, 0.05))
        return shard, f"{shard}-healthy"

    pairs = await asyncio.gather(*(_poll(shard) for shard in shards))
    return dict(pairs)


async def stream_pod_logs(pods: Sequence[str]) -> dict[str, list[str]]:
    """Stream pod logs by delegating blocking reads to the shared thread pool."""

    async def _stream(pod: str) -> tuple[str, list[str]]:
        def _read() -> list[str]:
            time.sleep(random.uniform(0.01, 0.03))
            return [f"{pod} line {index}" for index in range(3)]

        lines = await to_thread(_read)
        return pod, lines

    results = await asyncio.gather(*(_stream(pod) for pod in pods))
    return dict(results)


async def fan_out_smtp_confirmations(messages: Sequence[str]) -> list[str]:
    """Confirm SMTP deliveries concurrently while throttling socket creation."""

    semaphore = asyncio.Semaphore(5)

    async def _confirm(message: str) -> str:
        async with semaphore:
            await asyncio.sleep(0.02)
            return f"{message}: confirmed"

    return await asyncio.gather(*(_confirm(message) for message in messages))


async def mirror_cdn_artifacts(urls: Sequence[str]) -> list[str]:
    """Mirror CDN artifacts using asyncio tasks that imitate downloads."""

    async def _download(url: str) -> str:
        await asyncio.sleep(0.01)
        return f"mirror:{url}"

    return await asyncio.gather(*(_download(url) for url in urls))


async def backfill_rest_batches(endpoints: Sequence[str]) -> dict[str, int]:
    """Backfill paginated REST data and return per-endpoint batch counts."""

    async def _consume(endpoint: str) -> tuple[str, int]:
        pages = random.randint(1, 4)
        await asyncio.sleep(pages * 0.01)
        return endpoint, pages

    counts = await asyncio.gather(*(_consume(endpoint) for endpoint in endpoints))
    return dict(counts)


async def synchronize_crm_contacts(partners: Sequence[str]) -> dict[str, datetime]:
    """Synchronize CRM contacts with retries executed in the thread pool."""

    async def _sync(partner: str) -> tuple[str, datetime]:
        def _perform() -> datetime:
            for _ in range(2):
                if random.random() > 0.2:
                    break
                time.sleep(0.01)
            return datetime.utcnow()

        return partner, await to_thread(_perform)

    timestamps = await asyncio.gather(*(_sync(partner) for partner in partners))
    return dict(timestamps)


async def retrieve_firmware_manifests(devices: Sequence[str]) -> dict[str, dict[str, str]]:
    """Retrieve firmware manifests using thread-bound tasks with telemetry."""

    async def _retrieve(device: str) -> tuple[str, dict[str, str]]:
        def _probe() -> dict[str, str]:
            time.sleep(0.01)
            return {"device": device, "version": "1.2.3"}

        payload = await to_thread(_probe)
        payload["timestamp"] = datetime.utcnow().isoformat()
        return device, payload

    pairs = await asyncio.gather(*(_retrieve(device) for device in devices))
    return dict(pairs)


async def check_ssl_expiry(hosts: Sequence[str]) -> dict[str, timedelta]:
    """Check SSL expirations concurrently and compute renewal thresholds."""

    async def _check(host: str) -> tuple[str, timedelta]:
        def _probe() -> timedelta:
            time.sleep(0.01)
            return timedelta(days=random.randint(10, 90))

        return host, await to_thread(_probe)

    entries = await asyncio.gather(*(_check(host) for host in hosts))
    return dict(entries)


async def aggregate_financial_quotes(symbols: Sequence[str]) -> dict[str, float]:
    """Aggregate symbol quotes while sharing a cancellation scope."""

    async def _quote(symbol: str) -> tuple[str, float]:
        await asyncio.sleep(0.01)
        return symbol, round(random.uniform(10, 50), 2)

    tasks = [asyncio.create_task(_quote(symbol)) for symbol in symbols]
    try:
        pairs = await asyncio.gather(*tasks)
        return dict(pairs)
    finally:
        for task in tasks:
            task.cancel()


async def ingest_webhooks(payloads: Sequence[str]) -> list[str]:
    """Parse webhooks concurrently and return normalized payload identifiers."""

    async def _parse(payload: str) -> str:
        await asyncio.sleep(0.01)
        return payload.upper()

    return await asyncio.gather(*(_parse(payload) for payload in payloads))


async def fetch_entitlement_data(accounts: Sequence[str]) -> dict[str, int]:
    """Fetch entitlement data while guarding shared caches with a semaphore."""

    semaphore = asyncio.Semaphore(3)

    async def _fetch(account: str) -> tuple[str, int]:
        async with semaphore:
            await asyncio.sleep(0.01)
            return account, random.randint(1, 5)

    entries = await asyncio.gather(*(_fetch(account) for account in accounts))
    return dict(entries)


async def crawl_documentation_portals(urls: Sequence[str]) -> dict[str, int]:
    """Crawl documentation portals and offload parsing to the thread pool."""

    async def _crawl(url: str) -> tuple[str, int]:
        def _parse() -> int:
            time.sleep(0.01)
            return len(url)

        return url, await to_thread(_parse)

    return dict(await asyncio.gather(*(_crawl(url) for url in urls)))


async def replicate_database_snapshots(sources: Sequence[Path]) -> dict[str, Path]:
    """Replicate database snapshots under connection ceiling constraints."""

    async def _replicate(source: Path) -> tuple[str, Path]:
        def _copy() -> Path:
            time.sleep(0.02)
            return source.with_suffix(".replica")

        return source.name, await to_thread(_copy)

    return dict(await asyncio.gather(*(_replicate(source) for source in sources)))


async def refresh_cdn_metadata(regions: Sequence[str]) -> dict[str, datetime]:
    """Refresh CDN edge metadata concurrently and track completion times."""

    async def _refresh(region: str) -> tuple[str, datetime]:
        await asyncio.sleep(0.01)
        return region, datetime.utcnow()

    return dict(await asyncio.gather(*(_refresh(region) for region in regions)))


async def monitor_dns_propagation(hosts: Sequence[str]) -> dict[str, float]:
    """Monitor DNS propagation by dispatching dig-style probes in threads."""

    async def _probe(host: str) -> tuple[str, float]:
        def _dig() -> float:
            time.sleep(0.01)
            return round(random.uniform(0.1, 0.5), 3)

        return host, await to_thread(_dig)

    return dict(await asyncio.gather(*(_probe(host) for host in hosts)))


async def bulk_verify_email_deliverability(addresses: Sequence[str]) -> dict[str, bool]:
    """Verify email deliverability asynchronously with shared throttling."""

    semaphore = asyncio.Semaphore(10)

    async def _verify(address: str) -> tuple[str, bool]:
        async with semaphore:
            await asyncio.sleep(0.005)
            return address, address.endswith("@example.com")

    return dict(await asyncio.gather(*(_verify(address) for address in addresses)))


async def query_status_dashboards(dashboards: Sequence[str]) -> dict[str, str]:
    """Query dashboards concurrently and normalize payloads via thread workers."""

    async def _query(board: str) -> tuple[str, str]:
        def _fetch() -> str:
            time.sleep(0.01)
            return f"{board}:green"

        return board, await to_thread(_fetch)

    raw_results = await asyncio.gather(*(_query(board) for board in dashboards))
    executor = thread_executor()

    def _normalize(entry: tuple[str, str]) -> tuple[str, str]:
        board, status = entry
        return board, status.upper()

    return dict(unirun_map(executor, _normalize, raw_results))


async def validate_webhook_signatures(payloads: Sequence[bytes]) -> dict[int, bool]:
    """Validate webhook signatures with context preserved across tasks."""

    async def _validate(index: int, payload: bytes) -> tuple[int, bool]:
        await asyncio.sleep(0.005)
        return index, payload.endswith(b"signature")

    tasks = [
        asyncio.create_task(_validate(index, payload))
        for index, payload in enumerate(payloads)
    ]
    return dict(await asyncio.gather(*tasks))


async def scrape_competitor_pricing(urls: Sequence[str]) -> dict[str, float]:
    """Scrape pricing pages with polite delays enforced by asyncio primitives."""

    async def _scrape(url: str) -> tuple[str, float]:
        await asyncio.sleep(0.015)
        return url, round(random.uniform(5.0, 20.0), 2)

    return dict(await asyncio.gather(*(_scrape(url) for url in urls)))


async def rotate_machine_credentials(machines: Sequence[str]) -> dict[str, datetime]:
    """Rotate machine credentials concurrently with unified cancellation."""

    async def _rotate(machine: str) -> tuple[str, datetime]:
        await asyncio.sleep(0.01)
        return machine, datetime.utcnow()

    tasks = [asyncio.create_task(_rotate(machine)) for machine in machines]
    try:
        results = await asyncio.gather(*tasks)
        return dict(results)
    finally:
        for task in tasks:
            task.cancel()




__all__ = [
    "poll_regional_shards",
    "stream_pod_logs",
    "fan_out_smtp_confirmations",
    "mirror_cdn_artifacts",
    "backfill_rest_batches",
    "synchronize_crm_contacts",
    "retrieve_firmware_manifests",
    "check_ssl_expiry",
    "aggregate_financial_quotes",
    "ingest_webhooks",
    "fetch_entitlement_data",
    "crawl_documentation_portals",
    "replicate_database_snapshots",
    "refresh_cdn_metadata",
    "monitor_dns_propagation",
    "bulk_verify_email_deliverability",
    "query_status_dashboards",
    "validate_webhook_signatures",
    "scrape_competitor_pricing",
    "rotate_machine_credentials",
]
