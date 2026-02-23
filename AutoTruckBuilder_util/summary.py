from config import _fmt


def print_summary(total: int, failures: int, durations: list[float], total_time: float):
    """Print pipeline execution summary."""
    print(f"\n{'='*60}")
    print(f"Files: {total} | Failed: {failures} | Successful: {len(durations)}")
    if durations:
        print(f"Total time: {_fmt(total_time)} | Avg per file: {_fmt(sum(durations)/len(durations))}")
    print(f"{'='*60}")