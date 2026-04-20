#!/usr/bin/env python3
"""Generate one-time invite codes and matching SQL inserts."""

from __future__ import annotations

import argparse
import hashlib
import secrets
from dataclasses import dataclass

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass
class InviteCode:
    plain: str
    code_hash: str
    code_prefix: str


def normalize_code(value: str) -> str:
    return value.strip().upper().replace("-", "").replace(" ", "")


def generate_plain_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def build_invite_code(length: int) -> InviteCode:
    plain = normalize_code(generate_plain_code(length))
    code_hash = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return InviteCode(
        plain=plain,
        code_hash=code_hash,
        code_prefix=plain[:6],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate invite codes for Supabase registration.")
    parser.add_argument("--count", type=int, default=1, help="How many invite codes to generate.")
    parser.add_argument("--length", type=int, default=18, help="Invite code length, between 16 and 20.")
    parser.add_argument("--max-uses", type=int, default=1, help="Max uses stored in SQL.")
    parser.add_argument(
        "--expires-at",
        default="null",
        help="Optional SQL timestamp literal, e.g. '2026-05-01T00:00:00+08:00'. Use 'null' to leave empty.",
    )
    return parser.parse_args()


def format_sql_literal(value: str) -> str:
    if value.lower() == "null":
        return "null"
    escaped = value.replace("'", "''")
    return f"'{escaped}'::timestamptz"


def main() -> int:
    args = parse_args()
    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    if not 16 <= args.length <= 20:
        raise SystemExit("--length must be between 16 and 20")
    if args.max_uses < 1:
        raise SystemExit("--max-uses must be >= 1")

    invites = [build_invite_code(args.length) for _ in range(args.count)]
    expires_at_sql = format_sql_literal(args.expires_at)

    print("-- Plain invite codes (send these to users only once)")
    for index, invite in enumerate(invites, start=1):
        print(f"-- {index}. {invite.plain}")

    print("\n-- SQL inserts (store only hashes in Supabase)")
    print("begin;")
    for invite in invites:
        print(
            "insert into public.invite_codes (code_hash, code_prefix, max_uses, expires_at)\n"
            f"values ('{invite.code_hash}', '{invite.code_prefix}', {args.max_uses}, {expires_at_sql});"
        )
    print("commit;")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
