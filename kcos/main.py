from __future__ import annotations

import argparse
import asyncio
import threading

import uvicorn

from .config import settings
from .runtime_config import RuntimeConfigStore


def _load_desired_state():
    store = RuntimeConfigStore(settings.runtime_dir)
    store.apply_to(settings)
    return store


def serve_api():
    from .api import app
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["runtime", "research", "genesis", "admin-token"], nargs="?", default="runtime")
    mode = parser.parse_args().mode
    _load_desired_state()
    if mode == "genesis":
        from .genesis import main as genesis_main
        return genesis_main()
    if mode == "admin-token":
        token = RuntimeConfigStore(settings.runtime_dir).generate_admin_token()
        print(token)
        return None
    if mode == "research":
        from .research.worker import run
        return asyncio.run(run())
    from .autonomous_runtime import AutonomousRuntime
    threading.Thread(target=serve_api, daemon=True).start()
    asyncio.run(AutonomousRuntime().run_forever())


if __name__ == "__main__":
    main()
