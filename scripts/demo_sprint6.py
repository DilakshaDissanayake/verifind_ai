#!/usr/bin/env python3
"""Sprint 6 demo checklist — prints the §13 path + admin REVIEW smoke.

Does not call live OpenAI / Supabase unless VERIFIND_LIVE_DEMO=1.
Unit-level assertions always run (fusion / decide / observe).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("AUTH_DEV_BYPASS", "true")
os.environ.setdefault("AUTH_DEV_ROLE", "admin")

STEPS = [
    "1. Finder uploads laptop photo with sticker -> public image blurred (vault private)",
    "2. Owner submits LOST nearby -> HIGH match notify (>= 0.80)",
    "3. Owner claims -> answers sticker questions correctly -> PASS -> chat opens",
    "4. Second account guesses vaguely -> FAIL / BLOCK or REVIEW",
    "5. Admin opens REVIEW -> vault original vs public side-by-side -> PASS/BLOCK",
]


def main() -> int:
    from pipelines.fusion import compute_fusion_score
    from pipelines.verification_pipeline import _decide
    from infrastructure.observability import flush, observe

    print("VERIFIND demo path (FINAL_PROJECT_PLAN §13)\n")
    for s in STEPS:
        print(f"  {s}")

    high = compute_fusion_score(
        vision_score=0.9, text_score=0.85, geo_score=0.9, category_score=1.0
    )
    assert high["band"] == "HIGH", high
    assert _decide(0.9) == "PASS"
    assert _decide(0.4) == "REVIEW"
    assert _decide(0.1) == "BLOCK"

    @observe(name="demo_smoke")
    def _ok() -> str:
        return "ok"

    assert _ok() == "ok"
    flush()

    print("\nOK Core fusion / verify / observe checks passed")
    print("   Admin UI:  make ui-install && make ui-dev  -> http://localhost:5173")
    print("   API docs:  make api  -> http://localhost:8000/docs  (admin/reviews)")
    print("   Tests:     make test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
