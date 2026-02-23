# AutoTruckBuilder Util

> **Portfolio Note:** This utility was built for a proprietary enterprise vehicle configuration system. The architecture and code are real — a demo version with a mock API and sample data is in progress for public use.

---

## What This Is

A production Python utility that automates the ingestion and processing of vehicle specification Excel files through a multi-stage async pipeline, ultimately generating **DCT (Data Configuration Tool)** outputs used in enterprise truck configuration workflows.

Think: drag-and-drop Excel files in, structured `.dctzip` configuration bundles out — with auth, retries, concurrency control, and progress tracking handled automatically.

---

## The Engineering Story

This wasn't a simple script. The real challenge was orchestrating **authenticated, async HTTP calls** across potentially dozens of files without hammering the API, losing track of failures, or making the operator babysit the process.

Key design decisions:

- **Async-first with `httpx`** — each file goes through spec fetching → DCT building → download as a fully async pipeline, keeping I/O from being the bottleneck
- **Semaphore-controlled concurrency** — prevents API overload while still processing files in parallel (default: 5 concurrent)
- **Automatic auth + retry handling** — token refresh and transient failure recovery are baked into the pipeline, not bolted on
- **Live console board** — real-time progress tracking across all concurrent jobs, not just a spinner
- **Structured summary output** — at the end you get a clean breakdown of successes, failures, and why things failed

---

## Features

- Async batch processing of multiple Excel files
- Auth management via `AsyncAuth` with automatic token refresh
- Configurable concurrency via semaphore
- Real-time progress tracking with a live console board
- Per-file error capture with a human-readable summary report
- TLS configuration with startup logging

---

## Requirements

- Python 3.8+
- `httpx`, `tqdm`
- Internal `core` package (enterprise dependency — mock version coming for demo)

---

## Usage

```bash
cd AutoTruckBuilder_util
python main.py
```

The tool will:
1. Scan the configured `xml_bucket` for Excel files
2. Authenticate and process each file through the pipeline concurrently
3. Output `.dctzip` files for each successful spec
4. Print a full run summary with status per file

---

## Project Structure

```
AutoTruckBuilder_util/
├── main.py              # Entry point — orchestrates async task queue
├── config.py            # Config, constants, TLS settings
├── pipeline.py          # Core async processing logic (fetch → build → download)
├── summary.py           # Terminal output and run reporting
└── core/                # Internal enterprise modules (demo stubs coming)
    ├── auth_edge.py     # Async token management
    ├── console_board.py # Live multi-job progress display
    ├── excel.py         # Excel parsing and spec extraction
    └── util.py          # Shared helpers
```

---

## Demo

> 🚧 A demo environment with a mock API server and sample Excel file is in progress. It will allow you to run the full pipeline locally without enterprise credentials.

In the meantime, feel free to reach out or open an issue if you'd like to discuss the architecture.

---

## License

See [LICENSE](LICENSE) for details.
