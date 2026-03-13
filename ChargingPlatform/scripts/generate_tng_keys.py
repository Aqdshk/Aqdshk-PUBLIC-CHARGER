#!/usr/bin/env python3
"""
Generate RSA 2048 key pair for TNG OrderCode API.
Outputs PKCS8 format (private + public) as required by TNG.

Usage: python scripts/generate_tng_keys.py
Output: tng_private_key.pem, tng_public_key.pem (in current directory)
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def main():
    # Generate RSA 2048 key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Private key in PKCS8 PEM (no passphrase)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Public key in PKCS8 PEM
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Save to files
    with open("tng_private_key.pem", "wb") as f:
        f.write(private_pem)
    with open("tng_public_key.pem", "wb") as f:
        f.write(public_pem)

    print("[OK] Keys generated successfully!")
    print()
    print("Files created:")
    print("  - tng_private_key.pem  (keep secret! add to .env as PAYMENT_TNG_PRIVATE_KEY)")
    print("  - tng_public_key.pem   (send this to TNG)")
    print()
    print("For .env, use single line (escape newlines as \\n):")
    print("  PAYMENT_TNG_PRIVATE_KEY=\"-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\"")
    print()
    print("Or copy the full content of tng_private_key.pem into .env (multi-line in quotes).")

if __name__ == "__main__":
    main()
