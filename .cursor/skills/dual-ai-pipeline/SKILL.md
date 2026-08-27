---
name: dual-ai-pipeline
description: Implement or debug the VERIFIND dual multimodal pipeline (vision parallel text embed, sanitization, fusion, Arq). Use when working on process_report_ai, pipelines/*, match scoring, or AI latency budgets.
---

# Dual AI Pipeline

## Flow

```
Report 202 → Arq process_report_ai
  ├─ vision_pipeline (gpt-4o-mini): category, brand, colors, mask boxes
  ├─ text_pipeline: parse + text-embedding-3-small (1536d)
  ├─ sanitization_pipeline: blur masks → public-sanitized; original → private-vault
  ├─ metadata_pipeline: EXIF + pHash + HSV
  └─ dual_executor: asyncio.gather(vision, text) → fusion → persist tags/embeddings
Then compute_matches → notify if HIGH
```

## Rules

1. Vision ∥ text via `asyncio.gather`; do not run them serially unless debugging.
2. Fusion weights from `config/param.yaml` only.
3. Public bucket never receives unblurred unique identifiers.
4. Target ≤8s end-to-end for demo path; API stays ≤200ms (enqueue only).
5. Mock LLM in unit tests; integration tests may use recorded fixtures.

## Verify

- [ ] Mask boxes → blurred public image
- [ ] Vault row stores original path + `hidden_features` JSON
- [ ] Embedding dimension 1536
- [ ] pHash Hamming ≤5 flags near-dup
- [ ] Langfuse spans on vision/text/fusion
