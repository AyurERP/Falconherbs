"""
Falcon Agency — Competitor Price Tracker
=========================================
Scrapes Amazon India for competitor Ayurvedic product prices,
computes recommended Falcon Herbs price (undercut by ₹5-20),
and sends weekly WhatsApp alert if prices change.

Strategy: Price ₹5-10 below competitors to acquire customers,
increase price once loyalty/repeat purchase is established.

Gap tiers:
  budget   our_price < ₹200  → undercut ₹5
  standard ₹200–₹499         → undercut ₹10
  premium  ₹500+              → undercut ₹20

Data stored in: data/pricing/
Config read from: config/product_map.yaml
"""

import os
import re
import json
import time
import yaml
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional


# Realistic browser headers to avoid basic bot blocks
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# How many seconds to wait between Amazon requests
_AMAZON_DELAY = 2.5


class PriceTrackerAgent:
    """
    Weekly competitor price monitor for Falcon Herbs.
    Reads product map from config/product_map.yaml,
    scrapes Amazon India prices, computes undercut recommendation,
    saves history, sends WhatsApp alert.
    """

    def __init__(self, bridge=None):
        self.bridge = bridge
        self.data_dir = Path("data/pricing")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.product_map_file = Path("config/product_map.yaml")
        self._products = None   # lazy-loaded

    # ─────────────────────────────────────────────────────
    #  PRODUCT MAP
    # ─────────────────────────────────────────────────────

    def load_product_map(self) -> list:
        """Load product mapping from YAML. Cached after first load."""
        if self._products is not None:
            return self._products
        if not self.product_map_file.exists():
            return []
        with open(self.product_map_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._products = data.get("products", [])
        return self._products

    # ─────────────────────────────────────────────────────
    #  SCRAPERS
    # ─────────────────────────────────────────────────────

    def scrape_amazon_price(self, url: str) -> Optional[float]:
        """
        Scrape current price from Amazon India product page.
        Returns price as float (₹) or None if unavailable.
        Handles both standard pricing and deal prices.
        """
        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=15
            )
            if resp.status_code != 200:
                return None

            html = resp.text

            # Try multiple Amazon price patterns (format changes often)
            patterns = [
                # JSON price in page data
                r'"priceAmount":\s*([\d.]+)',
                # Standard buy box price
                r'id="priceblock_ourprice"[^>]*>\s*[₹\s]*([\d,]+)',
                r'id="priceblock_dealprice"[^>]*>\s*[₹\s]*([\d,]+)',
                # a-price format (most common 2024+)
                r'class="a-price-whole"[^>]*>\s*([\d,]+)',
                # a-offscreen (hidden but machine-readable)
                r'class="a-offscreen"[^>]*>[₹\s]*([\d,]+\.?\d*)',
                # corePrice format
                r'"corePrice"[^>]*>[₹\s]*([\d,]+)',
                # apex price
                r'apexPriceToPay[^>]*>[₹\s]*([\d,]+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    raw = match.group(1).replace(",", "").strip()
                    try:
                        price = float(raw)
                        if 10 < price < 10000:  # Sanity check
                            return price
                    except ValueError:
                        continue

            return None

        except Exception:
            return None

    def scrape_1mg_price(self, url: str) -> Optional[float]:
        """
        Scrape price from 1mg.com product page.
        Used as supplementary source when Amazon unavailable.
        """
        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=15
            )
            if resp.status_code != 200:
                return None

            html = resp.text

            patterns = [
                r'"price":\s*"?([\d.]+)"?',
                r'class="[^"]*price[^"]*"[^>]*>[₹\s]*([\d,]+)',
                r'"sellingPrice":\s*([\d.]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    raw = match.group(1).replace(",", "").strip()
                    try:
                        price = float(raw)
                        if 10 < price < 10000:
                            return price
                    except ValueError:
                        continue
            return None

        except Exception:
            return None

    # ─────────────────────────────────────────────────────
    #  PRICING STRATEGY
    # ─────────────────────────────────────────────────────

    def get_gap(self, our_price: float) -> int:
        """
        Tiered undercut gap based on our current price.
        budget < ₹200 → ₹5 gap
        standard ₹200-499 → ₹10 gap
        premium ₹500+ → ₹20 gap
        """
        if our_price < 200:
            return 5
        elif our_price < 500:
            return 10
        return 20

    def compute_recommendation(
        self,
        product: dict,
        competitor_prices: dict,
    ) -> dict:
        """
        Given scraped competitor prices, compute:
          - competitor average
          - competitor minimum
          - recommended price for Falcon Herbs
          - action (lower/raise/ok)
        """
        prices = [
            v for v in competitor_prices.values()
            if v is not None and v > 0
        ]
        if not prices:
            return {
                "competitor_avg": None,
                "competitor_min": None,
                "recommended": None,
                "action": "no_data",
                "note": "No competitor prices available",
            }

        our_price   = product.get("our_price", 0)
        comp_avg    = round(sum(prices) / len(prices), 2)
        comp_min    = min(prices)
        gap         = self.get_gap(our_price)
        recommended = round(comp_min - gap)

        # Determine action
        diff = our_price - recommended
        if diff > 15:
            action = "lower"
            note = "Lower by ₹{} to match competition".format(diff)
        elif diff < -20:
            action = "raise"
            note = "Room to raise by ₹{} — still competitive".format(abs(diff))
        else:
            action = "ok"
            note = "Price competitive ✅"

        return {
            "competitor_avg":  comp_avg,
            "competitor_min":  comp_min,
            "recommended":     recommended,
            "gap_applied":     gap,
            "action":          action,
            "note":            note,
        }

    # ─────────────────────────────────────────────────────
    #  MANUAL PRICE UPDATE (via WhatsApp)
    # ─────────────────────────────────────────────────────

    def update_manual_price(
        self,
        product_name: str,
        brand: str,
        price: float,
    ) -> dict:
        """
        Manually set a competitor's price (WhatsApp command).
        Use when scraping fails or for offline verification.
        """
        manual_file = self.data_dir / "manual_prices.json"
        manual = {}
        if manual_file.exists():
            try:
                manual = json.loads(
                    manual_file.read_text(encoding="utf-8")
                )
            except Exception:
                pass

        key = product_name.lower().strip()
        if key not in manual:
            manual[key] = {}

        manual[key][brand.lower()] = {
            "price":      price,
            "updated_at": datetime.now().isoformat(),
            "source":     "manual",
        }

        manual_file.write_text(
            json.dumps(manual, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "success": True,
            "message": "Updated: {} — {} = ₹{:.0f}".format(
                product_name, brand.title(), price
            ),
        }

    def _load_manual_prices(self) -> dict:
        """Load manually entered prices as fallback."""
        manual_file = self.data_dir / "manual_prices.json"
        if not manual_file.exists():
            return {}
        try:
            return json.loads(
                manual_file.read_text(encoding="utf-8")
            )
        except Exception:
            return {}

    # ─────────────────────────────────────────────────────
    #  CORE SCAN
    # ─────────────────────────────────────────────────────

    def run_weekly_scan(self, silent: bool = False) -> dict:
        """
        Full weekly scan: scrape all products, compute
        recommendations, save results, return report.
        """
        products = self.load_product_map()
        manual   = self._load_manual_prices()

        if not products:
            return {
                "success": False,
                "error": "No products in config/product_map.yaml",
            }

        scan_results = []
        alerts       = []    # Products needing price action

        for product in products:
            name      = product["name"]
            our_price = product.get("our_price", 0)
            comps     = product.get("competitors", {})

            if not silent:
                print(f"[PRICE] Scanning: {name}...")

            competitor_prices: dict = {}

            for brand, comp_info in comps.items():
                price = None

                # 1. Try Amazon scrape
                amazon_url = comp_info.get("amazon_url")
                if amazon_url:
                    price = self.scrape_amazon_price(amazon_url)
                    if price:
                        time.sleep(_AMAZON_DELAY)

                # 2. Fallback: manual price
                if price is None:
                    man = manual.get(name.lower(), {})
                    if brand in man:
                        price = man[brand].get("price")

                competitor_prices[brand] = price

            rec = self.compute_recommendation(product, competitor_prices)

            entry = {
                "product":          name,
                "our_sku":          product.get("our_sku", ""),
                "our_price":        our_price,
                "category":         product.get("category", ""),
                "competitor_prices": competitor_prices,
                "recommendation":   rec,
                "scanned_at":       datetime.now().isoformat(),
            }
            scan_results.append(entry)

            if rec.get("action") in ("lower", "raise"):
                alerts.append(entry)

        # Save scan
        scan_date = datetime.now().strftime("%Y-%m-%d")
        out_file  = self.data_dir / f"scan_{scan_date}.json"
        out_file.write_text(
            json.dumps(scan_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Save latest (for quick WhatsApp status)
        latest_file = self.data_dir / "latest.json"
        latest_file.write_text(
            json.dumps(scan_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        summary = self._format_whatsapp_report(
            scan_results, alerts, scan_date
        )

        return {
            "success":   True,
            "products":  len(scan_results),
            "alerts":    len(alerts),
            "data":      scan_results,
            "summary":   summary,
        }

    # ─────────────────────────────────────────────────────
    #  REPORTING
    # ─────────────────────────────────────────────────────

    def _format_whatsapp_report(
        self,
        results: list,
        alerts: list,
        scan_date: str,
    ) -> str:
        """Format scan results for WhatsApp."""
        lines = [
            "\U0001F4B0 *COMPETITOR PRICE REPORT*",
            "\U0001F4C5 {}".format(scan_date),
            "\u2500" * 30,
        ]

        if alerts:
            lines.append("\n\u26A0\uFE0F *ACTION NEEDED:*")
            for a in alerts:
                rec  = a["recommendation"]
                act  = rec.get("action", "")
                icon = "\u2B07\uFE0F" if act == "lower" else "\u2B06\uFE0F"
                lines.append(
                    "{} *{}*\n"
                    "   Our price:  \u20B9{}\n"
                    "   Comp. min:  \u20B9{}\n"
                    "   Suggested:  \u20B9{}\n"
                    "   \U0001F4AC {}".format(
                        icon,
                        a["product"],
                        a["our_price"],
                        rec.get("competitor_min", "?"),
                        rec.get("recommended", "?"),
                        rec.get("note", ""),
                    )
                )
        else:
            lines.append("\n\u2705 All prices competitive!")

        # Full table
        lines.append("\n\U0001F4CA *FULL COMPARISON:*")
        for r in results:
            rec       = r["recommendation"]
            comp_min  = rec.get("competitor_min")
            suggested = rec.get("recommended")
            status    = (
                "\u2705" if rec.get("action") == "ok"
                else "\u26A0\uFE0F"
            )
            comp_str = (
                "\u20B9{:.0f}".format(comp_min)
                if comp_min else "N/A"
            )
            sug_str = (
                "\u20B9{:.0f}".format(suggested)
                if suggested else "N/A"
            )
            lines.append(
                "{} {} | Ours:\u20B9{} | CompMin:{} | Rec:{}".format(
                    status,
                    r["product"][:22],
                    r["our_price"],
                    comp_str,
                    sug_str,
                )
            )

        lines += [
            "",
            "\u2500" * 30,
            "\U0001F916 _Falcon Agency \u2014 Pricing Intel_",
        ]
        return "\n".join(lines)

    def get_latest_report(self) -> str:
        """Return the most recent price scan as WhatsApp message."""
        latest = self.data_dir / "latest.json"
        if not latest.exists():
            return (
                "\U0001F4B0 *PRICING STATUS*\n"
                "No scans run yet.\n"
                "Say *'price scan'* to start weekly monitoring.\n\n"
                "\u2139\uFE0F Checks Amazon India for competitor prices."
            )
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            alerts = [
                r for r in data
                if r["recommendation"].get("action") in ("lower", "raise")
            ]
            scanned_at = (
                data[0].get("scanned_at", "?")[:10]
                if data else "?"
            )
            return self._format_whatsapp_report(data, alerts, scanned_at)
        except Exception as e:
            return "\u274C Price report error: {}".format(e)

    def get_status_summary(self) -> str:
        """One-liner for bridge status."""
        latest = self.data_dir / "latest.json"
        if not latest.exists():
            return "No scans yet"
        try:
            data   = json.loads(latest.read_text(encoding="utf-8"))
            alerts = sum(
                1 for r in data
                if r["recommendation"].get("action") in ("lower", "raise")
            )
            return "{} products tracked, {} need action".format(
                len(data), alerts
            )
        except Exception:
            return "Error reading scan"


# ═══════════════════════════════════════════════════════════
#  STANDALONE TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ))

    print("💰 Price Tracker — Test Mode")
    print("=" * 50)

    agent = PriceTrackerAgent()

    # Load product map
    products = agent.load_product_map()
    print(f"Products configured: {len(products)}")
    for p in products:
        comps = list(p.get("competitors", {}).keys())
        print(f"  • {p['name']} (₹{p['our_price']}) "
              f"vs {', '.join(comps)}")

    # Test pricing strategy
    print("\n📊 Gap strategy test:")
    for price in [150, 299, 599]:
        gap = agent.get_gap(price)
        print(f"  Our price ₹{price} → gap ₹{gap}")

    # Test recommendation with mock data
    mock_product = {"name": "Test", "our_price": 349}
    mock_prices  = {"himalaya": 379, "patanjali": 299, "dabur": 359}
    rec = agent.compute_recommendation(mock_product, mock_prices)
    print(f"\n🎯 Mock recommendation:")
    print(f"  Competitor min: ₹{rec['competitor_min']}")
    print(f"  Recommended:    ₹{rec['recommended']}")
    print(f"  Action:         {rec['action']}")
    print(f"  Note:           {rec['note']}")

    # Test manual price update
    result = agent.update_manual_price("Ashwagandha Capsules", "himalaya", 399)
    print(f"\n✍️  Manual update: {result['message']}")

    print("\n✅ Price Tracker test complete!")
    print("Run 'price scan' from WhatsApp for live Amazon scan")
