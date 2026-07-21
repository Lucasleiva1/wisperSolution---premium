"""Verify a ScribeFloat installer checksum and Ed25519 signature."""

import argparse
import base64
import hashlib
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from updater import UPDATE_PUBLIC_KEY_B64  # noqa: E402


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

    digest = sha256_digest(args.installer)
    expected = Path(f"{args.installer}.sha256").read_text(encoding="ascii").split()[0]
    if digest.hex() != expected.lower():
        raise SystemExit("El SHA-256 no coincide.")

    signature = base64.b64decode(
        Path(f"{args.installer}.sig").read_text(encoding="ascii"), validate=True
    )
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(UPDATE_PUBLIC_KEY_B64))
    public_key.verify(signature, digest)

    try:
        public_key.verify(signature, b"\x00" * 32)
    except InvalidSignature:
        pass
    else:
        raise SystemExit("La prueba negativa de firma no fue rechazada.")

    print("SHA256_OK")
    print("ED25519_SIGNATURE_OK")
    print("TAMPER_REJECTED_OK")


if __name__ == "__main__":
    main()
