"""
Falcon Agency — Health Claims Scanner
Crawls website and flags FDA/FTC risky language
NOT legal advice — risk flagging tool only
"""

import requests
import re
import json
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class HealthClaimsScanner:
    """
    Scans product pages for health claims that could
    violate FDA/FTC regulations for dietary supplements
    and herbal products.
    """
    
    def __init__(self, site_url="https://falconherbs.com"):
        self.site_url = site_url
        self.data_dir = Path("data/health_audit")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scanned_urls = set()
        self.results = []
        self._smart_swaps = self._load_smart_swaps()
        
        # ====== VIOLATION PATTERNS ======
        # These are common FDA/FTC red flags for supplements
        
        self.high_risk_patterns = {
            "disease_cure_claims": {
                "patterns": [
                    r"\bcures?\b",
                    r"\bcure\s+(?:for|of)\b",
                    r"\btreat(?:s|ment)?\b.*(?:disease|cancer|diabetes|"
                    r"arthritis|HIV|AIDS|covid|tumor|infection|condition)",
                    r"\bprevents?\b.*(?:cancer|disease|infection|diabetes|heart)",
                    r"\bheals?\b.*(?:disease|condition|disorder|wound|infection)",
                    r"\beliminates?\b.*(?:disease|cancer|tumor|infection|toxin)",
                    r"\banti[- ]?cancer\b",
                    r"\banti[- ]?tumor\b",
                    r"\banti[- ]?diabetic\b",
                    r"\bcancer[- ]?fighting\b",
                    r"\b(?:effective|works?)\s+(?:for|against)\s+(?:cancer|diabetes|disease)",
                    r"\bcombats?\s+(?:cancer|diabetes|disease|infection)",
                    r"\bfights?\s+(?:cancer|diabetes|disease|tumor)",
                    r"\breverses?\s+(?:diabetes|cancer|disease)",
                    r"\b(?:remedy|remedies)\s+for\b",
                ],
                "risk": "HIGH",
                "reason": "Direct disease claims — FDA considers this "
                          "marketing an unapproved drug",
                "fix": "Remove disease names. Use structure/function "
                       "claims instead."
            },
            
            "drug_claims": {
                "patterns": [
                    r"\bclinically\s+proven\b",
                    r"\bscientifically\s+proven\b",
                    r"\bmedically\s+proven\b",
                    r"\bFDA\s+approved\b",
                    r"\bdoctor\s+recommended\b",
                    r"\bprescri(?:be|ption)\b",
                    r"\bguaranteed\s+(?:to|results?)\b",
                    r"\b100%\s+(?:effective|cure|guaranteed)\b",
                    r"\bproven\s+to\s+(?:cure|treat|prevent)\b",
                    r"\bguaranteed\s+(?:cure|relief|results?)\b",
                ],
                "risk": "HIGH",
                "reason": "Makes product sound like a drug — "
                          "requires FDA drug approval",
                "fix": "Use 'traditionally used for' or "
                       "'may support' language"
            },
            
            "specific_disease_mentions": {
                "patterns": [
                    r"\bcancer\b", r"\bdiabetes\b", r"\bheart\s+disease\b",
                    r"\bAlzheimer'?s?\b", r"\bParkinson'?s?\b",
                    r"\bHIV\b", r"\bAIDS\b", r"\bcovid\b",
                    r"\bcoronavirus\b", r"\btumor\b", r"\bmalignant\b",
                    r"\bhypertension\b", r"\bstroke\b", r"\bepilepsy\b",
                    r"\basthma\b", r"\bhepatitis\b", r"\btuberculos\w+\b",
                    r"\bmalaria\b", r"\bdepression\b",
                    r"\banxi(?:ety|ous)\b",
                    r"\binsomnia\b", r"\barthritis\b", r"\beczema\b",
                    r"\bpsoriasis\b",
                    r"\bconstipation\b", r"\bindigestion\b",
                    r"\bobesity\b", r"\boverweight\b",
                    r"\bkidney\s+(?:disease|failure|stone)\b",
                    r"\bliver\s+(?:disease|failure)\b",
                    r"\b(?:skin|blood)\s+infection\b",
                    r"\b(?:skin|blood)\s+disorder\b",
                ],
                "risk": "HIGH",
                "reason": "Mentioning diseases in product context = "
                          "implied drug claim",
                "fix": "Remove disease names. Describe symptoms or "
                       "body functions instead."
            },
            
            "for_disease_claims": {
                "patterns": [
                    r"\bfor\s+(?:diabetes|cancer|heart\s+disease|hypertension)\b",
                    r"\bfor\s+(?:constipation|indigestion|obesity|depression)\b",
                    r"\bfor\s+(?:anxiety|arthritis|asthma|eczema|psoriasis)\b",
                    r"\b(?:relief|relieves?)\s+from\s+(?:diabetes|arthritis|pain)\b",
                    r"\b(?:relief|relieves?)\s+(?:for|of)\s+(?:constipation|pain)\b",
                ],
                "risk": "HIGH",
                "reason": "'For [disease]' = implied treatment claim",
                "fix": "Use 'traditionally used to support' or 'may help with wellness'"
            },
        }
        
        self.medium_risk_patterns = {
            "implied_treatment": {
                "patterns": [
                    r"\bboosts?\s+immun\w+\b",
                    r"\bstrengthens?\s+immun\w+\b",
                    r"\b(?:boost|boosts)\s+(?:immunity|energy)\b",
                    r"\bfights?\s+(?:infection|virus|bacteria)\b",
                    r"\banti[- ]?(?:viral|bacterial|fungal|microbial|"
                    r"inflammatory|oxidant)\b",
                    r"\bdetox(?:ify|ifies|ification)?\b",
                    r"\bdetox\s+(?:body|blood|liver)\b",
                    r"\bcleanses?\s+(?:blood|liver|kidney|body|toxins)\b",
                    r"\bpurif(?:y|ies)\s+blood\b",
                    r"\blowers?\s+(?:blood\s+(?:sugar|pressure)|"
                    r"cholesterol)\b",
                    r"\breduces?\s+(?:blood\s+sugar|cholesterol|"
                    r"blood\s+pressure)\b",
                    r"\bcontrols?\s+(?:blood\s+sugar|cholesterol|"
                    r"blood\s+pressure)\b",
                    r"\bmanages?\s+(?:diabetes|blood\s+sugar)\b",
                    r"\bregulates?\s+(?:blood\s+sugar|cholesterol)\b",
                    r"\bimproves?\s+(?:digestion|blood\s+sugar|cholesterol)\b",
                    r"\bhelps?\s+(?:in\s+)?(?:getting\s+rid\s+of|rid\s+of)\b",
                    r"\bweight\s+loss\b",
                    r"\bshed\s+(?:weight|pounds)\b",
                    r"\bburn\s+fat\b",
                    r"\breduces?\s+(?:stress|anxiety|inflammation)\b",
                    r"\b(?:relief|relieves?)\s+(?:from|for)\b",
                    r"\b(?:treat|treatment)\s+of\s+(?:skin|infection)\b",
                ],
                "risk": "MEDIUM",
                "reason": "Implied treatment claims — borderline "
                          "FDA violation",
                "fix": "Rephrase: 'supports healthy immune function' "
                       "instead of 'boosts immunity'"
            },
            
            "absolute_claims": {
                "patterns": [
                    r"\b100%\s+(?:natural|safe|effective|organic|pure)\b",
                    r"\bno\s+side\s+effects?\b",
                    r"\bcompletely\s+safe\b",
                    r"\brisk[- ]?free\b",
                    r"\bmiracle\b",
                    r"\bmagic(?:al)?\b",
                    r"\bwonder\s+(?:herb|drug|cure|remedy)\b",
                    r"\binstant\s+(?:relief|results?|cure)\b",
                    r"\bpermanent\s+(?:cure|solution|relief)\b",
                    r"\bguaranteed\s+(?:results?|relief)\b",
                    r"\bproven\s+(?:effective|to\s+work)\b",
                    r"\bpowerful\s+(?:cure|remedy|treatment)\b",
                    r"\btransform(?:s|ing)?\s+(?:your\s+)?(?:health|body)\b",
                ],
                "risk": "MEDIUM",
                "reason": "Absolute/exaggerated claims — FTC violation",
                "fix": "Add qualifiers: 'may help', "
                       "'traditionally used for'"
            },
            
            "ayurvedic_marketing": {
                "patterns": [
                    r"\b(?:cure|treat|heal)\s+for\b",
                    r"\bgood\s+for\s+(?:diabetes|cancer)\b",
                    r"\b(?:benefits?|beneficial)\s+for\s+(?:diabetes|cancer)\b",
                    r"\b(?:effective|works?)\s+for\s+(?:constipation|indigestion)\b",
                    r"\bimmunity\s+booster\b",
                    r"\bblood\s+sugar\s+(?:control|management)\b",
                    r"\bcholesterol\s+(?:control|lowering)\b",
                ],
                "risk": "MEDIUM",
                "reason": "Implied treatment — use structure/function language",
                "fix": "Use smart swap: 'supports X' or 'traditionally used for'"
            },
        }
        
        self.low_risk_patterns = {
            "missing_disclaimers": {
                "check_absence": [
                    r"These statements have not been evaluated",
                    r"not intended to diagnose",
                    r"consult.*(?:doctor|physician|healthcare)",
                    r"individual results may vary",
                ],
                "risk": "LOW",
                "reason": "FDA requires disclaimer on supplement pages",
                "fix": "Add standard FDA disclaimer to all product pages"
            },
        }
        
        # Additional LOW risk patterns (regex-based, like high/medium)
        self.low_risk_regex_patterns = {
            "borderline_claims": {
                "patterns": [
                    r"\b(?:helps?|supporting|supports?)\s+(?:with|in)\s+"
                    r"(?:constipation|indigestion|digestion)\b",
                    r"\b(?:natural|herbal)\s+(?:remedy|treatment)\b",
                    r"\b(?:traditional|ayurvedic)\s+(?:cure|remedy)\b",
                    r"\b(?:skin|hair|digestion)\s+(?:health|benefits?)\b",
                    r"\b(?:anti[- ]?oxidant|antioxidant)\s+(?:properties?|rich)\b",
                    r"\b(?:anti[- ]?bacterial|antibacterial)\s+(?:properties?)\b",
                ],
                "risk": "LOW",
                "reason": "Borderline — may need disclaimer",
                "fix": "Add FDA disclaimer; ensure structure/function language"
            },
        }
        
        # ====== SAFE ALTERNATIVES (SEO + compliant) ======
        # Load from config/smart_word_swap.json; fallback to built-in
        self.safe_replacements = {
            "cures": "traditionally used to support",
            "treats": "may help with",
            "prevents": "traditionally associated with",
            "heals": "supports natural",
            "boosts immunity": "supports healthy immune function",
            "fights infection": "supports the body's natural defenses",
            "anti-cancer": "rich in antioxidants",
            "lowers blood sugar": "may support healthy blood sugar levels already within normal range",
            "lowers blood pressure": "may support healthy blood pressure already within normal range",
            "cures diabetes": "traditionally used in Ayurveda for metabolic wellness",
            "detoxifies": "supports the body's natural cleansing processes",
            "purifies blood": "traditionally used to support skin and liver health",
            "no side effects": "generally well-tolerated when used as directed",
            "clinically proven": "supported by traditional Ayurvedic use",
            "100% safe": "made with carefully selected natural ingredients",
            "miracle": "time-honored",
            "instant relief": "fast-acting support",
        }
        if self._smart_swaps:
            self.safe_replacements.update(self._smart_swaps)
    
    def _load_smart_swaps(self) -> dict:
        """Load SEO-safe replacements from config."""
        try:
            cfg = Path(__file__).parent.parent / "config" / "smart_word_swap.json"
            if cfg.exists():
                data = json.loads(cfg.read_text(encoding="utf-8"))
                return data.get("replacements", {})
        except Exception:
            pass
        return {}
    
    def apply_smart_swaps(self, text: str) -> str:
        """
        Apply SEO-safe claim replacements to text.
        Uses phrase_priority so longer phrases get replaced first.
        """
        if not text or not self.safe_replacements:
            return text
        out = text
        # Sort by phrase length (longer first) so "cures diabetes" before "cures"
        order = sorted(
            self.safe_replacements.keys(),
            key=lambda k: (-len(k), k),
        )
        # Multiple passes: "for diabetes" → "for healthy blood sugar" → "for metabolic wellness"
        prev = None
        while prev != out:
            prev = out
            for bad in order:
                good = self.safe_replacements[bad]
                pat = re.compile(r"\b" + re.escape(bad) + r"\b", re.IGNORECASE)
                out = pat.sub(good, out)
        return out
    
    def crawl_site(self, max_pages=200):
        """Crawl the website and collect all page URLs"""
        print(f"🕷️ Crawling {self.site_url}...")
        
        to_visit = [self.site_url]
        visited = set()
        pages = []
        
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
            
            # Only crawl same domain
            if urlparse(url).netloc != urlparse(self.site_url).netloc:
                continue
            
            # Skip non-page URLs
            skip_ext = (
                '.jpg', '.jpeg', '.png', '.gif', '.pdf',
                '.css', '.js', '.svg', '.ico', '.webp',
                '.zip', '.mp4', '.mp3'
            )
            if any(url.lower().endswith(ext) for ext in skip_ext):
                continue
            
            try:
                response = requests.get(url, timeout=15, headers={
                    "User-Agent": "FalconAgency-HealthScanner/1.0"
                })
                
                if response.status_code != 200:
                    continue
                
                if 'text/html' not in response.headers.get(
                    'content-type', ''
                ):
                    continue
                
                visited.add(url)
                
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string if soup.title else "No Title"
                
                # Get visible text (script/style removed)
                for tag in soup(["script", "style"]):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)
                
                pages.append({
                    "url": url,
                    "title": title.strip() if title else "",
                    "text": text,
                    "is_product": self._is_product_page(url, soup)
                })
                
                print(f"  ✅ {len(visited)}/{max_pages}: {url[:80]}")
                
                # Find more links
                for link in soup.find_all('a', href=True):
                    full_url = urljoin(url, link['href']).split('#')[0]
                    full_url = full_url.split('?')[0]
                    if full_url not in visited:
                        to_visit.append(full_url)
                
            except Exception as e:
                print(f"  ❌ Error: {url[:60]} — {str(e)[:50]}")
                continue
        
        print(f"\n📊 Crawled {len(pages)} pages")
        return pages
    
    def _is_product_page(self, url, soup):
        """Detect if this is a product page"""
        if '/product/' in url:
            return True
        if soup.find('button', class_=re.compile('add.to.cart',
                                                   re.IGNORECASE)):
            return True
        if soup.find('span', class_=re.compile('price',
                                                re.IGNORECASE)):
            return True
        return False
    
    def scan_page(self, url, text, title, is_product=False):
        """Scan a single page for health claim violations"""
        findings = {
            "url": url,
            "title": title,
            "is_product": is_product,
            "high_risk": [],
            "medium_risk": [],
            "low_risk": [],
            "risk_score": 0,
            "suggested_fixes": []
        }
        
        text_lower = text.lower()
        
        # Check HIGH risk
        for category, data in self.high_risk_patterns.items():
            for pattern in data["patterns"]:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    # Get context (50 chars around match)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    
                    findings["high_risk"].append({
                        "category": category,
                        "matched": match.group(),
                        "context": f"...{context}...",
                        "reason": data["reason"],
                        "fix": data["fix"]
                    })
                    findings["risk_score"] += 10
        
        # Check MEDIUM risk
        for category, data in self.medium_risk_patterns.items():
            for pattern in data["patterns"]:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    
                    findings["medium_risk"].append({
                        "category": category,
                        "matched": match.group(),
                        "context": f"...{context}...",
                        "reason": data["reason"],
                        "fix": data["fix"]
                    })
                    findings["risk_score"] += 5
        
        # Check LOW risk (missing disclaimers)
        for category, data in self.low_risk_patterns.items():
            for pattern in data["check_absence"]:
                if not re.search(pattern, text_lower):
                    findings["low_risk"].append({
                        "category": category,
                        "issue": f"Missing: '{pattern}'",
                        "reason": data["reason"],
                        "fix": data["fix"]
                    })
                    findings["risk_score"] += 2
        
        # Check LOW risk (borderline regex matches)
        for category, data in self.low_risk_regex_patterns.items():
            for pattern in data["patterns"]:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end].strip()
                    findings["low_risk"].append({
                        "category": category,
                        "matched": match.group(),
                        "context": f"...{context}...",
                        "reason": data["reason"],
                        "fix": data["fix"]
                    })
                    findings["risk_score"] += 2
        
        # Generate specific fixes
        for item in findings["high_risk"] + findings["medium_risk"]:
            matched = item["matched"].lower()
            for bad, good in self.safe_replacements.items():
                if bad in matched:
                    findings["suggested_fixes"].append({
                        "original": item["matched"],
                        "suggested": good,
                        "page": url
                    })
        
        return findings
    
    def full_scan(self, max_pages=200):
        """Complete site health claims audit"""
        print("=" * 50)
        print("🏥 HEALTH CLAIMS AUDIT — FALCON HERBS")
        print("=" * 50)
        
        # Step 1: Crawl
        pages = self.crawl_site(max_pages)
        
        # Step 2: Scan each page
        print("\n🔍 Scanning for health claim violations...")
        all_findings = []
        
        for page in pages:
            findings = self.scan_page(
                url=page["url"],
                text=page["text"],
                title=page["title"],
                is_product=page["is_product"]
            )
            
            if (findings["high_risk"] or 
                findings["medium_risk"] or 
                findings["low_risk"]):
                all_findings.append(findings)
        
        # Step 3: Generate report
        report = {
            "audit_date": datetime.now().isoformat(),
            "site": self.site_url,
            "pages_crawled": len(pages),
            "pages_with_issues": len(all_findings),
            "product_pages_scanned": sum(
                1 for p in pages if p["is_product"]
            ),
            "summary": {
                "high_risk_total": sum(
                    len(f["high_risk"]) for f in all_findings
                ),
                "medium_risk_total": sum(
                    len(f["medium_risk"]) for f in all_findings
                ),
                "low_risk_total": sum(
                    len(f["low_risk"]) for f in all_findings
                ),
            },
            "top_risky_pages": sorted(
                all_findings,
                key=lambda x: x["risk_score"],
                reverse=True
            )[:20],
            "all_findings": all_findings,
            "all_suggested_fixes": [],
            "disclaimer_template": self._get_disclaimer_template()
        }
        
        # Collect all fixes
        for f in all_findings:
            report["all_suggested_fixes"].extend(
                f.get("suggested_fixes", [])
            )
        
        # Save
        self._save_report(report)
        
        # Print summary
        summary = self._generate_whatsapp_summary(report)
        print(summary)
        
        return {"success": True, "data": report, "summary": summary}
    
    def _get_disclaimer_template(self):
        """Standard FDA disclaimer for supplement pages"""
        return {
            "english": (
                "*Disclaimer: These statements have not been "
                "evaluated by the Food and Drug Administration. "
                "This product is not intended to diagnose, treat, "
                "cure, or prevent any disease. Please consult your "
                "healthcare provider before using any herbal "
                "supplements. Individual results may vary."
            ),
            "short": (
                "*This product is not intended to diagnose, treat, "
                "cure, or prevent any disease."
            ),
            "ayurveda_specific": (
                "*Based on traditional Ayurvedic practices. These "
                "statements have not been evaluated by the FDA. "
                "This product is not intended to diagnose, treat, "
                "cure, or prevent any disease. Consult a healthcare "
                "professional before use."
            )
        }
    
    def _generate_whatsapp_summary(self, report):
        """WhatsApp-friendly summary"""
        lines = [
            "🏥 *HEALTH CLAIMS AUDIT REPORT*",
            f"📅 {datetime.now().strftime('%d %b %Y')}",
            f"🌐 {self.site_url}",
            "─" * 30,
            "",
            f"📄 Pages Scanned: {report['pages_crawled']}",
            f"⚠️ Pages with Issues: {report['pages_with_issues']}",
            "",
            f"🔴 HIGH Risk Claims: "
            f"{report['summary']['high_risk_total']}",
            f"🟡 MEDIUM Risk Claims: "
            f"{report['summary']['medium_risk_total']}",
            f"🟢 LOW Risk Issues: "
            f"{report['summary']['low_risk_total']}",
            "",
        ]
        
        if report["summary"]["high_risk_total"] > 0:
            lines.append("🚨 *TOP RISKY PAGES:*")
            for page in report["top_risky_pages"][:5]:
                lines.append(
                    f"  ⚠️ Score {page['risk_score']}: "
                    f"{page['title'][:40]}"
                )
                lines.append(f"     {page['url'][:60]}")
                if page["high_risk"]:
                    lines.append(
                        f"     Found: "
                        f"{page['high_risk'][0]['matched']}"
                    )
            lines.append("")
        
        fixes = report.get("all_suggested_fixes", [])
        if fixes:
            lines.append("✏️ *TOP SUGGESTED FIXES:*")
            seen = set()
            for fix in fixes[:10]:
                key = fix["original"]
                if key not in seen:
                    seen.add(key)
                    lines.append(
                        f"  ❌ '{fix['original']}'"
                    )
                    lines.append(
                        f"  ✅ '{fix['suggested']}'"
                    )
                    lines.append("")
        
        lines.extend([
            "─" * 30,
            "⚖️ _This is AI-generated risk flagging,_",
            "_NOT legal advice. Review with judgment._",
            "🤖 _Falcon Agency — Health Scanner_"
        ])
        
        return "\n".join(lines)
    
    def _save_report(self, report):
        """Save report to JSON"""
        filepath = self.data_dir / "health_audit_report.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Report saved: {filepath}")


# ==================== STANDALONE TEST ====================

if __name__ == "__main__":
    scanner = HealthClaimsScanner("https://falconherbs.com")
    result = scanner.full_scan(max_pages=100)
    
    if result["success"]:
        data = result["data"]
        print(f"\n🏁 SCAN COMPLETE")
        print(f"   High Risk: {data['summary']['high_risk_total']}")
        print(f"   Medium Risk: {data['summary']['medium_risk_total']}")
        print(f"   Low Risk: {data['summary']['low_risk_total']}")
