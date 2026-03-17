"""
Re-encrypt backend/.env and frontend/.env -> .env.enc

Run from the project root whenever you update either .env:
    python create_env.py
"""

import base64
import hashlib
import pathlib
import sys

SECRET_KEY = "9cbfcce635d1160bf8fd4143a322ef1c1edebc84749ae1d34bcb167347754406"

ROOT = pathlib.Path(__file__).resolve().parent

# All .env files to encrypt: (source, destination)
ENV_PAIRS = [
    (ROOT / "backend" / ".env", ROOT / "backend" / ".env.enc"),
    (ROOT / "frontend" / ".env", ROOT / "frontend" / ".env.enc"),
]


def _encrypt_file(env_path: pathlib.Path, enc_path: pathlib.Path) -> list[str]:
    """Encrypt a single .env file. Returns list of key names found."""
    if not env_path.exists():
        print(f"  SKIP: {env_path} not found")
        return []

    env_bytes = env_path.read_bytes()
    key = hashlib.sha256(SECRET_KEY.encode()).digest()

    encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(env_bytes))
    encoded = base64.b64encode(encrypted)
    enc_path.write_bytes(encoded)

    keys_found: list[str] = []
    for line in env_bytes.decode("utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys_found.append(line.split("=", 1)[0].strip())

    print(f"  Encrypted {len(env_bytes)} bytes -> {enc_path.relative_to(ROOT)}")
    return keys_found


def main() -> None:
    print("Encrypting .env files...\n")
    all_keys: dict[str, list[str]] = {}

    for env_path, enc_path in ENV_PAIRS:
        label = env_path.parent.name
        print(f"[{label}]")
        keys = _encrypt_file(env_path, enc_path)
        if keys:
            all_keys[label] = keys
        print()

    # Summary
    print("Keys encrypted:")
    for section, keys in all_keys.items():
        print(f"  [{section}]")
        for k in keys:
            print(f"    - {k}")

    print("\nDone. Remember to exclude .env files from any zip/distribution!")


if __name__ == "__main__":
    main()
