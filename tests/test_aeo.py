"""
Tests for AEOAgent — brand monitoring in AI search answers.
Run: python tests/test_aeo.py
All tests run OFFLINE (no API calls needed).
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))

from agents.aeo_agent import AEOAgent


def make_agent(tmp_dir: Path) -> AEOAgent:
    """Create agent with temp data dir for isolated tests."""
    agent = AEOAgent(bridge=None)
    agent.data_dir = tmp_dir
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return agent


# ──────────────────────────────────────────────────────────
#  1. Brand mention detection
# ──────────────────────────────────────────────────────────

def test_brand_detected():
    """Falcon Herbs mentioned → brand_mentioned=True"""
    agent = AEOAgent()
    text = "I recommend Falcon Herbs for their quality ashwagandha."
    result = agent._analyse(text)
    assert result["brand_mentioned"] is True, "Should detect 'Falcon Herbs'"

def test_brand_falconherbs_no_space():
    """'falconherbs.com' variant detected"""
    agent = AEOAgent()
    text = "Visit falconherbs.com for authentic Ayurvedic products."
    result = agent._analyse(text)
    assert result["brand_mentioned"] is True, "Should detect 'falconherbs'"

def test_brand_not_mentioned():
    """No brand mention → brand_mentioned=False"""
    agent = AEOAgent()
    text = "Patanjali and Himalaya are popular Ayurvedic brands."
    result = agent._analyse(text)
    assert result["brand_mentioned"] is False, "Should NOT detect Falcon Herbs"

def test_brand_case_insensitive():
    """Detection is case-insensitive"""
    agent = AEOAgent()
    text = "FALCON HERBS makes the best triphala."
    result = agent._analyse(text)
    assert result["brand_mentioned"] is True, "Case-insensitive detection failed"


# ──────────────────────────────────────────────────────────
#  2. Competitor detection
# ──────────────────────────────────────────────────────────

def test_competitor_patanjali_detected():
    agent = AEOAgent()
    text = "Patanjali Ashwagandha is widely available."
    result = agent._analyse(text)
    assert "patanjali" in result["competitors_mentioned"]

def test_competitor_multiple():
    agent = AEOAgent()
    text = "Himalaya and Dabur both make good products."
    result = agent._analyse(text)
    assert "himalaya" in result["competitors_mentioned"]
    assert "dabur" in result["competitors_mentioned"]

def test_no_competitor():
    agent = AEOAgent()
    text = "Ayurvedic medicine has ancient roots."
    result = agent._analyse(text)
    assert result["competitors_mentioned"] == []


# ──────────────────────────────────────────────────────────
#  3. Content gap saving & retrieval
# ──────────────────────────────────────────────────────────

def test_save_content_gaps():
    """New gaps saved correctly to JSON"""
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(Path(tmp))
        missed = [
            {"topic": "immunity booster ayurveda",
             "keyword": "ayurvedic immunity India"},
            {"topic": "ashwagandha stress relief",
             "keyword": "ashwagandha brand India"},
        ]
        new_count = agent._save_content_gaps(missed)
        assert new_count == 2, f"Expected 2 new gaps, got {new_count}"

        gaps = agent.get_content_gaps()
        keywords = [g["keyword"] for g in gaps]
        assert "ayurvedic immunity India" in keywords
        assert "ashwagandha brand India" in keywords

def test_no_duplicate_gaps():
    """Same keyword not added twice"""
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(Path(tmp))
        missed = [{"topic": "immunity", "keyword": "ayurvedic immunity India"}]

        agent._save_content_gaps(missed)
        new_count = agent._save_content_gaps(missed)  # Second call
        assert new_count == 0, "Duplicate gap should not be added"

        gaps = agent.get_content_gaps()
        assert len(gaps) == 1, "Should have exactly 1 gap, not 2"

def test_mark_gap_used():
    """mark_gap_used sets used=True for correct keyword"""
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(Path(tmp))
        missed = [{"topic": "tulsi benefits", "keyword": "tulsi supplement India"}]
        agent._save_content_gaps(missed)

        agent.mark_gap_used("tulsi supplement India")
        gaps = agent.get_content_gaps()
        # get_content_gaps filters out used=True entries
        assert all(g["keyword"] != "tulsi supplement India" for g in gaps), \
            "Used gap should not appear in get_content_gaps()"


# ──────────────────────────────────────────────────────────
#  4. Report formatting
# ──────────────────────────────────────────────────────────

def test_report_format_new_scan():
    """Report generated correctly for first-ever scan"""
    agent = AEOAgent()
    data = {
        "scan_month":        "2026-02",
        "brand_mentions":    3,
        "api_answered":      10,
        "brand_score":       30,
        "missed_topics": [
            {"topic": "immunity booster ayurveda",
             "keyword": "ayurvedic immunity India"},
        ],
        "competitor_summary": {"patanjali": 5, "himalaya": 3},
        "trend": {"direction": "new", "change": 0},
    }
    report = agent._format_whatsapp_report(data)

    assert "FALCON HERBS" in report
    assert "30%" in report
    assert "3/10" in report
    assert "patanjali" in report.lower()
    assert "immunity" in report.lower()
    print("[PASS] Report format — new scan")

def test_report_trend_up():
    """Up-trend shown correctly"""
    agent = AEOAgent()
    data = {
        "scan_month": "2026-02",
        "brand_mentions": 15,
        "api_answered": 20,
        "brand_score": 75,
        "missed_topics": [],
        "competitor_summary": {},
        "trend": {"direction": "up", "change": 20},
    }
    report = agent._format_whatsapp_report(data)
    assert "⬆️" in report or "up" in report.lower()
    assert "75%" in report
    print("[PASS] Report format — trend up")

def test_report_no_api():
    """No-scan message when no files exist"""
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(Path(tmp))
        report = agent.get_latest_report()
        assert "No scans" in report or "aeo scan" in report.lower()
        print("[PASS] No-scan status message")


# ──────────────────────────────────────────────────────────
#  5. Question bank sanity checks
# ──────────────────────────────────────────────────────────

def test_questions_have_required_keys():
    """All questions have 'q', 'topic', 'keyword'"""
    agent = AEOAgent()
    for i, q in enumerate(agent.QUESTIONS):
        for key in ("q", "topic", "keyword"):
            assert key in q, f"Question {i} missing '{key}': {q}"
    print(f"[PASS] All {len(agent.QUESTIONS)} questions have required keys")

def test_questions_count():
    """At least 20 questions in bank"""
    agent = AEOAgent()
    assert len(agent.QUESTIONS) >= 20, \
        f"Expected ≥20 questions, got {len(agent.QUESTIONS)}"
    print(f"[PASS] Question bank size: {len(agent.QUESTIONS)}")


# ──────────────────────────────────────────────────────────
#  6. Trend tracking
# ──────────────────────────────────────────────────────────

def test_trend_first_scan():
    """First scan returns direction='new'"""
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(Path(tmp))
        trend = agent._get_trend(50)
        assert trend["direction"] == "new"
        print("[PASS] First scan trend = 'new'")

def test_trend_up():
    """Score improved → direction='up'"""
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(Path(tmp))
        # Write a fake previous scan
        prev = {"brand_score": 30}
        (agent.data_dir / "scan_2026-01.json").write_text(
            json.dumps(prev), encoding="utf-8"
        )
        # Write current scan
        cur = {"brand_score": 55}
        (agent.data_dir / "scan_2026-02.json").write_text(
            json.dumps(cur), encoding="utf-8"
        )
        trend = agent._get_trend(55)
        assert trend["direction"] == "up"
        assert trend["change"] == 25
        print("[PASS] Trend up detected correctly")


# ──────────────────────────────────────────────────────────
#  RUN ALL
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # Brand detection
        test_brand_detected,
        test_brand_falconherbs_no_space,
        test_brand_not_mentioned,
        test_brand_case_insensitive,
        # Competitor detection
        test_competitor_patanjali_detected,
        test_competitor_multiple,
        test_no_competitor,
        # Content gaps
        test_save_content_gaps,
        test_no_duplicate_gaps,
        test_mark_gap_used,
        # Reports
        test_report_format_new_scan,
        test_report_trend_up,
        test_report_no_api,
        # Questions
        test_questions_have_required_keys,
        test_questions_count,
        # Trend
        test_trend_first_scan,
        test_trend_up,
    ]

    passed = 0
    failed = 0
    print("=" * 55)
    print("AEO AGENT — TEST SUITE")
    print("=" * 55)

    for test_fn in tests:
        try:
            test_fn()
            print(f"[PASS] {test_fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_fn.__name__}: {e}")
            failed += 1

    print("=" * 55)
    print(f"RESULT: {passed}/{passed+failed} passed")
    if failed == 0:
        print("ALL PASS - OK")
    else:
        print(f"{failed} FAILED")
    print("=" * 55)
