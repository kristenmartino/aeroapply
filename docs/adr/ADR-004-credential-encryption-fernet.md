# ADR-004: Encrypt portal credentials at rest with Fernet

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Architecture, Security
- **Related:** `docs/PROJECT_BRIEF.md` §4, §7, §13; ADR-002

## Context

To apply through DOM portals, AeroApply creates and reuses per-domain accounts and
must store their passwords. These are high-value secrets: they must be encrypted at
rest, never logged, never returned to the UI in plaintext, and the encryption key
must differ between dev and prod and be rotatable without downtime.

## Decision

We will encrypt the `portal_credentials` password column with **Fernet** (from
`cryptography`): **AES-128-CBC** for confidentiality plus **HMAC-SHA256** for
authenticated integrity, with a timestamped token. The key comes from
`AEROAPPLY_FERNET_KEY` in **dev** and a **KMS-backed key** in **prod**. Key rotation
uses **MultiFernet** — decrypt under any historical key, always encrypt under the
newest. Passwords are generated with `secrets`.

## Alternatives considered

- **Raw AES-GCM via `cryptography` primitives** — fine algorithm, but we would
  hand-roll nonce management, key framing, and token format; Fernet packages this
  correctly and is hard to misuse.
- **Plaintext / DB-level (TDE) only** — fails the "never in plaintext to UI/logs"
  and app-layer-key requirements; TDE protects disks, not application reads.
- **Full external secrets manager per credential** — heavyweight for per-portal
  rows; we still want the encrypted value co-located in Postgres for atomic reads.

## Consequences

- **Positive:** authenticated encryption (tampering detected); clean dev→prod key
  story; zero-downtime rotation via MultiFernet; ciphertext lives with the row.
- **Negative:** key custody is now critical — losing the key loses all credentials;
  AES-128 (not 256), which is sufficient here but worth noting.
- **Follow-ups:** wire prod key retrieval to KMS; document the rotation runbook;
  never log decrypted values.
