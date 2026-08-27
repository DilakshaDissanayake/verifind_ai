---
name: zero-fraud-shield
description: Implement or review the 4-layer Zero-Fraud Shield (vault, metadata forensics, adversarial interrogation, behavioral risk). Use when building claim verify, fraud scoring, admin REVIEW, or sanitization/vault APIs.
---

# Zero-Fraud Shield

## Layers

| Layer | Module | Must |
|---|---|---|
| L1 Vault + sanitize | `sanitization_pipeline` | Blur unique IDs; vault private only |
| L2 Metadata | `metadata_pipeline` | EXIF, pHash, HSV; near-dup block |
| L3 Interrogation | `verification_pipeline` | Qs from vault features; semantic score |
| L4 Behavioral | `fraud_pipeline` | Velocity, fail cooldown, device/geo flags |

## Decisions

- Risk `< 0.3` → PASS → anonymous chat
- `0.3–0.7` → REVIEW → admin queue (vault vs public)
- `≥ 0.7` → BLOCK → flag + trust penalty
- Claims ≤3 / 24h; 3 fails → 24h lockout

## Hard invariants

1. Claimant UI never sees vault originals or hidden feature answers.
2. Admin REVIEW may see side-by-side; audit-log access.
3. Chat room provisioned only after PASS.
4. Never short-circuit: public feed must never receive vault originals.

## Demo path

Finder photo with sticker → blurred public → owner match → claim Qs → PASS chat; vague guess → FAIL/BLOCK/REVIEW.
