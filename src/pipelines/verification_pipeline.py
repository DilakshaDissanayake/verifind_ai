"""Verification pipeline — Sprint 5 (Zero-Fraud L3).

Flow:
  1. Fetch vault hidden_features for the matched report image.
  2. Call GPT-4o to generate N adversarial questions from those features.
  3. Claimant submits answers; score each semantically with GPT-4o.
  4. Overall score → PASS / REVIEW / BLOCK decision.

Invariants (hard):
  - Questions are generated from vault; answers are NEVER returned to client.
  - Scoring uses the stronger verify model (gpt-4o by default).
  - Decision thresholds from config/param.yaml.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from loguru import logger

from infrastructure.config import FRAUD
from infrastructure.observability import observe, update_current_observation

_QUESTION_COUNT = 3
_PASS_THRESHOLD = 0.6
_BLOCK_THRESHOLD = 0.3


@observe(name="generate_adversarial_questions")
async def generate_adversarial_questions(
    *,
    hidden_features: dict[str, Any],
    category: Optional[str],
    report_id: str,
    n: int = _QUESTION_COUNT,
) -> list[dict[str, Any]]:
    """Generate N adversarial ownership-proof questions from vault features.

    Returns list of {question_id, question, feature_key, expected_hint}.
    The expected_hint is stored server-side only — never sent to client.
    """
    start = time.monotonic()
    features_text = json.dumps(hidden_features, indent=2)

    prompt = f"""You are verifying whether a claimant is the true owner of a lost {category or 'item'}.

Hidden features extracted from the original item image (NEVER shown to public):
{features_text}

Generate exactly {n} short, specific questions that only the true owner could answer correctly.
Each question must probe a distinct visible detail (unique marks, colors, model numbers, stickers, damage, etc.).
Do NOT ask about GPS, time, or personal identity.

Respond with a JSON array of objects:
[
  {{
    "question_id": "q1",
    "question": "What is written on the sticker near the charging port?",
    "feature_key": "sticker_text",
    "expected_hint": "CS101"
  }}
]

Return ONLY the JSON array, no prose."""

    questions = await _call_llm_for_questions(prompt, n)

    latency_s = round(time.monotonic() - start, 3)
    update_current_observation(
        metadata={"report_id": report_id, "n": len(questions), "latency_s": latency_s}
    )
    logger.info(
        "generate_questions report_id={} n={} latency_s={}",
        report_id,
        len(questions),
        latency_s,
    )
    return questions


async def _call_llm_for_questions(prompt: str, n: int) -> list[dict[str, Any]]:
    """Call verify LLM with multi-provider failover; stub questions on total failure."""
    try:
        from infrastructure.llm.llm_provider import chat_completions_with_failover

        out = await chat_completions_with_failover(
            role="verify",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=800,
        )
        raw = out.get("content") or "[]"
        parsed = json.loads(raw)
        questions = _normalize_question_list(parsed, n)
        if not questions:
            raise ValueError(f"unusable LLM questions payload: {type(parsed)}")
        return questions
    except Exception as exc:
        logger.warning("generate_questions LLM failed: {} — using stub", exc)
        return _stub_questions(n)


def _normalize_question_list(parsed: Any, n: int) -> list[dict[str, Any]]:
    """Coerce LLM JSON into [{question_id, question, feature_key, expected_hint}].

    Guards against string payloads (list('I...') character-splitting) which caused
    AttributeError: 'str' object has no attribute 'get' in start_claim.
    """
    # Nested JSON string
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except json.JSONDecodeError:
            text = parsed.strip()
            if len(text) > 8:
                return [
                    {
                        "question_id": "q1",
                        "question": text,
                        "feature_key": "feature_1",
                        "expected_hint": "",
                    }
                ]
            return []

    if isinstance(parsed, dict):
        if isinstance(parsed.get("questions"), list):
            parsed = parsed["questions"]
        elif "question" in parsed:
            parsed = [parsed]
        else:
            vals = list(parsed.values())
            if vals and all(isinstance(v, dict) for v in vals):
                parsed = vals
            elif vals and isinstance(vals[0], list):
                parsed = vals[0]
            else:
                return []

    if not isinstance(parsed, list):
        return []

    out: list[dict[str, Any]] = []
    for i, item in enumerate(parsed):
        if len(out) >= n:
            break
        if isinstance(item, dict):
            qtext = str(item.get("question") or item.get("q") or "").strip()
            if not qtext:
                continue
            out.append(
                {
                    "question_id": str(item.get("question_id") or f"q{len(out)+1}"),
                    "question": qtext,
                    "feature_key": str(item.get("feature_key") or f"feature_{len(out)+1}"),
                    "expected_hint": str(item.get("expected_hint") or ""),
                }
            )
        elif isinstance(item, str) and len(item.strip()) > 8:
            # Full question string — never treat single chars as questions
            out.append(
                {
                    "question_id": f"q{len(out)+1}",
                    "question": item.strip(),
                    "feature_key": f"feature_{len(out)+1}",
                    "expected_hint": "",
                }
            )
    return out


def _stub_questions(n: int) -> list[dict[str, Any]]:
    stubs = [
        {
            "question_id": f"q{i+1}",
            "question": f"Describe unique feature #{i+1} of your item.",
            "feature_key": f"feature_{i+1}",
            "expected_hint": "",
        }
        for i in range(n)
    ]
    return stubs[:n]


@observe(name="score_answers")
async def score_answers(
    *,
    questions: list[dict[str, Any]],
    answers: list[str],
    report_id: str,
) -> dict[str, Any]:
    """Semantically score each answer against its expected_hint.

    Returns:
        {
          semantic_scores: [0.0–1.0, ...],
          overall_score: float,
          decision: 'PASS' | 'REVIEW' | 'BLOCK',
          latency_s: float,
        }
    """
    start = time.monotonic()
    if len(answers) != len(questions):
        logger.warning(
            "score_answers: answer count mismatch — questions={} answers={} report_id={}",
            len(questions),
            len(answers),
            report_id,
        )

    semantic_scores: list[float] = []
    for i, (q, ans) in enumerate(zip(questions, answers)):
        hint = q.get("expected_hint", "")
        score = await _score_single_answer(
            question=q.get("question", ""),
            answer=ans,
            expected_hint=hint,
        )
        semantic_scores.append(score)

    overall = sum(semantic_scores) / max(len(semantic_scores), 1)
    decision = _decide(overall)

    latency_s = round(time.monotonic() - start, 3)
    logger.info(
        "score_answers report_id={} overall={:.3f} decision={} latency_s={}",
        report_id,
        overall,
        decision,
        latency_s,
    )
    return {
        "semantic_scores": semantic_scores,
        "overall_score": round(overall, 4),
        "decision": decision,
        "latency_s": latency_s,
    }


async def _score_single_answer(
    *,
    question: str,
    answer: str,
    expected_hint: str,
) -> float:
    """Score one answer [0.0–1.0]. Falls back to keyword match on LLM error."""
    if not answer or not answer.strip():
        return 0.0

    if not expected_hint:
        # No ground truth — give partial credit for non-empty answer
        return 0.4

    prompt = f"""Score how well this answer proves ownership of an item.

Question: {question}
Correct feature hint (ground truth, private): {expected_hint}
Claimant answer: {answer}

Score from 0.0 (completely wrong) to 1.0 (exact match / clearly correct).
Reply with ONLY a float like 0.85"""

    try:
        from infrastructure.llm.llm_provider import chat_completions_with_failover

        out = await chat_completions_with_failover(
            role="verify",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
        )
        raw = (out.get("content") or "0.0").strip()
        return max(0.0, min(1.0, float(raw)))
    except Exception as exc:
        logger.warning("_score_single_answer LLM failed: {} — keyword fallback", exc)
        # Keyword overlap fallback (local degradation when all providers fail)
        answer_words = set(answer.lower().split())
        hint_words = set(expected_hint.lower().split())
        if not hint_words:
            return 0.3
        overlap = len(answer_words & hint_words) / len(hint_words)
        return round(min(1.0, overlap), 4)


def _decide(overall_score: float) -> str:
    """Map overall score to PASS / REVIEW / BLOCK."""
    pass_t = float(FRAUD.get("risk_pass", 0.3))
    review_t = float(FRAUD.get("risk_review", 0.7))
    # Higher score = better answer = lower fraud risk
    if overall_score >= pass_t + 0.3:   # ≥ 0.60 → PASS
        return "PASS"
    if overall_score >= pass_t:         # ≥ 0.30 → REVIEW
        return "REVIEW"
    return "BLOCK"                      # < 0.30 → BLOCK


async def fetch_vault_features(report_id: str) -> dict[str, Any]:
    """Fetch hidden_features JSON from image_vaults for the primary image."""
    from sqlalchemy import text

    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT iv.hidden_features, at.category, at.brand, at.colors, at.attributes
                FROM image_vaults iv
                JOIN report_images ri ON ri.id = iv.report_image_id
                LEFT JOIN ai_tags at ON at.report_id = ri.report_id
                WHERE ri.report_id = :rid AND ri.is_primary = TRUE
                ORDER BY iv.created_at DESC
                LIMIT 1
                """
            ),
            {"rid": str(report_id)},
        ).mappings().first()
    finally:
        session.close()

    if row is None:
        return {}

    features: dict[str, Any] = dict(row.get("hidden_features") or {})
    # Enrich with AI tags if vault features are sparse
    if row.get("brand"):
        features["brand"] = row["brand"]
    if row.get("colors"):
        features["colors"] = list(row["colors"])
    if row.get("attributes"):
        features.update(dict(row["attributes"]))
    return features
