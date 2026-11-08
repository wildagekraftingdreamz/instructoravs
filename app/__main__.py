"""``python -m app`` - start the local studio and open it once it answers."""

from __future__ import annotations

import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from .config import HOST, PORT


def _open_when_ready(url: str, attempts: int = 60) -> None:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(0.5)


def main() -> None:
    url = f"http://{HOST}:{PORT}"
    if "--no-browser" not in sys.argv:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    print(f"Instructoravs on {url}  (store: data/documents)")
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
