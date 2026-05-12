# A-15 Stack Note

`nikos/a-15` is intentionally stacked because `origin/main` does not yet contain A-13 or A-14 after the latest fetch.

Dependency branches included below A-15:

- A-13: `origin/nikos/a-13` at `2b824af` (`2ff9397`, `2b824af`)
- A-14: `origin/nikos/a-14` at `80a51d7` (`16cdc94`, `80a51d7`)

Merge order:

1. Merge A-13.
2. Merge A-14.
3. Merge A-15.

A-15-specific review base:

- Use `cb9078e..HEAD` for the A-15-only hardening diff on this branch.
- Do not review `nikos/a-15` as an independent PR against `origin/main` until A-13 and A-14 are merged there.
