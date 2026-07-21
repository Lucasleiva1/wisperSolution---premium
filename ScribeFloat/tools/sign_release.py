"""Sign a ScribeFloat installer digest with the protected Ed25519 release key."""

import argparse
import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization


def sha256_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()

    key_dir = Path(os.environ["APPDATA"]) / "ScribeFloat Premium" / "updater"
    key_path = key_dir / "release-signing-ed25519.pem"
    password_path = key_dir / "release-signing-password.txt"
    if not key_path.is_file() or not password_path.is_file():
        raise SystemExit(f"Falta la clave privada protegida en {key_dir}")

    private_key = serialization.load_pem_private_key(
        key_path.read_bytes(),
        password=password_path.read_bytes(),
    )
    digest = sha256_digest(args.installer)
    signature = private_key.sign(digest)
    private_key.public_key().verify(signature, digest)

    signature_path = Path(f"{args.installer}.sig")
    signature_path.write_text(base64.b64encode(signature).decode("ascii"), encoding="ascii")
    print(f"Firma Ed25519 creada: {signature_path}")


if __name__ == "__main__":
    main()
