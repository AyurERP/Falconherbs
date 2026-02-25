"""
Falcon Agency -- Health Claims Rewriter
Scans all WooCommerce products for health claim violations,
AI-rewrites them using safe Ayurvedic language,
saves for approval. NEVER auto-applies.
"""

import html as html_module
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

                # Use descriptions already fetched by get_all_products()
                # NO individual API call per product (was 87×10s = 14 min!)
                desc = p.get("description", "")
                short_desc = p.get("short_description", "")

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

    # ── Bulk push (Task 4) ───────────────────────────────

    def push_all_rewrites(self):
        """
        Apply all pending rewrites to WooCommerce.
        Records every change in ChangelogManager.
        Returns { success, summary, report_path, applied, failed, errors }.
        """
        try:
            from core.changelog_manager import ChangelogManager

            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {
                    "success": False,
                    "error": "WooCommerce not loaded",
                    "summary": "❌ WooCommerce not connected.",
                }

            files = [
                f for f in self.rewrites_dir.glob("*.json")
                if f.name != "last_scan.json"
            ]
            pending = []
            for f in files:
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = json.load(fh)
                    if data.get("status") != "applied":
                        pending.append((int(f.stem), data))
                except Exception:
                    continue

            if not pending:
                return {
                    "success": True,
                    "summary": "✅ No pending rewrites. All done!",
                    "report_path": None,
                    "applied": 0,
                    "failed": 0,
                    "errors": [],
                }

            cm = ChangelogManager()
            applied = 0
            failed = 0
            errors = []

            for pid, data in pending:
                try:
                    # Get BEFORE from WooCommerce
                    raw = woo._make_request(f"products/{pid}")
                    if not raw.get("success"):
                        errors.append(f"Product {pid}: fetch failed")
                        failed += 1
                        continue

                    prod = raw["data"]
                    name = prod.get("name", "")
                    before_desc = prod.get("description", "")
                    before_name = prod.get("name", "")

                    new_desc = data.get("rewritten_description", "")
                    new_name = data.get("rewritten_name", "")

                    update_fields = {}
                    if new_desc:
                        update_fields["description"] = new_desc
                    if new_name:
                        update_fields["name"] = new_name

                    if not update_fields:
                        errors.append(f"{name}: no rewritten content")
                        failed += 1
                        continue

                    result = woo.update_product(pid, update_fields)

                    if result.get("success"):
                        if "description" in update_fields:
                            cm.record(
                                "product", pid, name,
                                field="description",
                                before=before_desc,
                                after=new_desc,
                            )
                        if "name" in update_fields:
                            cm.record(
                                "product", pid, name,
                                field="name",
                                before=before_name,
                                after=new_name,
                            )
                        data["status"] = "applied"
                        data["applied_at"] = datetime.now().isoformat()
                        rfile = self.rewrites_dir / f"{pid}.json"
                        with open(rfile, "w", encoding="utf-8") as fh:
                            json.dump(data, fh, indent=2, ensure_ascii=False)
                        applied += 1
                    else:
                        errors.append(f"{name}: {result.get('error', 'update failed')}")
                        failed += 1

                except Exception as e:
                    errors.append(f"Product {pid}: {str(e)[:100]}")
                    failed += 1

            report_path = None
            if cm.change_count > 0:
                report_path = cm.save_report(
                    title="FALCON AGENCY — PRODUCT REWRITE REPORT"
                )

            summary = cm.get_whatsapp_summary("Product Rewrites")
            if errors:
                summary += "\n\n⚠️ *Errors:*\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    summary += f"\n... and {len(errors) - 5} more"

            return {
                "success": applied > 0,
                "summary": summary,
                "report_path": str(report_path) if report_path else None,
                "applied": applied,
                "failed": failed,
                "errors": errors,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": f"❌ Push failed: {e}",
                "report_path": None,
                "applied": 0,
                "failed": 0,
                "errors": [str(e)],
            }

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

    # ── Blog Posts ───────────────────────────────────────

    def scan_blog_posts(self):
        """Scan all blog posts for health claim violations.
        Returns {total, flagged, posts: [...]}"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            pipeline = self.bridge.tools.get("content")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}
            if not pipeline:
                return {"success": False, "error": "Content Pipeline missing"}

            result = woo.get_posts()
            if not result.get("success"):
                return result

            posts = result["data"]
            flagged = []
            for post in posts:
                pid = post.get("id")
                title_raw = post.get("title", {})
                title = html_module.unescape(
                    title_raw.get("rendered", "")
                    if isinstance(title_raw, dict)
                    else str(title_raw)
                )
                content_raw = post.get("content", {})
                content = html_module.unescape(
                    content_raw.get("rendered", "")
                    if isinstance(content_raw, dict)
                    else str(content_raw)
                )
                excerpt_raw = post.get("excerpt", {})
                excerpt = html_module.unescape(
                    excerpt_raw.get("rendered", "")
                    if isinstance(excerpt_raw, dict)
                    else str(excerpt_raw)
                )

                combined = f"{title} {excerpt}".strip()
                check = pipeline.safety_check(combined) if combined else {"is_safe": True}

                if not check.get("is_safe", True):
                    flagged.append({
                        "id": pid,
                        "title": title,
                        "link": post.get("link", ""),
                        "content_preview": content[:300],
                        "safety_check": check,
                    })

            # Save
            blog_scan_file = self.rewrites_dir / "blog_scan.json"
            scan_data = {
                "scanned_at": datetime.now().isoformat(),
                "total": len(posts),
                "flagged": len(flagged),
                "posts": flagged,
            }
            with open(blog_scan_file, "w", encoding="utf-8") as f:
                json.dump(scan_data, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "total": len(posts),
                "flagged": len(flagged),
                "posts": flagged,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rewrite_blog_post(self, post_id=None):
        """AI-rewrite flagged blog posts using safe language.
        Saves to product_rewrites/blog_{id}.json for approval.
        If post_id given, rewrites only that post."""
        try:
            blog_scan_file = self.rewrites_dir / "blog_scan.json"
            if not blog_scan_file.exists():
                return {
                    "success": False,
                    "error": "No blog scan results. Run scan_blog_posts() first.",
                }

            with open(blog_scan_file, encoding="utf-8") as f:
                scan_data = json.load(f)

            flagged = scan_data.get("posts", [])
            if post_id:
                flagged = [p for p in flagged if p["id"] == post_id]

            ai = self.bridge.tools.get("ai_client")
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}

            count = 0
            for post in flagged:
                pid = post["id"]
                title = post["title"]
                content_preview = post.get("content_preview", "")

                new_title = title
                if ai:
                    try:
                        prompt = (
                            "Rewrite this blog post title to remove any health claims "
                            "(cures, treats, controls, reverses, heals, etc). "
                            "Keep it informative and SEO-friendly.\n\n"
                            f"Original title: {title}"
                        )
                        resp = ai.generate(prompt)
                        if resp:
                            new_title = resp.strip().strip('"').strip("'")
                    except Exception:
                        pass

                rewrite_data = {
                    "type": "blog_post",
                    "post_id": pid,
                    "original_title": title,
                    "rewritten_title": new_title,
                    "link": post.get("link", ""),
                    "safety_issues": post.get("safety_check", {}).get("violations", []),
                    "status": "pending_approval",
                    "created_at": datetime.now().isoformat(),
                    "applied_at": None,
                    "note": (
                        "Title rewritten. Full content review needed in WP Admin."
                    ),
                }
                out = self.rewrites_dir / f"blog_{pid}.json"
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(rewrite_data, f, indent=2, ensure_ascii=False)
                count += 1

            return {"success": True, "rewrites": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_blog_fix(self, post_id):
        """Apply an approved blog post title fix via WP REST API."""
        try:
            rfile = self.rewrites_dir / f"blog_{post_id}.json"
            if not rfile.exists():
                return {
                    "success": False,
                    "error": f"No rewrite found for post {post_id}",
                }

            with open(rfile, encoding="utf-8") as f:
                data = json.load(f)

            if data.get("status") == "applied":
                return {"success": False, "error": "Already applied"}

            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}

            update_data = {}
            new_title = data.get("rewritten_title", "")
            if new_title and new_title != data.get("original_title", ""):
                update_data["title"] = new_title

            if not update_data:
                return {"success": False, "error": "Nothing to update"}

            result = woo.update_post(post_id, update_data)
            if result.get("success"):
                data["status"] = "applied"
                data["applied_at"] = datetime.now().isoformat()
                with open(rfile, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return {
                    "success": True,
                    "post_id": post_id,
                    "message": f"Blog post title updated: {new_title}",
                }
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def push_all_blog_fixes(self):
        """Apply all pending blog post title rewrites. Returns {success, applied, failed, errors}."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {
                    "success": False,
                    "error": "WooCommerce tool missing",
                    "applied": 0,
                    "failed": 0,
                    "errors": [],
                }
            from core.changelog_manager import ChangelogManager
            cm = ChangelogManager()
            applied = 0
            failed = 0
            errors = []
            for rfile in self.rewrites_dir.glob("blog_*.json"):
                try:
                    with open(rfile, encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("status") == "applied":
                        continue
                    pid = data.get("post_id")
                    if not pid:
                        continue
                    new_title = data.get("rewritten_title", "")
                    old_title = data.get("original_title", "")
                    if not new_title or new_title == old_title:
                        errors.append(f"Blog {pid}: no change")
                        failed += 1
                        continue
                    result = woo.update_post(pid, {"title": new_title})
                    if result.get("success"):
                        data["status"] = "applied"
                        data["applied_at"] = datetime.now().isoformat()
                        with open(rfile, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        cm.record("blog_post", pid, old_title, field="title", before=old_title, after=new_title)
                        applied += 1
                    else:
                        errors.append(f"Blog {pid}: {result.get('error', 'update failed')}")
                        failed += 1
                except Exception as e:
                    errors.append(f"Blog {rfile.stem}: {str(e)[:80]}")
                    failed += 1
            summary = cm.get_whatsapp_summary("Blog Title Fixes") if applied > 0 else ""
            if not summary and applied == 0 and failed == 0:
                summary = "No pending blog rewrites."
            elif applied > 0:
                summary = f"Blogs updated: {applied}. " + summary
            if errors:
                summary += "\n\nErrors: " + "; ".join(errors[:5])
            report_path = None
            if cm.change_count > 0:
                report_path = cm.save_report(title="FALCON AGENCY — BLOG REWRITE REPORT")
            return {
                "success": applied > 0,
                "summary": summary,
                "report_path": str(report_path) if report_path else None,
                "applied": applied,
                "failed": failed,
                "errors": errors,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": f"Push failed: {e}",
                "applied": 0,
                "failed": 0,
                "errors": [str(e)],
            }

    # ── Pages ────────────────────────────────────────────

    def scan_pages(self):
        """Scan all WP pages for health claim violations."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            pipeline = self.bridge.tools.get("content")
            if not woo or not pipeline:
                return {"success": False, "error": "Tools missing"}

            result = woo.get_pages()
            if not result.get("success"):
                return result

            pages = result["data"]
            flagged = []
            for page in pages:
                pid = page.get("id")
                title_raw = page.get("title", {})
                title = (
                    title_raw.get("rendered", "")
                    if isinstance(title_raw, dict)
                    else str(title_raw)
                )
                content_raw = page.get("content", {})
                content = (
                    content_raw.get("rendered", "")
                    if isinstance(content_raw, dict)
                    else str(content_raw)
                )
                check = pipeline.safety_check(f"{title} {content[:500]}")
                if not check.get("is_safe", True):
                    flagged.append({
                        "id": pid,
                        "title": title,
                        "link": page.get("link", ""),
                        "safety_check": check,
                    })

            page_scan_file = self.rewrites_dir / "page_scan.json"
            scan_data = {
                "scanned_at": datetime.now().isoformat(),
                "total": len(pages),
                "flagged": len(flagged),
                "pages": flagged,
            }
            with open(page_scan_file, "w", encoding="utf-8") as f:
                json.dump(scan_data, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "total": len(pages),
                "flagged": len(flagged),
                "pages": flagged,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rewrite_pages(self):
        """AI-rewrite flagged page titles. Saves to page_{id}.json."""
        try:
            page_scan_file = self.rewrites_dir / "page_scan.json"
            if not page_scan_file.exists():
                return {"success": False, "error": "Run scan_pages() first."}
            with open(page_scan_file, encoding="utf-8") as f:
                scan_data = json.load(f)
            flagged = scan_data.get("pages", [])
            if not flagged:
                return {"success": True, "rewrites": 0}
            ai = self.bridge.tools.get("ai_client")
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}
            count = 0
            for page in flagged:
                pid = page["id"]
                title = page["title"]
                new_title = title
                if ai:
                    try:
                        prompt = (
                            "Rewrite this page title to remove health claims. "
                            "Keep it informative.\n\nOriginal: " + title
                        )
                        resp = ai.generate(prompt)
                        if resp:
                            new_title = resp.strip().strip('"').strip("'")
                    except Exception:
                        pass
                rewrite_data = {
                    "type": "page",
                    "page_id": pid,
                    "original_title": title,
                    "rewritten_title": new_title,
                    "status": "pending_approval",
                    "created_at": datetime.now().isoformat(),
                }
                out = self.rewrites_dir / f"page_{pid}.json"
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(rewrite_data, f, indent=2, ensure_ascii=False)
                count += 1
            return {"success": True, "rewrites": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_page_fix(self, page_id):
        """Apply single page title fix."""
        try:
            rfile = self.rewrites_dir / f"page_{page_id}.json"
            if not rfile.exists():
                return {"success": False, "error": f"No rewrite for page {page_id}"}
            with open(rfile, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") == "applied":
                return {"success": False, "error": "Already applied"}
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}
            new_title = data.get("rewritten_title", "")
            if not new_title:
                return {"success": False, "error": "No rewritten title"}
            result = woo.update_page(page_id, {"title": new_title})
            if result.get("success"):
                data["status"] = "applied"
                data["applied_at"] = datetime.now().isoformat()
                with open(rfile, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return {"success": True, "page_id": page_id, "message": f"Page updated: {new_title}"}
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def push_all_page_fixes(self):
        """Apply all pending page title rewrites."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing", "applied": 0, "failed": 0, "errors": []}
            from core.changelog_manager import ChangelogManager
            cm = ChangelogManager()
            applied = 0
            failed = 0
            errors = []
            for rfile in self.rewrites_dir.glob("page_*.json"):
                try:
                    with open(rfile, encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("status") == "applied":
                        continue
                    pid = data.get("page_id")
                    if not pid:
                        continue
                    new_title = data.get("rewritten_title", "")
                    old_title = data.get("original_title", "")
                    if not new_title:
                        continue
                    result = woo.update_page(pid, {"title": new_title})
                    if result.get("success"):
                        data["status"] = "applied"
                        data["applied_at"] = datetime.now().isoformat()
                        with open(rfile, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        cm.record("page", pid, old_title, field="title", before=old_title, after=new_title)
                        applied += 1
                    else:
                        errors.append(f"Page {pid}: {result.get('error')}")
                        failed += 1
                except Exception as e:
                    errors.append(f"Page {rfile.stem}: {str(e)[:80]}")
                    failed += 1
            summary = cm.get_whatsapp_summary("Page Fixes") if applied > 0 else ""
            if not summary and applied == 0 and failed == 0:
                summary = "No pending page rewrites."
            elif applied > 0:
                summary = f"Pages updated: {applied}. " + summary
            report_path = None
            if cm.change_count > 0:
                report_path = cm.save_report(title="FALCON AGENCY — PAGE REWRITE REPORT")
            return {
                "success": applied > 0,
                "summary": summary,
                "report_path": str(report_path) if report_path else None,
                "applied": applied,
                "failed": failed,
                "errors": errors,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "applied": 0, "failed": 0, "errors": [str(e)]}

    # ── Categories ───────────────────────────────────────

    # Risky category name → safe replacement
    RISKY_CATEGORY_NAMES = {
        # Medical condition names (direct disease references)
        "Diabetic Teas": "Wellness Teas",
        "Diabetic Tea": "Wellness Teas",
        "Diabetes Management": "Wellness Support",
        "Blood Sugar Control": "Metabolic Wellness",
        "Diabetic": "Wellness",
        # Cardiovascular
        "Heart Health": "Cardiovascular Wellness",
        "Cardiovascular": "Cardiovascular Wellness",
        # Immunity
        "Immune Boost": "Immunity Support",
        "Immune Booster": "Immunity Support",
        # Weight
        "Weight Loss": "Weight Management",
        "Fat Burner": "Wellness Blends",
        # Detox / cure / treatment
        "Detox": "Cleansing Blends",
        "Cure": "Natural Remedies",
        "Treatment": "Traditional Support",
        # Mental health condition names
        "Stress, Anxiety & Depression": "Calm & Balance",
        "Stress Anxiety Depression": "Calm & Balance",
        # Inflammation / pain (medical claim)
        "Inflammation, Swelling & Body Pain": "Joint & Muscle Wellness",
        "Inflammation": "Natural Wellness",
        # Digestion problems
        "Digestion Problems": "Digestive Wellness",
    }

    def scan_categories(self):
        """Scan WooCommerce categories for risky names."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}

            result = woo.get_wc_categories()
            if not result.get("success"):
                return result

            cats = result["data"]
            flagged = []
            for cat in cats:
                cid = cat.get("id")
                raw_name = cat.get("name", "")
                # Decode HTML entities (&amp; → &, etc.)
                name = html_module.unescape(raw_name)
                # Check exact and partial match
                suggested = None
                for risky, safe in self.RISKY_CATEGORY_NAMES.items():
                    if risky.lower() in name.lower():
                        suggested = name.lower().replace(
                            risky.lower(), safe.lower()
                        ).title()
                        break
                if suggested:
                    flagged.append({
                        "id": cid,
                        "name": name,
                        "suggested": suggested,
                        "count": cat.get("count", 0),
                    })

            cat_scan_file = self.rewrites_dir / "category_scan.json"
            scan_data = {
                "scanned_at": datetime.now().isoformat(),
                "total": len(cats),
                "flagged": len(flagged),
                "categories": flagged,
            }
            with open(cat_scan_file, "w", encoding="utf-8") as f:
                json.dump(scan_data, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "total": len(cats),
                "flagged": len(flagged),
                "categories": flagged,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_category(self, cat_id, new_name=None):
        """Rename a single WooCommerce category.
        If new_name not given, uses suggested name from last scan."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}

            if not new_name:
                # Load from scan file
                cat_scan_file = self.rewrites_dir / "category_scan.json"
                if cat_scan_file.exists():
                    with open(cat_scan_file, encoding="utf-8") as f:
                        scan_data = json.load(f)
                    for cat in scan_data.get("categories", []):
                        if cat["id"] == cat_id:
                            new_name = cat["suggested"]
                            break
                if not new_name:
                    return {
                        "success": False,
                        "error": "No new name provided and no scan data found",
                    }

            result = woo.update_wc_category(cat_id, {"name": new_name})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_all_risky_categories(self, dry_run=True):
        """Scan and rename all risky category names.
        dry_run=True: shows what would change without applying.
        dry_run=False: applies renames immediately."""
        try:
            scan = self.scan_categories()
            if not scan.get("success"):
                return scan

            flagged = scan.get("categories", [])
            if not flagged:
                return {
                    "success": True,
                    "message": "No risky category names found.",
                    "renamed": 0,
                }

            if dry_run:
                lines = ["📋 *CATEGORY RENAME PREVIEW* (dry run)\n"]
                for cat in flagged:
                    lines.append(
                        f"  • '{cat['name']}' → '{cat['suggested']}' "
                        f"({cat['count']} products)"
                    )
                lines.append("\nSend 'rename categories' to apply.")
                return {
                    "success": True,
                    "dry_run": True,
                    "flagged": len(flagged),
                    "preview": "\n".join(lines),
                }

            renamed = 0
            errors = []
            for cat in flagged:
                res = self.rename_category(cat["id"], cat["suggested"])
                if res.get("success"):
                    renamed += 1
                else:
                    errors.append(f"{cat['name']}: {res.get('error')}")

            return {
                "success": True,
                "renamed": renamed,
                "errors": errors,
                "message": f"Renamed {renamed}/{len(flagged)} categories.",
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
