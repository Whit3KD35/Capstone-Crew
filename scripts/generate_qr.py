#!/usr/bin/env python3
"""
Generate a QR code PNG for a deployed frontend URL.

This script uses the public QRServer API so no extra Python packages are required.
"""

from __future__ import annotations

import argparse
import pathlib
import urllib.parse
import urllib.request


def build_qr_api_url(target_url: str, size: int) -> str:
    encoded_target = urllib.parse.quote(target_url, safe="")
    return f"https://api.qrserver.com/v1/create-qr-code/?size={size}x{size}&data={encoded_target}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a PNG QR code for a URL.")
    parser.add_argument("--url", required=True, help="URL to encode in the QR code.")
    parser.add_argument(
        "--output",
        default="deployment-qr.png",
        help="Output PNG file path (default: deployment-qr.png).",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=512,
        help="QR image size in pixels (default: 512).",
    )
    args = parser.parse_args()

    if not args.url.startswith(("http://", "https://")):
        raise SystemExit("Error: --url must start with http:// or https://")

    output_path = pathlib.Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    qr_api_url = build_qr_api_url(args.url, args.size)

    with urllib.request.urlopen(qr_api_url, timeout=20) as response:
        png_bytes = response.read()

    output_path.write_bytes(png_bytes)
    print(f"QR code generated: {output_path}")


if __name__ == "__main__":
    main()
