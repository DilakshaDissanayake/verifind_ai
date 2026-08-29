"""Verification pipeline — Sprint 5 (Zero-Fraud L3).

Flow:
  1. Fetch vault hidden_features for the matched report image.
  2. Call GPT-4o to generate N adversarial questions from those features.
  3. Claimant submits answers; score each semantically with GPT-4o.
  4. Overall score → PASS / REVIEW / BLOCK decision.

Invariants (hard):
  - Questions are generated from vault; answers are NEVER returned to client.
  - Scoring uses the stronger verify model (gpt-4o by default).
  - Decision thresholds from config/param.yaml verify.pass_threshold / block_threshold.
  - Empty expected_hint must NOT invent a fake 0.4 semantic score.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from loguru import logger

from infrastructure.config import VERIFY_BLOCK, VERIFY_PASS
from infrastructure.observability import observe, update_current_observation

_QUESTION_COUNT = 3
_SKIP_FEATURE_KEYS = {
    "bucket",
    "pending_sanitize",
    "path",
    "storage_path",
    "public_path",
    "content_type",
}


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
    features = dict(hidden_features or {})
    features_text = json.dumps(features, indent=2, default=str)

    prompt = f"""You are verifying whether a claimant is the true owner of a lost {category or 'item'}.

Hidden features extracted from the original item image (NEVER shown to public):
{features_text}

Generate exactly {n} short, specific questions that only the true owner could answer correctly.
Each question must probe a distinct visible detail (unique marks, colors, model numbers, stickers, damage, etc.).
Do NOT ask about GPS, time, or personal identity.
Every object MUST include a non-empty expected_hint taken from the hidden features above.

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
    questions = _ensure_hints_from_features(questions, features, n)

    if not _has_any_hint(questions):
        feature_qs = _questions_from_features(features, n)
        if feature_qs:
            logger.warning(
                "generate_questions report_id={} — LLM/stub lacked hints; using feature-backed questions n={}",
                report_id,
                len(feature_qs),
            )
            questions = feature_qs
        else:
            logger.error(
                "generate_questions report_id={} — no vault/ai features for hints; "
                "using unscored stubs (will force REVIEW)",
                report_id,
            )
            questions = _stub_questions(n)

    latency_s = round(time.monotonic() - start, 3)
    update_current_observation(
        metadata={
            "report_id": report_id,
            "n": len(questions),
            "latency_s": latency_s,
            "hints_present": _has_any_hint(questions),
        }
    )
    logger.info(
        "generate_questions report_id={} n={} hints={} latency_s={}",
        report_id,
        len(questions),
        _has_any_hint(questions),
        latency_s,
    )
    return questions


async def _call_llm_for_questions(prompt: str, n: int) -> list[dict[str, Any]]:
    """Call verify LLM with multi-provider failover; empty list on total failure."""
    try:
        from infrastructure.llm.llm_provider import chat_completions_with_failover

        out = await chat_completions_with_failover(
            role="verify",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=800,
        )
        raw = out.get("content") or "[]"
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        questions = _normalize_question_list(parsed, n)
        if not questions:
            raise ValueError(f"unusable LLM questions payload: {type(parsed)}")
        return questions
    except Exception as exc:
        logger.warning("generate_questions LLM failed: {} — feature/stub fallback", exc)
        return []


def _normalize_question_list(parsed: Any, n: int) -> list[dict[str, Any]]:
    """Coerce LLM JSON into [{question_id, question, feature_key, expected_hint}].

    Guards against string payloads (list('I...') character-splitting) which caused
    AttributeError: 'str' object has no attribute 'get' in start_claim.
    """
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
                    "expected_hint": str(item.get("expected_hint") or "").strip(),
                }
            )
        elif isinstance(item, str) and len(item.strip()) > 8:
            out.append(
                {
                    "question_id": f"q{len(out)+1}",
                    "question": item.strip(),
                    "feature_key": f"feature_{len(out)+1}",
                    "expected_hint": "",
                }
            )
    return out


def _feature_pairs(features: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten vault/ai_tags features into (key, hint) pairs suitable for Q&A."""
    pairs: list[tuple[str, str]] = []
    for key, value in (features or {}).items():
        k = str(key).strip()
        if not k or k.lower() in _SKIP_FEATURE_KEYS:
            continue
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (list, tuple)):
            hint = ", ".join(str(x) for x in value if x is not None and str(x).strip())
        elif isinstance(value, dict):
            hint = ", ".join(
                f"{sk}: {sv}" for sk, sv in value.items() if sv is not None and str(sv).strip()
            )
        else:
            hint = str(value).strip()
        if len(hint) < 2:
            continue
        pairs.append((k, hint[:200]))
    return pairs


def _questions_from_features(features: dict[str, Any], n: int) -> list[dict[str, Any]]:
    """Build ownership questions directly from vault / AI tag features."""
    pairs = _feature_pairs(features)
    if not pairs:
        return []
    out: list[dict[str, Any]] = []
    for i, (key, hint) in enumerate(pairs[:n]):
        label = key.replace("_", " ")
        out.append(
            {
                "question_id": f"q{i+1}",
                "question": f"What is the {label} of your item? (unique detail only you would know)",
                "feature_key": key,
                "expected_hint": hint,
            }
        )
    return out


def _ensure_hints_from_features(
    questions: list[dict[str, Any]],
    features: dict[str, Any],
    n: int,
) -> list[dict[str, Any]]:
    """Fill empty expected_hint from matching feature_key or unused feature pairs."""
    if not questions:
        return questions
    pairs = _feature_pairs(features)
    by_key = {k.lower(): v for k, v in pairs}
    unused = list(pairs)
    filled: list[dict[str, Any]] = []
    for q in questions[:n]:
        item = dict(q)
        hint = str(item.get("expected_hint") or "").strip()
        fkey = str(item.get("feature_key") or "").strip().lower()
        if not hint and fkey and fkey in by_key:
            hint = by_key[fkey]
        if not hint and unused:
            key, hint = unused.pop(0)
            item["feature_key"] = item.get("feature_key") or key
        item["expected_hint"] = hint
        filled.append(item)
    return filled


def _has_any_hint(questions: list[dict[str, Any]]) -> bool:
    return any(str(q.get("expected_hint") or "").strip() for q in questions)


def _all_hints_empty(questions: list[dict[str, Any]]) -> bool:
    if not questions:
        return True
    return not _has_any_hint(questions)


def _stub_questions(n: int) -> list[dict[str, Any]]:
    """Last-resort placeholders — empty hints; scoring must force REVIEW."""
    stubs = [
        {
            "question_id": f"q{i+1}",
            "question": f"Describe unique feature #{i+1} of your item.",
            "feature_key": f"feature_{i+1}",
            "expected_hint": "",
            "unscored": True,
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
          semantic_scores: [0.0–1.0 | None, ...],
          overall_score: float | None,
          decision: 'PASS' | 'REVIEW' | 'BLOCK',
          unscored: bool,
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

    if _all_hints_empty(questions):
        latency_s = round(time.monotonic() - start, 3)
        logger.error(
            "score_answers report_id={} — empty expected_hint on all questions; "
            "forcing REVIEW (unscored). Verification questions unavailable.",
            report_id,
        )
        return {
            "semantic_scores": [None] * max(len(questions), 1),
            "overall_score": None,
            "decision": "REVIEW",
            "unscored": True,
            "latency_s": latency_s,
        }

    semantic_scores: list[Optional[float]] = []
    for q, ans in zip(questions, answers):
        hint = str(q.get("expected_hint") or "").strip()
        if not hint:
            semantic_scores.append(None)
            continue
        score = await _score_single_answer(
            question=str(q.get("question") or ""),
            answer=ans,
            expected_hint=hint,
        )
        semantic_scores.append(score)

    scored = [s for s in semantic_scores if s is not None]
    if not scored:
        latency_s = round(time.monotonic() - start, 3)
        logger.error(
            "score_answers report_id={} — no scorable answers; forcing REVIEW",
            report_id,
        )
        return {
            "semantic_scores": semantic_scores,
            "overall_score": None,
            "decision": "REVIEW",
            "unscored": True,
            "latency_s": latency_s,
        }

    overall = sum(scored) / len(scored)
    decision = _decide(overall)
    if any(s is None for s in semantic_scores) and decision == "PASS":
        decision = "REVIEW"

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
        "unscored": False,
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

    hint = (expected_hint or "").strip()
    if not hint:
        raise ValueError("expected_hint required for semantic scoring")

    prompt = f"""Score how well this answer proves ownership of an item.

Question: {question}
Correct feature hint (ground truth, private): {hint}
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
        token = raw.split()[0].rstrip(",;")
        for ch in token:
            if ch.isdigit() or ch in ".-":
                start_i = token.index(ch)
                token = token[start_i:]
                break
        return max(0.0, min(1.0, float(token)))
    except Exception as exc:
        logger.warning("_score_single_answer LLM failed: {} — keyword fallback", exc)
        answer_words = set(answer.lower().split())
        hint_words = set(hint.lower().split())
        if not hint_words:
            return 0.0
        overlap = len(answer_words & hint_words) / len(hint_words)
        return round(min(1.0, overlap), 4)


def _decide(overall_score: float) -> str:
    """Map overall answer score to PASS / REVIEW / BLOCK via param.yaml verify.*."""
    pass_t = float(VERIFY_PASS)
    block_t = float(VERIFY_BLOCK)
    if overall_score >= pass_t:
        return "PASS"
    if overall_score >= block_t:
        return "REVIEW"
    return "BLOCK"


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

        if row is None:
            row = session.execute(
                text(
                    """
                    SELECT NULL::jsonb AS hidden_features,
                           at.category, at.brand, at.colors, at.attributes
                    FROM ai_tags at
                    WHERE at.report_id = :rid
                    ORDER BY at.created_at DESC
                    LIMIT 1
                    """
                ),
                {"rid": str(report_id)},
            ).mappings().first()
    finally:
        session.close()

    if row is None:
        return {}

    features: dict[str, Any] = {}
    raw_hf = row.get("hidden_features")
    if isinstance(raw_hf, dict):
        features.update(raw_hf)
    elif isinstance(raw_hf, str) and raw_hf.strip():
        try:
            parsed = json.loads(raw_hf)
            if isinstance(parsed, dict):
                features.update(parsed)
        except json.JSONDecodeError:
            pass

    if row.get("category"):
        features.setdefault("category", row["category"])
    if row.get("brand"):
        features["brand"] = row["brand"]
    if row.get("colors"):
        features["colors"] = list(row["colors"])
    if row.get("attributes"):
        attrs = row["attributes"]
        if isinstance(attrs, dict):
            features.update(attrs)
        elif isinstance(attrs, str):
            try:
                parsed_attrs = json.loads(attrs)
                if isinstance(parsed_attrs, dict):
                    features.update(parsed_attrs)
            except json.JSONDecodeError:
                pass
    return features
