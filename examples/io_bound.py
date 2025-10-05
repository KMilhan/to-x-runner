"""I/O-bound integration scenarios implemented with familiar asyncio patterns.

The examples highlight how ``unirun`` bridges ``asyncio`` tasks with plain
thread pools so blocking operations like log streaming and cryptographic probes
remain ergonomic while keeping the standard-library terminology front and center.
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

from unirun import map as unirun_map
from unirun import thread_executor, to_thread

from ._structures import ExampleResult, ExampleScenario, format_result


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
    "SCENARIOS",
    "run_all",
]


async def poll_regional_shards(shards: Sequence[str]) -> dict[str, str]:
    """Poll API shards concurrently using ``asyncio.gather``.

    Args:
        shards: Region identifiers representing API hosts.

    Returns:
        dict[str, str]: Region keyed health statuses returned by the probes.
    """

    async def _poll(shard: str) -> tuple[str, str]:
        await asyncio.sleep(random.uniform(0.01, 0.05))
        return shard, f"{shard}-healthy"

    pairs = await asyncio.gather(*(_poll(shard) for shard in shards))
    return dict(pairs)


async def stream_pod_logs(pods: Sequence[str]) -> dict[str, list[str]]:
    """Stream pod logs by delegating blocking reads to the shared thread pool.

    Args:
        pods: Kubernetes pod names to stream from.

    Returns:
        dict[str, list[str]]: Collected log lines per pod.
    """

    async def _stream(pod: str) -> tuple[str, list[str]]:
        def _read() -> list[str]:
            time.sleep(random.uniform(0.01, 0.03))
            return [f"{pod} line {index}" for index in range(3)]

        lines = await to_thread(_read)
        return pod, lines

    results = await asyncio.gather(*(_stream(pod) for pod in pods))
    return dict(results)


async def fan_out_smtp_confirmations(messages: Sequence[str]) -> list[str]:
    """Confirm SMTP deliveries concurrently while controlling concurrency.

    Args:
        messages: Message identifiers pending SMTP confirmation.

    Returns:
        list[str]: Confirmation payloads for each message.
    """

    semaphore = asyncio.Semaphore(5)

    async def _confirm(message: str) -> str:
        async with semaphore:
            await asyncio.sleep(0.02)
            return f"{message}: confirmed"

    return await asyncio.gather(*(_confirm(message) for message in messages))


async def mirror_cdn_artifacts(urls: Sequence[str]) -> list[str]:
    """Mirror CDN artifacts using coroutine-based download simulations.

    Args:
        urls: CDN artifact URLs to mirror.

    Returns:
        list[str]: Mirror locations created by the job.
    """

    async def _download(url: str) -> str:
        await asyncio.sleep(0.01)
        return f"mirror:{url}"

    return await asyncio.gather(*(_download(url) for url in urls))


async def backfill_rest_batches(endpoints: Sequence[str]) -> dict[str, int]:
    """Backfill paginated REST data and return per-endpoint batch counts.

    Args:
        endpoints: REST endpoints to backfill.

    Returns:
        dict[str, int]: Page counts for each endpoint.
    """

    async def _consume(endpoint: str) -> tuple[str, int]:
        pages = random.randint(1, 4)
        await asyncio.sleep(pages * 0.01)
        return endpoint, pages

    counts = await asyncio.gather(*(_consume(endpoint) for endpoint in endpoints))
    return dict(counts)


async def synchronize_crm_contacts(partners: Sequence[str]) -> dict[str, datetime]:
    """Synchronize CRM contacts with retries executed in the thread pool.

    Args:
        partners: Partner account identifiers.

    Returns:
        dict[str, datetime]: Synchronization timestamps keyed by partner.
    """

    async def _sync(partner: str) -> tuple[str, datetime]:
        def _perform() -> datetime:
            for _ in range(2):
                if random.random() > 0.2:
                    break
                time.sleep(0.01)
            return datetime.now(UTC)

        return partner, await to_thread(_perform)

    timestamps = await asyncio.gather(*(_sync(partner) for partner in partners))
    return dict(timestamps)


async def retrieve_firmware_manifests(devices: Sequence[str]) -> dict[str, dict[str, str]]:
    """Retrieve firmware manifests by offloading blocking probes to threads.

    Args:
        devices: Device identifiers needing firmware metadata.

    Returns:
        dict[str, dict[str, str]]: Firmware manifest data per device.
    """

    async def _retrieve(device: str) -> tuple[str, dict[str, str]]:
        def _probe() -> dict[str, str]:
            time.sleep(0.01)
            return {"device": device, "version": "1.2.3"}

        payload = await to_thread(_probe)
        payload["timestamp"] = datetime.now(UTC).isoformat()
        return device, payload

    pairs = await asyncio.gather(*(_retrieve(device) for device in devices))
    return dict(pairs)


async def check_ssl_expiry(hosts: Sequence[str]) -> dict[str, timedelta]:
    """Check SSL expirations concurrently with ``asyncio.gather``.

    Args:
        hosts: Hostnames to inspect via TLS probes.

    Returns:
        dict[str, timedelta]: Time-to-expiry per host.
    """

    async def _check(host: str) -> tuple[str, timedelta]:
        def _probe() -> timedelta:
            time.sleep(0.01)
            return timedelta(days=random.randint(10, 90))

        return host, await to_thread(_probe)

    entries = await asyncio.gather(*(_check(host) for host in hosts))
    return dict(entries)


async def aggregate_financial_quotes(symbols: Sequence[str]) -> dict[str, float]:
    """Aggregate market quotes while sharing a cancellation scope.

    Args:
        symbols: Stock or commodity tickers.

    Returns:
        dict[str, float]: Last price per symbol.
    """

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
    """Parse webhooks concurrently and return normalized payload identifiers.

    Args:
        payloads: Raw webhook payloads.

    Returns:
        list[str]: Normalized webhook identifiers.
    """

    async def _parse(payload: str) -> str:
        await asyncio.sleep(0.01)
        return payload.upper()

    return await asyncio.gather(*(_parse(payload) for payload in payloads))


async def fetch_entitlement_data(accounts: Sequence[str]) -> dict[str, int]:
    """Fetch entitlement data while guarding shared caches with semaphores.

    Args:
        accounts: Account identifiers needing entitlement refreshes.

    Returns:
        dict[str, int]: Entitlement counts keyed by account.
    """

    semaphore = asyncio.Semaphore(3)

    async def _fetch(account: str) -> tuple[str, int]:
        async with semaphore:
            await asyncio.sleep(0.01)
            return account, random.randint(1, 5)

    entries = await asyncio.gather(*(_fetch(account) for account in accounts))
    return dict(entries)


async def crawl_documentation_portals(urls: Sequence[str]) -> dict[str, int]:
    """Crawl documentation portals and offload parsing to the thread pool.

    Args:
        urls: Documentation URLs to crawl.

    Returns:
        dict[str, int]: Parsed byte counts per URL.
    """

    async def _crawl(url: str) -> tuple[str, int]:
        def _parse() -> int:
            time.sleep(0.01)
            return len(url)

        return url, await to_thread(_parse)

    return dict(await asyncio.gather(*(_crawl(url) for url in urls)))


async def replicate_database_snapshots(sources: Sequence[Path]) -> dict[str, Path]:
    """Replicate database snapshots under connection ceiling constraints.

    Args:
        sources: Snapshot file paths.

    Returns:
        dict[str, Path]: Replica paths keyed by original snapshot name.
    """

    async def _replicate(source: Path) -> tuple[str, Path]:
        def _copy() -> Path:
            time.sleep(0.02)
            return source.with_suffix(".replica")

        return source.name, await to_thread(_copy)

    return dict(await asyncio.gather(*(_replicate(source) for source in sources)))


async def refresh_cdn_metadata(regions: Sequence[str]) -> dict[str, datetime]:
    """Refresh CDN edge metadata concurrently and track completion times.

    Args:
        regions: CDN region identifiers requiring metadata refresh.

    Returns:
        dict[str, datetime]: Completion timestamps keyed by region.
    """

    async def _refresh(region: str) -> tuple[str, datetime]:
        await asyncio.sleep(0.01)
        return region, datetime.now(UTC)

    return dict(await asyncio.gather(*(_refresh(region) for region in regions)))


async def monitor_dns_propagation(hosts: Sequence[str]) -> dict[str, float]:
    """Monitor DNS propagation by dispatching dig-style probes in threads.

    Args:
        hosts: Hostnames to query across resolvers.

    Returns:
        dict[str, float]: Propagation latency per host in seconds.
    """

    async def _probe(host: str) -> tuple[str, float]:
        def _dig() -> float:
            time.sleep(0.01)
            return round(random.uniform(0.1, 0.5), 3)

        return host, await to_thread(_dig)

    return dict(await asyncio.gather(*(_probe(host) for host in hosts)))


async def bulk_verify_email_deliverability(addresses: Sequence[str]) -> dict[str, bool]:
    """Verify email deliverability asynchronously with shared throttling.

    Args:
        addresses: Email addresses to verify.

    Returns:
        dict[str, bool]: Deliverability flag keyed by address.
    """

    semaphore = asyncio.Semaphore(10)

    async def _verify(address: str) -> tuple[str, bool]:
        async with semaphore:
            await asyncio.sleep(0.005)
            return address, address.endswith("@example.com")

    return dict(await asyncio.gather(*(_verify(address) for address in addresses)))


async def query_status_dashboards(dashboards: Sequence[str]) -> dict[str, str]:
    """Query dashboards and normalize payloads via thread workers.

    Args:
        dashboards: Dashboard identifiers to fetch.

    Returns:
        dict[str, str]: Normalized status payload per dashboard.
    """

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
    """Validate webhook signatures with context preserved across tasks.

    Args:
        payloads: Serialized webhook payloads.

    Returns:
        dict[int, bool]: Validation flag per payload.
    """

    async def _validate(index: int, payload: bytes) -> tuple[int, bool]:
        await asyncio.sleep(0.005)
        return index, payload.endswith(b"signature")

    tasks = [
        asyncio.create_task(_validate(index, payload))
        for index, payload in enumerate(payloads)
    ]
    return dict(await asyncio.gather(*tasks))


async def scrape_competitor_pricing(urls: Sequence[str]) -> dict[str, float]:
    """Scrape pricing pages with polite delays enforced by asyncio primitives.

    Args:
        urls: Competitor URLs to sample.

    Returns:
        dict[str, float]: Extracted price per URL.
    """

    async def _scrape(url: str) -> tuple[str, float]:
        await asyncio.sleep(0.015)
        return url, round(random.uniform(5.0, 20.0), 2)

    return dict(await asyncio.gather(*(_scrape(url) for url in urls)))


async def rotate_machine_credentials(machines: Sequence[str]) -> dict[str, datetime]:
    """Rotate machine credentials concurrently with unified cancellation.

    Args:
        machines: Machine identifiers that require credential rotation.

    Returns:
        dict[str, datetime]: Rotation completion times keyed by machine.
    """

    async def _rotate(machine: str) -> tuple[str, datetime]:
        await asyncio.sleep(0.01)
        return machine, datetime.now(UTC)

    tasks = [asyncio.create_task(_rotate(machine)) for machine in machines]
    try:
        results = await asyncio.gather(*tasks)
        return dict(results)
    finally:
        for task in tasks:
            task.cancel()


SCENARIOS: list[ExampleScenario[Any]] = [
    ExampleScenario(
        name="Regional health polling",
        summary="Validates API shard health across data centers.",
        details=(
            "Customer support teams rely on a shard health snapshot before "
            "opening trading hours. ``asyncio`` fan-out keeps the syntax for "
            "polling readable while ``unirun`` orchestrates the event loop."
        ),
        entrypoint=poll_regional_shards,
        args=(
            (
                "us-east-1",
                "eu-central-1",
                "ap-southeast-2",
            ),
        ),
        tags=("io", "asyncio"),
    ),
    ExampleScenario(
        name="Log streaming bridge",
        summary="Streams pod logs without blocking the loop.",
        details=(
            "SRE dashboards stream the last hundred log lines from production pods. "
            "``to_thread`` wraps the blocking tail call while the coroutine "
            "awaits results."),
        entrypoint=stream_pod_logs,
        args=(("api-0", "api-1"),),
        tags=("io", "threads"),
    ),
    ExampleScenario(
        name="SMTP confirmation",
        summary="Confirms outbound messages with throttling.",
        details=(
            "Transactional email systems verify deliveries in batches. A "
            "semaphore caps concurrent socket creation to keep the MTA happy."),
        entrypoint=fan_out_smtp_confirmations,
        args=(("msg-1", "msg-2", "msg-3", "msg-4"),),
        tags=("io", "asyncio"),
    ),
    ExampleScenario(
        name="Firmware manifest sync",
        summary="Collects firmware metadata from field devices.",
        details=(
            "Device management portals invoke blocking RPCs per device. Using "
            "``to_thread`` keeps the coroutine responsive while threads handle the I/O."),
        entrypoint=retrieve_firmware_manifests,
        args=(("sensor-a", "sensor-b", "sensor-c"),),
        tags=("io", "threads"),
    ),
    ExampleScenario(
        name="SSL expiry audit",
        summary="Captures certificate expirations for critical hosts.",
        details=(
            "Security teams run continuous TLS expiry audits. Blocking SSL probes "
            "move to the default thread executor via ``to_thread``."),
        entrypoint=check_ssl_expiry,
        args=(("login.example.com", "api.example.com"),),
        tags=("io", "threads"),
    ),
    ExampleScenario(
        name="Entitlement refresh",
        summary="Refreshes account entitlements with cache-aware throttling.",
        details=(
            "Revenue systems recalculate seat entitlements nightly. A semaphore "
            "keeps calls to the shared cache under control."),
        entrypoint=fetch_entitlement_data,
        args=(("acme", "globex", "initech"),),
        tags=("io", "asyncio"),
    ),
    ExampleScenario(
        name="Snapshot replication",
        summary="Copies snapshots into cold storage without blocking requests.",
        details=(
            "Disaster recovery plans store database snapshots in colder storage. "
            "Threads copy the payload while async callers coordinate progress."),
        entrypoint=replicate_database_snapshots,
        args=((Path("/tmp/pg.dump"), Path("/tmp/redis.dump")),),
        tags=("io", "threads"),
    ),
    ExampleScenario(
        name="DNS propagation watch",
        summary="Calculates propagation latencies during rollouts.",
        details=(
            "Networking teams monitor DNS after record pushes. The coroutine drives "
            "probe fan-out while threads run blocking dig commands."),
        entrypoint=monitor_dns_propagation,
        args=(("edge.example.com", "cdn.example.com"),),
        tags=("io", "threads"),
    ),
]


def run_all(verbose: bool = True) -> list[ExampleResult[Any]]:
    """Execute each I/O-bound scenario and optionally print formatted output.

    Args:
        verbose: When ``True`` the function prints human-readable summaries.

    Returns:
        list[ExampleResult[Any]]: Results produced by the scenarios.
    """

    results: list[ExampleResult[Any]] = []
    for scenario in SCENARIOS:
        result = scenario.execute()
        results.append(result)
        if verbose:
            print(format_result(result))
    return results


if __name__ == "__main__":
    run_all()
