#!/usr/bin/env python3
"""Generate small deterministic RGBA and indexed PNG fixtures."""
from pathlib import Path
import struct
import zlib


FIXTURES = Path(__file__).resolve().parents[1] / "investigations/7.3.0-functional/cases/png-decoding/fixtures"


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def png(width, height, bit_depth, color_type, chunks, rows):
    header = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + b"".join(chunk(kind, data) for kind, data in chunks)
            + chunk(b"IDAT", zlib.compress(b"".join(rows)))
            + chunk(b"IEND", b""))


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    rgba_rows = [
        b"\x00" + bytes((255, 0, 0, 128, 0, 255, 0, 255)),
        b"\x00" + bytes((0, 0, 255, 0, 255, 255, 255, 255)),
    ]
    indexed_rows = [b"\x00\x00\x01", b"\x00\x02\x00"]
    (FIXTURES / "alpha.png").write_bytes(png(2, 2, 8, 6, [], rgba_rows))
    (FIXTURES / "indexed.png").write_bytes(
        png(2, 2, 8, 3, [(b"PLTE", bytes((255, 0, 0, 0, 255, 0, 0, 0, 255))),
                         (b"tRNS", bytes((255, 0, 128)))], indexed_rows))
    (FIXTURES / "tcz-png.png").write_bytes(png(2, 2, 8, 6, [], rgba_rows))
    (FIXTURES / "invalid.bin").write_bytes(b"not a PNG\x00\xff")


if __name__ == "__main__":
    main()
