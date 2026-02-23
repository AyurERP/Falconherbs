"""
Falcon Agency — AEO (Answer Engine Optimization) Agent
=======================================================
Monitors whether Falcon Herbs appears in AI-generated answers
from Perplexity and OpenAI.

NOT an SEO injection tool — this is BRAND MONITORING.
Like Google Alerts, but for AI search engines.

How it works:
  1. Queries 25 Ayurveda-related questions to Perplexity/OpenAI
  2. Checks if "Falcon Herbs" is mentioned in the answer
  3. Tracks competitor mentions (Patanjali, Himalaya, etc.)
  4. Saves missed topics as content gaps
  5. ContentWorkflow picks up those gaps automatically (closed loop)
  6. Reports monthly score card to WhatsApp

APIs needed (.env):
  PERPLEXITY_API_KEY  — perplexity.ai (free tier: 5 req/min)
  OPENAI_API_KEY      — fallback if Perplexity unavailable
"""

import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class AEOAgent:
    """
    Answer Engine Optimization monitor for Falcon Herbs.
    Runs monthly, saves results to data/aeo/,
    auto-feeds content gaps into ContentWorkflow queue.
    """

    BRAND_VARIANTS = ["falcon herbs", "falconherbs", "falcon herb"]

    COMPETITORS = [
        "patanjali", "himalaya", "dabur", "baidyanath",
        "zandu", "hamdard", "charak", "kerala ayurveda",
        "kama ayurveda", "forest essentials", "biotique",
    ]

    # 25 questions covering all product categories
    QUESTIONS: List[Dict] = [
        # ── Immunity ──────────────────────────────────────
        {
            "q": "best ayurvedic brand for immunity in India",
            "topic": "immunity booster ayurveda",
            "keyword": "best ayurvedic brand immunity India",
        },
        {
            "q": "which ayurvedic supplement helps boost immunity naturally",
            "topic": "immunity booster ayurveda",
            "keyword": "ayurvedic immunity supplement natural",
        },
        {
            "q": "giloy supplement for immunity India best brand",
            "topic": "giloy benefits",
            "keyword": "giloy supplement India",
        },
        {
            "q": "chyawanprash best brand India for immunity",
            "topic": "chyawanprash",
            "keyword": "chyawanprash brand India",
        },
        # ── Stress & Sleep ───────────────────────────────
        {
            "q": "best ashwagandha supplement brand India",
            "topic": "ashwagandha stress relief",
            "keyword": "best ashwagandha brand India",
        },
        {
            "q": "ayurvedic herbs for stress relief India trusted brand",
            "topic": "ashwagandha stress relief",
            "keyword": "ayurvedic stress relief herbs India",
        },
        {
            "q": "shilajit supplement trusted brand India",
            "topic": "shilajit energy",
            "keyword": "shilajit brand India trusted",
        },
        # ── Digestion ─────────────────────────────────────
        {
            "q": "best triphala brand in India for digestion",
            "topic": "triphala gut health",
            "keyword": "best triphala brand India",
        },
        {
            "q": "ayurvedic supplement for gut health India",
            "topic": "triphala gut health",
            "keyword": "ayurvedic gut health supplement",
        },
        # ── Hair Care ──────────────────────────────────────
        {
            "q": "best ayurvedic hair oil brand India bhringraj",
            "topic": "natural hair care herbs",
            "keyword": "ayurvedic hair oil brand India",
        },
        {
            "q": "amla supplement for hair and immunity India brand",
            "topic": "natural hair care herbs",
            "keyword": "amla supplement India brand",
        },
        # ── Skin Care ──────────────────────────────────────
        {
            "q": "neem products for skin India best ayurvedic brand",
            "topic": "ayurvedic skincare",
            "keyword": "neem skin products India",
        },
        {
            "q": "ayurvedic skincare brand India trusted online",
            "topic": "ayurvedic skincare",
            "keyword": "ayurvedic skincare brand India online",
        },
        # ── Women's Health ─────────────────────────────────
        {
            "q": "shatavari supplement for women India best brand",
            "topic": "shatavari womens health",
            "keyword": "shatavari supplement India women",
        },
        # ── Memory & Brain ──────────────────────────────────
        {
            "q": "brahmi supplement for memory focus India",
            "topic": "brahmi memory",
            "keyword": "brahmi memory supplement India",
        },
        # ── Joint & Pain ──────────────────────────────────
        {
            "q": "ayurvedic joint pain relief herbs supplement India",
            "topic": "joint pain herbal remedy",
            "keyword": "ayurvedic joint pain supplement",
        },
        # ── Weight Management ──────────────────────────────
        {
            "q": "ayurvedic weight management herbs supplement India",
            "topic": "ayurvedic weight loss",
            "keyword": "ayurvedic weight management India",
        },
        # ── Superfoods / Nutrition ─────────────────────────
        {
            "q": "moringa supplement India best quality brand",
            "topic": "moringa superfood",
            "keyword": "moringa supplement India",
        },
        {
            "q": "tulsi supplement benefits brand India",
            "topic": "tulsi benefits",
            "keyword": "tulsi supplement India",
        },
        # ── General Brand Discovery ─────────────────────────
        {
            "q": "trusted ayurvedic herbal supplement brand India online shop",
            "topic": "brand discovery",
            "keyword": "trusted ayurvedic brand India online",
        },
        {
            "q": "quality ayurvedic products online India where to buy",
            "topic": "brand discovery",
            "keyword": "quality ayurvedic products online",
        },
        {
            "q": "best herbal supplement store India online",
            "topic": "brand discovery",
            "keyword": "herbal supplement store India",
        },
        # ── Diabetes / Blood Sugar ────────────────────────
        {
            "q": "ayurvedic herbs for healthy blood sugar management India",
            "topic": "ayurvedic diabetes management",
            "keyword": "ayurvedic blood sugar herbs India",
        },
        # ── Liver & Detox ─────────────────────────────────
        {
            "q": "neem detox ayurvedic supplement India brand",
            "topic": "neem detox",
            "keyword": "neem detox supplement India",
        },
        # ── Overall wellness ─────────────────────────────
        {
            "q": "best overall ayurvedic wellness brand India 2024",
            "topic": "brand discovery",
            "keyword": "best ayurvedic wellness brand India",
        },
    ]

    def __init__(self, bridge=None):
        self.bridge = bridge
        self.data_dir = Path("data/aeo")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────
    #  API QUERY LAYER
    # ─────────────────────────────────────────────────────

    def _query_perplexity(self, question: str) -> str:
        """Query Perplexity sonar model. Returns answer text or ''."""
        api_key = os.getenv("PERPLEXITY_API_KEY", "")
        if not api_key:
            return ""
        try:
            r = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": question}],
                    "max_tokens": 300,
                },
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            return ""
        except Exception:
            return ""

    def _query_openai(self, question: str) -> str:
        """Query OpenAI gpt-3.5-turbo as fallback. Returns answer text or ''."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": question}],
                    "max_tokens": 300,
                },
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            return ""
        except Exception:
            return ""

    def _query_nvidia(self, question: str) -> str:
        """Query NVIDIA API (llama/deepseek) — uses existing project key."""
        api_key = os.getenv("NVIDIA_API_KEY", "")
        if not api_key:
            return ""
        try:
            # Try the project's existing AI client
            if self.bridge:
                ai = self.bridge.tools.get("ai_client")
                if ai and hasattr(ai, "generate"):
                    prompt = (
                        "Answer this question in 2-3 sentences, "
                        "naming specific brands if relevant: "
                        + question
                    )
                    return ai.generate(prompt) or ""
            return ""
        except Exception:
            return ""

    def _best_answer(self, question: str) -> tuple:
        """
        Try Perplexity → OpenAI → NVIDIA API in order.
        Returns (answer_text, engine_name).
        Respects Perplexity free-tier rate limit (1 req/sec).
        """
        text = self._query_perplexity(question)
        if text:
            time.sleep(1.2)   # Perplexity free tier: ~1 req/sec
            return text, "perplexity"

        text = self._query_openai(question)
        if text:
            return text, "openai"

        text = self._query_nvidia(question)
        if text:
            return text, "nvidia"

        return "", "unavailable"

    # ─────────────────────────────────────────────────────
    #  ANALYSIS
    # ─────────────────────────────────────────────────────

    def _analyse(self, text: str) -> dict:
        """
        Check if Falcon Herbs and/or competitors are in the answer.
        Returns dict with brand_mentioned, competitors_mentioned, snippet.
        """
        lower = text.lower()
        brand_mentioned = any(v in lower for v in self.BRAND_VARIANTS)
        competitors_found = [c for c in self.COMPETITORS if c in lower]
        return {
            "brand_mentioned": brand_mentioned,
            "competitors_mentioned": competitors_found,
            "snippet": text[:350].strip(),
        }

    def _count_competitors(self, results: list) -> dict:
        counts: Dict[str, int] = {}
        for r in results:
            for comp in r.get("competitors_mentioned", []):
                counts[comp] = counts.get(comp, 0) + 1
        return {k: v for k, v in sorted(
            counts.items(), key=lambda x: x[1], reverse=True
        ) if v > 0}

    # ─────────────────────────────────────────────────────
    #  CORE SCAN
    # ─────────────────────────────────────────────────────

    def run_monthly_scan(self, max_questions: int = 25) -> dict:
        """
        Run full AEO scan.
        Queries all questions, saves results + content gaps,
        returns WhatsApp-ready report.
        """
        results = []
        missed: List[Dict] = []
        mentioned_count = 0

        questions = self.QUESTIONS[:max_questions]
        total_q = len(questions)

        print(f"[AEO] Starting scan: {total_q} questions...")

        for i, q_data in enumerate(questions, 1):
            question = q_data["q"]
            topic    = q_data["topic"]
            keyword  = q_data["keyword"]

            print(f"[AEO] {i}/{total_q}: {question[:55]}...")

            answer, engine = self._best_answer(question)

            entry = {
                "question": question,
                "topic":    topic,
                "keyword":  keyword,
                "engine":   engine,
                "brand_mentioned": False,
                "competitors_mentioned": [],
                "snippet": "",
            }

            if answer:
                analysis = self._analyse(answer)
                entry.update(analysis)
                if analysis["brand_mentioned"]:
                    mentioned_count += 1
                else:
                    missed.append({
                        "topic":   topic,
                        "keyword": keyword,
                    })
            else:
                # API unavailable — still mark as gap
                missed.append({"topic": topic, "keyword": keyword})

            results.append(entry)

        # ── Build scan summary ──────────────────────────
        answered = sum(1 for r in results if r["engine"] != "unavailable")

        scan_data = {
            "scan_date":         datetime.now().isoformat(),
            "scan_month":        datetime.now().strftime("%Y-%m"),
            "total_questions":   total_q,
            "api_answered":      answered,
            "brand_mentions":    mentioned_count,
            "brand_score":       round(
                mentioned_count / max(answered, 1) * 100
            ),
            "missed_topics":     missed,
            "competitor_summary": self._count_competitors(results),
            "results":           results,
        }

        # ── Save monthly file ───────────────────────────
        scan_file = self.data_dir / "scan_{}.json".format(
            datetime.now().strftime("%Y-%m")
        )
        scan_file.write_text(
            json.dumps(scan_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[AEO] Saved: {scan_file}")

        # ── Save content gaps for ContentWorkflow ───────
        new_gaps = self._save_content_gaps(missed)
        print(f"[AEO] {new_gaps} new content gaps queued.")

        # ── Trend comparison ────────────────────────────
        scan_data["trend"] = self._get_trend(scan_data["brand_score"])

        return {
            "success": True,
            "data":    scan_data,
            "summary": self._format_whatsapp_report(scan_data),
        }

    # ─────────────────────────────────────────────────────
    #  CONTENT GAP CLOSED LOOP
    # ─────────────────────────────────────────────────────

    def _save_content_gaps(self, missed: list) -> int:
        """
        Persist missed topics to data/aeo/content_gaps.json.
        ContentWorkflow.pick_next_topic() reads this file
        and prioritises these topics over evergreen list.
        Returns number of NEW gaps added.
        """
        gaps_file = self.data_dir / "content_gaps.json"

        existing: List[Dict] = []
        if gaps_file.exists():
            try:
                existing = json.loads(
                    gaps_file.read_text(encoding="utf-8")
                )
            except Exception:
                pass

        existing_keywords = {g["keyword"] for g in existing}

        # Deduplicate by topic too
        seen_topics: set = set()
        new_gaps = []
        for t in missed:
            if (t["keyword"] not in existing_keywords
                    and t["topic"] not in seen_topics):
                seen_topics.add(t["topic"])
                new_gaps.append({
                    "topic":      t["topic"].replace("-", " ").title(),
                    "keyword":    t["keyword"],
                    "source":     "aeo_gap",
                    "added_date": datetime.now().isoformat(),
                    "used":       False,
                })

        gaps_file.write_text(
            json.dumps(existing + new_gaps, indent=2,
                       ensure_ascii=False),
            encoding="utf-8",
        )
        return len(new_gaps)

    def get_content_gaps(self) -> list:
        """Return unused AEO content gaps for ContentWorkflow."""
        gaps_file = self.data_dir / "content_gaps.json"
        if not gaps_file.exists():
            return []
        try:
            gaps = json.loads(gaps_file.read_text(encoding="utf-8"))
            return [g for g in gaps if not g.get("used", False)]
        except Exception:
            return []

    def mark_gap_used(self, keyword: str):
        """Mark a gap as consumed (blog was created for it)."""
        gaps_file = self.data_dir / "content_gaps.json"
        if not gaps_file.exists():
            return
        try:
            gaps = json.loads(gaps_file.read_text(encoding="utf-8"))
            for g in gaps:
                if g.get("keyword") == keyword:
                    g["used"] = True
                    g["used_date"] = datetime.now().isoformat()
            gaps_file.write_text(
                json.dumps(gaps, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ─────────────────────────────────────────────────────
    #  TREND
    # ─────────────────────────────────────────────────────

    def _get_trend(self, current_score: int) -> dict:
        """Compare current score to previous month's scan."""
        scans = sorted(self.data_dir.glob("scan_*.json"), reverse=True)
        if len(scans) < 2:
            return {"direction": "new", "change": 0, "prev_score": None}
        try:
            prev = json.loads(scans[1].read_text(encoding="utf-8"))
            prev_score = prev.get("brand_score", 0)
            change     = current_score - prev_score
            direction  = ("up" if change > 0
                          else "down" if change < 0
                          else "same")
            return {
                "direction":  direction,
                "change":     abs(change),
                "prev_score": prev_score,
            }
        except Exception:
            return {"direction": "new", "change": 0, "prev_score": None}

    # ─────────────────────────────────────────────────────
    #  REPORT FORMATTING
    # ─────────────────────────────────────────────────────

    def _format_whatsapp_report(self, data: dict) -> str:
        """Format scan data as WhatsApp-ready message."""
        score    = data.get("brand_score", 0)
        mentions = data.get("brand_mentions", 0)
        answered = data.get("api_answered", 0)
        month    = data.get("scan_month", "")
        trend    = data.get("trend", {})
        comp     = data.get("competitor_summary", {})
        missed   = data.get("missed_topics", [])

        # Score colour
        score_icon = "🟢" if score >= 60 else "🟡" if score >= 30 else "🔴"

        # Trend
        d = trend.get("direction", "new")
        if d == "up":
            trend_str = "⬆️  +{}% vs last month".format(trend["change"])
        elif d == "down":
            trend_str = "⬇️  -{}% vs last month".format(trend["change"])
        elif d == "new":
            trend_str = "🆕  First scan — baseline set"
        else:
            trend_str = "➡️  No change"

        lines = [
            "🤖 *AEO BRAND MONITOR — FALCON HERBS*",
            "📅 {}".format(month),
            "─" * 30,
            "",
            "{} *AI VISIBILITY: {}%*".format(score_icon, score),
            "   Mentioned in {}/{} AI answers".format(mentions, answered),
            "   {}".format(trend_str),
        ]

        # Competitors
        if comp:
            lines += ["", "🏆 *COMPETITORS MENTIONED INSTEAD:*"]
            for name, count in list(comp.items())[:4]:
                bar = "█" * min(count, 8)
                lines.append("   {} {} {}x".format(
                    name.title(), bar, count
                ))

        # Top content gaps
        if missed:
            seen: set = set()
            unique_missed = []
            for m in missed:
                if m["topic"] not in seen:
                    seen.add(m["topic"])
                    unique_missed.append(m)

            lines += ["", "📝 *TOP CONTENT GAPS (write these):*"]
            for m in unique_missed[:5]:
                lines.append("   • {}".format(
                    m["topic"].replace("-", " ").title()
                ))
            lines.append(
                "\n✅ {} gaps auto-queued in ContentWorkflow".format(
                    len(unique_missed)
                )
            )

        lines += [
            "",
            "─" * 30,
            "🦅 _Falcon Agency — AEO Monitor_",
        ]
        return "\n".join(lines)

    def get_latest_report(self) -> str:
        """Return most recent saved scan as WhatsApp message."""
        scans = sorted(self.data_dir.glob("scan_*.json"), reverse=True)
        if not scans:
            return (
                "📊 *AEO STATUS*\n"
                "No scans run yet.\n"
                "Say *'aeo scan'* to start monthly monitoring.\n\n"
                "ℹ️ Needs PERPLEXITY_API_KEY in .env"
            )
        try:
            data = json.loads(scans[0].read_text(encoding="utf-8"))
            return self._format_whatsapp_report(data)
        except Exception as e:
            return "❌ AEO report error: {}".format(e)

    def get_status_summary(self) -> str:
        """Quick one-liner status for bridge status report."""
        scans = sorted(self.data_dir.glob("scan_*.json"), reverse=True)
        if not scans:
            return "No scans yet"
        try:
            data = json.loads(scans[0].read_text(encoding="utf-8"))
            return "Score {}% — {} gaps queued".format(
                data.get("brand_score", 0),
                len([g for g in self.get_content_gaps()
                     if not g.get("used")])
            )
        except Exception:
            return "Error reading scan"


# ═══════════════════════════════════════════════════════════
#  STANDALONE TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ))

    print("🤖 AEO Agent — Test Mode")
    print("=" * 50)

    agent = AEOAgent()

    # ── Check API availability ───────────────────────────
    perp = bool(os.getenv("PERPLEXITY_API_KEY"))
    oai  = bool(os.getenv("OPENAI_API_KEY"))
    nv   = bool(os.getenv("NVIDIA_API_KEY"))
    print(f"APIs: Perplexity={'✅' if perp else '❌'}  "
          f"OpenAI={'✅' if oai else '❌'}  "
          f"NVIDIA={'✅' if nv else '❌'}")

    if not (perp or oai or nv):
        print("\n⚠️  No API keys found in .env")
        print("Add PERPLEXITY_API_KEY or OPENAI_API_KEY to run live scan")
        print("\nRunning OFFLINE demo with 2 mock questions...")

        # Offline demo — simulate a result
        mock_data = {
            "scan_month":        "2026-02",
            "total_questions":   2,
            "api_answered":      0,
            "brand_mentions":    0,
            "brand_score":       0,
            "missed_topics": [
                {"topic": "immunity booster ayurveda",
                 "keyword": "best ayurvedic brand immunity India"},
                {"topic": "ashwagandha stress relief",
                 "keyword": "best ashwagandha brand India"},
            ],
            "competitor_summary": {},
            "trend": {"direction": "new", "change": 0},
        }
        print("\n" + agent._format_whatsapp_report(mock_data))
    else:
        print("\n🚀 Running LIVE scan (2 questions)...")
        q = agent.QUESTIONS[:2]
        for item in q:
            ans, eng = agent._best_answer(item["q"])
            analysis = agent._analyse(ans) if ans else {}
            mentioned = analysis.get("brand_mentioned", False)
            print(f"\nQ: {item['q'][:60]}")
            print(f"  Engine: {eng}")
            print(f"  Brand: {'✅ mentioned' if mentioned else '❌ not mentioned'}")
            comps = analysis.get("competitors_mentioned", [])
            if comps:
                print(f"  Competitors: {', '.join(comps)}")

    # ── Content gaps test ────────────────────────────────
    gaps = agent.get_content_gaps()
    print(f"\n📝 Current content gaps: {len(gaps)}")

    print("\n✅ AEO Agent test complete!")
