from __future__ import annotations


def compute_checksum(body: str) -> str:
    value = 0
    for ch in body:
        value ^= ord(ch)
    return f"{value:02X}"


def with_checksum(body: str) -> str:
    return f"${body}*{compute_checksum(body)}"
