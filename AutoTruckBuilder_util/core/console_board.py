# console_board.py
import sys
import threading
from tqdm import tqdm

class ConsoleBoard:
    """Fixed N-line dashboard with tqdm progress bars for each job."""
    def __init__(self, n_lines: int):
        self.n = n_lines
        self._lock = threading.Lock()
        self._bars: dict[int, tqdm] = {}
        self._disable = not sys.stdout.isatty()

        for i in range(n_lines):
            bar = tqdm(
                total=100,
                position=i,
                desc=f"Job {i+1}",
                bar_format="{desc}: {percentage:3.0f}%|{bar}| [{elapsed}]",
                leave=True,
                dynamic_ncols=True,
                disable=self._disable,
                file=sys.stdout,
            )
            self._bars[i] = bar

    def set_progress(self, i: int, text: str, percent: int):
        with self._lock:
            bar = self._bars.get(i)
            if bar:
                pct = max(0, min(100, int(percent)))
                bar.n = pct
                bar.set_description_str(text, refresh=False)
                bar.refresh()

    def complete(self, i: int, text: str = "DONE ✓"):
        with self._lock:
            bar = self._bars.get(i)
            if bar:
                bar.n = 100
                bar.set_description_str(text, refresh=False)
                bar.refresh()
                bar.close()

    def fail(self, i: int, text: str = "FAILED ✗"):
        with self._lock:
            bar = self._bars.get(i)
            if bar:
                bar.set_description_str(text, refresh=False)
                try:
                    bar.colour = "red"
                except Exception:
                    pass
                bar.refresh()
                bar.close()

    def close_all(self):
        with self._lock:
            for bar in self._bars.values():
                try:
                    bar.close()
                except Exception:
                    pass
            # Safety: close any stragglers tqdm is tracking
            try:
                for inst in list(tqdm._instances):  # type: ignore[attr-defined]
                    try:
                        inst.close()
                    except Exception:
                        pass
            except Exception:
                pass

    @staticmethod
    def write(msg: str):
        """Use tqdm-safe writes to avoid bar redraws."""
        tqdm.write(msg)
