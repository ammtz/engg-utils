# AutoTruckBuilder Util

A Python utility for processing Excel files through the processing pipeline to generate DCT (Data Configuration Tool) outputs for vehicle specifications.

## Description

This tool automates the processing of Excel spreadsheets containing vehicle spec data. It handles authentication, spec fetching, DCT building, and downloading results asynchronously for efficient batch processing.

## Features

- Asynchronous processing of multiple Excel files
- Automatic authentication and retry handling
- Progress tracking with console board
- Error handling and summary reporting
- TLS verification configuration

## Requirements

- Python 3.8+
- Dependencies: `httpx`, `tqdm`, `pathlib` (standard library), and the `core` package

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ammtz/engg-utils.git
   cd engg-utils
   ```

2. Install dependencies (if using pip):
   ```bash
   pip install httpx tqdm
   ```

3. Ensure the `core` package is available (internal dependency).

## Usage

Navigate to the app directory and run the main script:

```bash
cd AutoTruckBuilder_util
python main.py
```

The tool will:
- Scan for Excel files in the configured `xml_bucket`
- Process each file through the processing pipeline
- Output `.dctzip` files for successful processing
- Display a summary of results

## Configuration

- TLS settings are logged at startup
- Semaphore limits concurrent operations (default: 5)
- Authentication is handled via the `AsyncAuth` class

## Project Structure

```
AutoTruckBuilder_util/
├── main.py              # Entry point
├── config.py            # Configuration and utilities
├── pipeline.py          # Core processing logic
├── summary.py           # Output formatting
└── core/             # Internal modules
    ├── auth_edge.py
    ├── console_board.py
    ├── excel.py
    └── util.py
```

## License

See LICENSE file for details.