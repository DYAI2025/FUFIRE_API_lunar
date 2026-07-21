#!/usr/bin/env python3
"""
Generate a FuFirE API key with sufficient entropy.

Usage:
    python scripts/generate_api_key.py --tier pro
    python scripts/generate_api_key.py --tier free

Output: prints the key to stdout (add to FUFIRE_API_KEYS env var or Fly secrets)

Key format: ff_<tier>_<32-char hex>
Entropy: 128 bits (secrets.token_hex(16) → 32 hex chars)
"""
import argparse
import secrets

VALID_TIERS = {"free", "starter", "pro", "enterprise"}


def generate_key(tier: str) -> str:
    if tier not in VALID_TIERS:
        raise ValueError(f"Invalid tier: {tier}. Must be one of {VALID_TIERS}")
    random_part = secrets.token_hex(16)  # 128 bits entropy
    return f"ff_{tier}_{random_part}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a FuFirE API key")
    parser.add_argument("--tier", required=True, choices=sorted(VALID_TIERS))
    args = parser.parse_args()
    print(generate_key(args.tier))
