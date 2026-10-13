"""Durable worker; importing extension modules registers their handlers."""
import importlib
import signal
import sys
import time
from .jobs import run_once
from .settings import settings

MODULES = ("app.core_api", "app.learning_api", "app.sessions", "app.review", "app.ingestion_api", "app.ingest", "app.sources")

def load_handlers():
    for name in MODULES:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name != name:
                raise

def main():
    settings.validate()
    load_handlers()
    if "--once" in sys.argv:
        run_once()
        return
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopped:
        worked = run_once()
        if not worked:
            time.sleep(1)

if __name__ == "__main__":
    main()
