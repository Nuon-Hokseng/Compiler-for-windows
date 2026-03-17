"""
Entrypoint — decrypts .env.enc into os.environ, then starts uvicorn.
"""

import base64
import hashlib
import os
import pathlib
import platform
import sys

SECRET_KEY = "9cbfcce635d1160bf8fd4143a322ef1c1edebc84749ae1d34bcb167347754406"


def _decrypt_env() -> None:
    """Read .env.enc alongside this file, decrypt, load into os.environ."""
    enc_path = pathlib.Path(__file__).resolve().parent / ".env.enc"
    if not enc_path.exists():
        print(f"[run] WARNING: {enc_path} not found — skipping env decrypt")
        return

    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    decoded = base64.b64decode(enc_path.read_bytes())
    decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(decoded))

    for line in decrypted.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        var, _, val = line.partition("=")
        os.environ[var.strip()] = val.strip()


def main() -> None:
    _decrypt_env()

    # Windows asyncio fix
    if platform.system() == "Windows":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)

    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
