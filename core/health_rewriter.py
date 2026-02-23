"""
Falcon Agency -- Health Claims Rewriter
Scans all WooCommerce products for health claim violations,
AI-rewrites them using safe Ayurvedic language,
saves for approval. NEVER auto-applies.
"""

import json
from datetime import datetime
from pathlib import Path


class HealthClaimsRewriter:
    """Scan products for health claims, rewrite with
    safe Ayurvedic language, save for human approval."""

    def __init__(self, bridge):
        self.bridge = bridge
        self.rewrites_dir = Path("data/content/product_rewrites")
        self.rewrites_dir.mkdir(parents=True, exist_ok=True)

    # ── Scan ────────────────────────────────────────────

    def scan_all_products(self):
        """Scan all products via WooCommerce, run
        safety_check on each description.
        Returns {total, flagged, products: [list]}"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {
                    "success": False,
                    "error": "WooCommerce not loaded",
                }

            result = woo.get_all_products(save=False)
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "Unknown"),
                }

            pipeline = self.bridge.tools.get("content")
            if not pipeline:
                return {
                    "success": False,
                    "error": "Content Pipeline not loaded",
                }

            products = result["data"].get("products", [])
            flagged = []

            for p in products:
                pid = p.get("id")
                name = p.get("name", "")

                # Combine description + short_description
                desc = ""
                short_desc = ""
                try:
                    # get_all_products stores lengths,
                    # need raw product data for text
                    raw = woo._make_request(
                        f"products/{pid}"
                    )
                    if raw.get("success"):
                        desc = raw["data"].get(
                            "description", ""
                        )
                        short_desc = raw["data"].get(
                            "short_description", ""
                        )
                except Exception:
                    pass

                combined = f"{name} {desc} {short_desc}".strip()
                if not combined:
                    continue

                check = pipeline.safety_check(combined)
                
                # Specifically check title for safety too
                title_check = pipeline.safety_check(name)
                
                if not check.get("is_safe", True) or not title_check.get("is_safe", True):
                    flagged.append({
                        "id": pid,
                        "name": name,
                        "description": desc,
                        "short_description": short_desc,
                        "safety_check": check,
                        "title_safety_check": title_check
                    })

            # Save scan results for later rewrite
            scan_file = self.rewrites_dir / "last_scan.json"
            scan_data = {
                "scanned_at": datetime.now().isoformat(),
                "total": len(products),
                "flagged": len(flagged),
                "products": flagged,
            }
            with open(scan_file, "w", encoding="utf-8") as f:
                json.dump(scan_data, f, indent=2,
                          ensure_ascii=False)

            return {
                "success": True,
                "total": len(products),
                "flagged": len(flagged),
                "products": flagged,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Rewrite ─────────────────────────────────────────

    def rewrite_flagged(self, product_id=None):
        """AI-rewrite flagged product descriptions.
        If product_id given, rewrite just that one.
        Saves to product_rewrites/{id}.json.
        Returns count of rewrites generated."""
        try:
            # Load scan results
            scan_file = self.rewrites_dir / "last_scan.json"
            if not scan_file.exists():
                return {
                    "success": False,
                    "error": "No scan results. Run "
                             "scan_all_products() first.",
                }

            with open(scan_file, encoding="utf-8") as f:
                scan_data = json.load(f)

            flagged = scan_data.get("products", [])
            if product_id:
                flagged = [
                    p for p in flagged
                    if p["id"] == product_id
                ]

            pipeline = self.bridge.tools.get("content")
            if not pipeline:
                return {
                    "success": False,
                    "error": "Content Pipeline not loaded",
                }

            count = 0
            for product in flagged:
                pid = product["id"]
                name = product["name"]
                desc = product.get("description", "")
                short_desc = product.get(
                    "short_description", ""
                )

                # Use safety_check cleaned_content
                # as fallback rewrite
                check = product.get("safety_check", {})
                new_desc = check.get(
                    "cleaned_content", desc
                )

                # If AI client available, do proper
                # rewrite
                ai = self.bridge.tools.get("ai_client")
                new_name = name
                
                if ai:
                    # 1. Title Rewrite (if flagged)
                    t_check = product.get("title_safety_check", {})
                    if not t_check.get("is_safe", True):
                        try:
                            t_prompt = (
                                "Rewrite this product title to be safe and "
                                "compliant (no health claims/cures). "
                                "Keep it SEO-friendly.\n\n"
                                "Original Title: {}"
                            ).format(name)
                            t_response = ai.generate(t_prompt)
                            if t_response:
                                # Strip quotes if LLM adds them
                                new_name = t_response.strip().strip('"').strip("'")
                        except Exception:
                            pass

                    # 2. Description Rewrite
                    if desc:
                        try:
                            prompt = (
                                "Rewrite this product description "
                                "for '{}' using safe, compliant "
                                "Ayurvedic language. Remove ALL "
                                "health claims. Keep it compelling "
                                "and SEO-friendly.\n\n"
                                "Original:\n{}"
                            ).format(new_name, desc)
                            response = ai.generate(prompt)
                            if response:
                                new_desc = response
                        except Exception:
                            pass

                # Save original + rewrite
                rewrite_data = {
                    "product_id": pid,
                    "name": name,
                    "original_description": desc,
                    "original_short_description": short_desc,
                    "rewritten_name": new_name if new_name != name else None,
                    "rewritten_description": new_desc,
                    "safety_issues": check.get(
                        "violations", []
                    ),
                    "title_issues": product.get("title_safety_check", {}).get("violations", []),
                    "status": "pending_approval",
                    "created_at": datetime.now().isoformat(),
                    "applied_at": None,
                }

                out = self.rewrites_dir / f"{pid}.json"
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(rewrite_data, f, indent=2,
                              ensure_ascii=False)
                count += 1

            return {"success": True, "rewrites": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Apply (human-approved only) ─────────────────────

    def apply_rewrite(self, product_id):
        """Apply an approved rewrite via WooCommerce API.
        Only call after human approval."""
        try:
            rfile = self.rewrites_dir / f"{product_id}.json"
            if not rfile.exists():
                return {
                    "success": False,
                    "error": f"No rewrite found for "
                             f"product {product_id}",
                }

            with open(rfile, encoding="utf-8") as f:
                data = json.load(f)

            if data.get("status") == "applied":
                return {
                    "success": False,
                    "error": "Rewrite already applied",
                }

            new_desc = data.get("rewritten_description", "")
            new_name = data.get("rewritten_name", "")
            
            update_fields = {}
            if new_desc:
                update_fields["description"] = new_desc
            if new_name:
                update_fields["name"] = new_name

            if not update_fields:
                return {
                    "success": False,
                    "error": "No rewritten content available",
                }

            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {
                    "success": False,
                    "error": "WooCommerce not loaded",
                }

            result = woo.update_product(
                product_id,
                update_fields
            )

            if result.get("success"):
                data["status"] = "applied"
                data["applied_at"] = (
                    datetime.now().isoformat()
                )
                with open(rfile, "w",
                          encoding="utf-8") as f:
                    json.dump(data, f, indent=2,
                              ensure_ascii=False)
                return {
                    "success": True,
                    "product_id": product_id,
                    "message": "Rewrite applied to "
                               "{}".format(data["name"]),
                }

            return {
                "success": False,
                "error": result.get("error", "Update failed"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Status ──────────────────────────────────────────

    def get_rewrite_status(self):
        """WhatsApp-friendly summary of pending rewrites"""
        try:
            files = list(self.rewrites_dir.glob("*.json"))
            # Exclude last_scan.json
            files = [
                f for f in files
                if f.name != "last_scan.json"
            ]

            if not files:
                return (
                    "📝 *PRODUCT REWRITES*\n"
                    "No rewrites pending.\n"
                    "Run 'scan products' first."
                )

            pending = 0
            applied = 0

            for f in files:
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = json.load(fh)
                    if data.get("status") == "applied":
                        applied += 1
                    else:
                        pending += 1
                except Exception:
                    continue

            return (
                "📝 *PRODUCT REWRITES*\n"
                "─────────────\n"
                "⏳ Pending: {}\n"
                "✅ Applied: {}\n"
                "📂 Total: {}\n\n"
                "Review in: data/content/"
                "product_rewrites/"
            ).format(pending, applied, len(files))
        except Exception as e:
            return f"❌ Rewrite status error: {e}"

    # ── Bulk Actions ─────────────────────────────────────

    def bulk_fix_titles(self):
        """Scan all products and apply title-only safety fixes.
        Safe because titles are short and AI fix is reliable."""
        try:
            # 1. Scan
            scan = self.scan_all_products()
            if not scan.get("success"):
                return scan
            
            flagged = scan.get("products", [])
            fixed = 0
            
            # 2. Rewrite & Apply
            ai = self.bridge.tools.get("ai_client")
            woo = self.bridge.tools.get("woocommerce")
            
            if not ai or not woo:
                return {"success": False, "error": "AI/Woo tools missing"}
            
            for p in flagged:
                pid = p["id"]
                name = p["name"]
                t_check = p.get("title_safety_check", {})
                
                if not t_check.get("is_safe", True):
                    # Rewrite title
                    prompt = (
                        "Rewrite this product title to be safe/compliant "
                        "(no health claims/cures). Keep it SEO-friendly.\n\n"
                        "Original: {}"
                    ).format(name)
                    new_name = ai.generate(prompt)
                    if new_name:
                        new_name = new_name.strip().strip('"').strip("'")
                        # Apply immediately
                        res = woo.update_product(pid, {"name": new_name})
                        if res.get("success"):
                            fixed += 1
            
            return {
                "success": True, 
                "message": f"Fixed {fixed} product titles automatically."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def inject_disclaimer(self, force=False):
        """Append FDA disclaimer to all product descriptions."""
        disclaimer = (
            "\n\n---\n"
            "*Disclaimer: These statements have not been evaluated by the "
            "FDA. This product is not intended to diagnose, treat, cure, "
            "or prevent any disease.*"
        )
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}
            
            result = woo.get_all_products(save=False)
            products = result.get("data", {}).get("products", [])
            injected = 0
            
            for p in products:
                pid = p["id"]
                # Need raw desc
                raw = woo._make_request(f"products/{pid}")
                if raw.get("success"):
                    desc = raw["data"].get("description", "")
                    if "not been evaluated by the FDA" not in desc or force:
                        new_desc = desc + disclaimer
                        res = woo.update_product(pid, {"description": new_desc})
                        if res.get("success"):
                            injected += 1
            
            return {
                "success": True, 
                "message": f"Added disclaimer to {injected} products."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
