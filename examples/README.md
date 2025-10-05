# Example Catalog

The `examples` package contains runnable, standard-library-aligned demonstrations
that highlight how `unirun` composes `asyncio`, thread pools, and
`ProcessPoolExecutor` helpers without inventing new concurrency vocabulary. Each
module exposes a curated `SCENARIOS` collection of `ExampleScenario` objects plus
a `run_all()` helper so you can preview realistic workloads end-to-end.

```bash
# Execute the CPU-bound catalog
python -m examples.cpu_bound

# Execute the asyncio-oriented recipes
python -m examples.io_bound

# Execute mixed async + process orchestration pipelines
python -m examples.mixed_pipelines
```

Running any module prints a formatted summary for every scenario along with the
structured output payload produced by the underlying workload.

## Scenario Structure

Every scenario pairs a real-world story with the callable, positional arguments,
and metadata tags. The shared `ExampleScenario.execute()` helper transparently
runs synchronous callables as well as coroutine functions by invoking
`asyncio.run()` under the hood. The resulting `ExampleResult` includes:

- `name`: Human-friendly label rendered in reports.
- `output`: The concrete payload returned by the workload.
- `tags`: Lightweight labels such as `cpu`, `asyncio`, or `process` that make it
  simple to filter or group demonstrations in higher-level documentation.

You can import the catalog to integrate with notebooks or tutorials:

```python
from examples.cpu_bound import SCENARIOS as CPU_SCENARIOS
from examples.io_bound import SCENARIOS as IO_SCENARIOS

for scenario in CPU_SCENARIOS + IO_SCENARIOS:
    result = scenario.execute()
    print(result.name, result.tags, result.output)
```

## CPU-Bound Highlights

| Scenario | Function | Summary |
| --- | --- | --- |
| Marketing thumbnail refresh | `render_video_thumbnails` | Encodes video frames in parallel processes so FFmpeg-style loops avoid the GIL. |
| Archive digest audit | `compute_archive_digests` | Computes FNV digests for regulatory evidence using worker processes. |
| Monte Carlo VaR | `run_monte_carlo_simulations` | Estimates trading book risk via process-backed Monte Carlo simulations. |
| Model grid search | `train_model_grid` | Trains lightweight models across a hyperparameter sweep in parallel. |
| Genomics alignment | `align_genomic_sequences` | Scores sequencing reads against a synthetic reference genome. |
| Static site build | `build_static_site` | Compiles Markdown into HTML snippets inside processes for isolation. |
| Matrix regression | `multiply_matrices` | Multiplies dense matrices to stress-test simulation kernels. |
| Render farm sizing | `ray_trace_frames` | Approximates ray tracing workloads while collecting completion callbacks. |
| Quarterly tax load | `calculate_tax_batches` | Applies progressive bracket calculations in process workers. |
| GIS normalization | `normalize_gis_tiles` | Normalizes elevation tiles without sharing mutable state between tasks. |

## I/O-Bound Highlights

| Scenario | Function | Summary |
| --- | --- | --- |
| Regional health polling | `poll_regional_shards` | Checks API shard health concurrently via `asyncio.gather`. |
| Log streaming bridge | `stream_pod_logs` | Wraps blocking Kubernetes log reads with `to_thread`. |
| SMTP confirmation | `fan_out_smtp_confirmations` | Coordinates socket creation using semaphores to respect SMTP limits. |
| Firmware manifest sync | `retrieve_firmware_manifests` | Offloads device probes to threads while awaiting metadata. |
| SSL expiry audit | `check_ssl_expiry` | Executes TLS probes inside the default thread pool. |
| Entitlement refresh | `fetch_entitlement_data` | Uses a semaphore to guard cache refresh calls. |
| Snapshot replication | `replicate_database_snapshots` | Copies snapshots in threads while coroutines track progress. |
| DNS propagation watch | `monitor_dns_propagation` | Delegates blocking DNS lookups to the thread pool. |

## Mixed Pipeline Highlights

| Scenario | Function | Summary |
| --- | --- | --- |
| Camera feed conversion | `convert_camera_feeds` | Streams frames asynchronously and encodes them in process workers. |
| ETL validation | `execute_etl_jobs` | Downloads objects via `asyncio` before validating payloads in processes. |
| Speech-to-text orchestration | `orchestrate_speech_to_text` | Uploads audio chunks while CPU-bound transcription runs in parallel. |
| CI pipeline | `run_ci_pipeline` | Fetches dependencies asynchronously and runs subprocess-backed test suites. |
| IoT anomaly detection | `manage_iot_telemetry` | Collects device payloads via async brokers and scores them per process. |
| Ledger settlement | `execute_financial_settlements` | Reconciles ledger entries using CPU-bound reconciliation workers. |
| Content moderation | `drive_content_moderation` | Normalizes items asynchronously and computes scores in processes. |
| Factory telemetry | `coordinate_factory_telemetry` | Streams line telemetry while predictive analytics execute out of band. |

Each table lists a subset of the full catalog; inspect the module-level
`SCENARIOS` lists for additional demonstrations. The workloads are deterministic
so you can embed them in tutorials, benchmarks, or smoke tests without seeding
randomness manually.
