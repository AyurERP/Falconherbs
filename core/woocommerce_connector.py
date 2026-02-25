"""
Falcon Agency — WooCommerce Connector
Connects to falconherbs.com WooCommerce REST API
Pulls: Products, Orders, Customers, Payment Status
"""

import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class WooCommerceConnector:
    """
    Direct connection to WooCommerce REST API
    Docs: https://woocommerce.github.io/woocommerce-rest-api-docs/
    """
    
    def __init__(self, site_url=None, consumer_key=None, consumer_secret=None):
        self.site_url = site_url or os.getenv("WOO_SITE_URL", "https://falconherbs.com")
        self.consumer_key = consumer_key or os.getenv("FALCONHERBS_WC_API_KEY")
        self.consumer_secret = consumer_secret or os.getenv("FALCONHERBS_WC_API_SECRET")
        self.api_base = f"{self.site_url}/wp-json/wc/v3"
        # WordPress REST API auth (blog posts, pages, categories)
        self.wp_api_base = f"{self.site_url}/wp-json/wp/v2"
        self.wp_user = os.getenv("FALCONHERBS_WP_USER")
        # App Password preferred; falls back to regular password
        self.wp_password = (
            os.getenv("FALCONHERBS_WP_APP_PASSWORD")
            or os.getenv("FALCONHERBS_WP_PASSWORD")
        )
        self.data_dir = Path("data/woocommerce")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.consumer_key or not self.consumer_secret:
            print("⚠️ WooCommerce API keys not set!")
            print("   Set FALCONHERBS_WC_API_KEY and FALCONHERBS_WC_API_SECRET in .env")
    
    def _make_request(self, endpoint, params=None):
        """Base API request with authentication"""
        url = f"{self.api_base}/{endpoint}"
        default_params = {
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret,
            "per_page": 100
        }
        if params:
            default_params.update(params)
        
        try:
            response = requests.get(url, params=default_params, timeout=30)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to site. Is it online?"}
        except requests.exceptions.HTTPError as e:
            return {"success": False, "error": f"HTTP {e.response.status_code}: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _make_update_request(self, endpoint, data):
        """Base API PUT request with authentication"""
        url = f"{self.api_base}/{endpoint}"
        params = {
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret,
        }
        
        try:
            response = requests.put(
                url, params=params, json=data, timeout=30
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Cannot connect to site. Is it online?"
            }
        except requests.exceptions.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {str(e)}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def update_product(self, product_id, data):
        """Update a WooCommerce product via REST API.
        data is a dict with WooCommerce fields:
        name, description, short_description, etc."""
        try:
            print(
                f"  🔄 Updating product {product_id}: "
                f"{list(data.keys())}"
            )
            result = self._make_update_request(
                f"products/{product_id}", data
            )
            if result.get("success"):
                return {
                    "success": True,
                    "product_id": product_id,
                    "updated_fields": list(data.keys()),
                }
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== WORDPRESS REST API ====================

    def _make_wp_request(self, endpoint, params=None):
        """WordPress REST API GET — uses Basic Auth (WP user + password)."""
        import base64
        url = f"{self.wp_api_base}/{endpoint}"
        headers = {}
        if self.wp_user and self.wp_password:
            token = base64.b64encode(
                f"{self.wp_user}:{self.wp_password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {token}"
        try:
            response = requests.get(
                url, params=params or {}, headers=headers, timeout=30
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to site."}
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 401:
                return {
                    "success": False,
                    "error": (
                        "HTTP 401: WP auth failed. "
                        "Generate an Application Password in "
                        "WP Admin > Users > Profile > Application Passwords "
                        "and add FALCONHERBS_WP_APP_PASSWORD to .env"
                    ),
                }
            return {"success": False, "error": f"HTTP {code}: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _make_wp_update(self, endpoint, data, method="PUT"):
        """WordPress REST API write — uses Basic Auth."""
        import base64
        url = f"{self.wp_api_base}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        if self.wp_user and self.wp_password:
            token = base64.b64encode(
                f"{self.wp_user}:{self.wp_password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {token}"
        try:
            fn = requests.post if method == "POST" else requests.put
            response = fn(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 401:
                return {
                    "success": False,
                    "error": (
                        "HTTP 401: WP auth failed. "
                        "Add FALCONHERBS_WP_APP_PASSWORD to .env"
                    ),
                }
            return {"success": False, "error": f"HTTP {code}: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_posts(self, per_page=100, status="publish"):
        """Fetch all published blog posts via WP REST API."""
        all_posts = []
        page = 1
        while True:
            result = self._make_wp_request(
                "posts",
                {"per_page": per_page, "page": page, "status": status},
            )
            if not result["success"]:
                return result
            batch = result["data"]
            if not batch:
                break
            all_posts.extend(batch)
            page += 1
            if len(batch) < per_page:
                break
        return {"success": True, "data": all_posts, "total": len(all_posts)}

    def update_post(self, post_id, data):
        """Update a blog post via WP REST API.
        data: dict with 'title', 'content', or 'excerpt' keys."""
        result = self._make_wp_update(f"posts/{post_id}", data)
        if result.get("success"):
            return {
                "success": True,
                "post_id": post_id,
                "updated_fields": list(data.keys()),
            }
        return result

    def get_pages(self, status="publish"):
        """Fetch all WP pages."""
        result = self._make_wp_request(
            "pages", {"per_page": 100, "status": status}
        )
        if not result["success"]:
            return result
        return {
            "success": True,
            "data": result["data"],
            "total": len(result["data"]),
        }

    def update_page(self, page_id, data):
        """Update a WP page via REST API."""
        result = self._make_wp_update(f"pages/{page_id}", data)
        if result.get("success"):
            return {
                "success": True,
                "page_id": page_id,
                "updated_fields": list(data.keys()),
            }
        return result

    def get_wc_categories(self):
        """Fetch all WooCommerce product categories."""
        all_cats = []
        page = 1
        while True:
            result = self._make_request(
                "products/categories", {"per_page": 100, "page": page}
            )
            if not result["success"]:
                return result
            batch = result["data"]
            if not batch:
                break
            all_cats.extend(batch)
            page += 1
            if len(batch) < 100:
                break
        return {"success": True, "data": all_cats, "total": len(all_cats)}

    def update_wc_category(self, cat_id, data):
        """Rename or update a WooCommerce product category."""
        result = self._make_update_request(f"products/categories/{cat_id}", data)
        if result.get("success"):
            return {
                "success": True,
                "category_id": cat_id,
                "updated_fields": list(data.keys()),
            }
        return result

    # ==================== PRODUCTS ====================

    def get_all_products(self, save=True):
        """Fetch all products with pagination"""
        all_products = []
        page = 1
        
        while True:
            result = self._make_request("products", {"page": page, "per_page": 100})
            if not result["success"]:
                return result
            
            products = result["data"]
            if not products:
                break
            
            all_products.extend(products)
            page += 1
            
            if len(products) < 100:
                break
        
        summary = {
            "total_products": len(all_products),
            "fetched_at": datetime.now().isoformat(),
            "products": []
        }
        
        for p in all_products:
            product_info = {
                "id": p.get("id"),
                "name": p.get("name"),
                "slug": p.get("slug"),
                "status": p.get("status"),  # publish, draft, private
                "price": p.get("price"),
                "regular_price": p.get("regular_price"),
                "sale_price": p.get("sale_price"),
                "stock_status": p.get("stock_status"),
                "stock_quantity": p.get("stock_quantity"),
                "categories": [c["name"] for c in p.get("categories", [])],
                "tags": [t["name"] for t in p.get("tags", [])],
                "description_length": len(p.get("description", "")),
                "short_description_length": len(p.get("short_description", "")),
                "images_count": len(p.get("images", [])),
                "permalink": p.get("permalink"),
                "total_sales": p.get("total_sales", 0),
                "average_rating": p.get("average_rating"),
                "rating_count": p.get("rating_count", 0),
            }
            summary["products"].append(product_info)
        
        if save:
            self._save_data("products.json", summary)
        
        return {"success": True, "data": summary}
    
    def get_product_issues(self):
        """Find products with problems"""
        result = self.get_all_products(save=False)
        if not result["success"]:
            return result
        
        issues = {
            "no_price": [],
            "no_image": [],
            "short_description_missing": [],
            "description_too_short": [],
            "out_of_stock": [],
            "draft_status": [],
            "no_categories": [],
        }
        
        for p in result["data"]["products"]:
            if not p["price"]:
                issues["no_price"].append(p["name"])
            if p["images_count"] == 0:
                issues["no_image"].append(p["name"])
            if p["short_description_length"] < 10:
                issues["short_description_missing"].append(p["name"])
            if p["description_length"] < 100:
                issues["description_too_short"].append(p["name"])
            if p["stock_status"] == "outofstock":
                issues["out_of_stock"].append(p["name"])
            if p["status"] != "publish":
                issues["draft_status"].append(p["name"])
            if not p["categories"]:
                issues["no_categories"].append(p["name"])
        
        total_issues = sum(len(v) for v in issues.values())
        
        return {
            "success": True,
            "total_issues": total_issues,
            "issues": issues
        }
    
    # ==================== ORDERS ====================
    
    def get_orders(self, days_back=365, save=True):
        """Fetch orders from last N days"""
        after_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        all_orders = []
        page = 1
        
        while True:
            result = self._make_request("orders", {
                "page": page,
                "per_page": 100,
                "after": after_date,
                "orderby": "date",
                "order": "desc"
            })
            if not result["success"]:
                return result
            
            orders = result["data"]
            if not orders:
                break
            
            all_orders.extend(orders)
            page += 1
            
            if len(orders) < 100:
                break
        
        summary = {
            "total_orders": len(all_orders),
            "period": f"Last {days_back} days",
            "fetched_at": datetime.now().isoformat(),
            "revenue": {
                "total": 0,
                "currency": "INR",
                "average_order_value": 0
            },
            "status_breakdown": {},
            "country_breakdown": {},
            "monthly_breakdown": {},
            "orders": []
        }
        
        for o in all_orders:
            order_info = {
                "id": o.get("id"),
                "status": o.get("status"),
                "total": float(o.get("total", 0)),
                "currency": o.get("currency"),
                "date": o.get("date_created"),
                "customer_email": o.get("billing", {}).get("email"),
                "country": o.get("billing", {}).get("country"),
                "city": o.get("billing", {}).get("city"),
                "payment_method": o.get("payment_method"),
                "payment_method_title": o.get("payment_method_title"),
                "items": [
                    {"name": item["name"], "quantity": item["quantity"], 
                     "total": item["total"]}
                    for item in o.get("line_items", [])
                ],
                "shipping_total": o.get("shipping_total"),
            }
            summary["orders"].append(order_info)
            
            # Aggregations
            status = o.get("status", "unknown")
            summary["status_breakdown"][status] = \
                summary["status_breakdown"].get(status, 0) + 1
            
            country = o.get("billing", {}).get("country", "Unknown")
            summary["country_breakdown"][country] = \
                summary["country_breakdown"].get(country, 0) + 1
            
            month = o.get("date_created", "")[:7]  # YYYY-MM
            if month not in summary["monthly_breakdown"]:
                summary["monthly_breakdown"][month] = {
                    "orders": 0, "revenue": 0
                }
            summary["monthly_breakdown"][month]["orders"] += 1
            summary["monthly_breakdown"][month]["revenue"] += \
                float(o.get("total", 0))
            
            summary["revenue"]["total"] += float(o.get("total", 0))
        
        if all_orders:
            summary["revenue"]["average_order_value"] = \
                round(summary["revenue"]["total"] / len(all_orders), 2)
        
        if save:
            self._save_data("orders.json", summary)
        
        return {"success": True, "data": summary}
    
    # ==================== CUSTOMERS ====================
    
    def get_customers(self, save=True):
        """Fetch all customers"""
        all_customers = []
        page = 1
        
        while True:
            result = self._make_request("customers", {
                "page": page, "per_page": 100
            })
            if not result["success"]:
                return result
            
            customers = result["data"]
            if not customers:
                break
            
            all_customers.extend(customers)
            page += 1
            
            if len(customers) < 100:
                break
        
        summary = {
            "total_customers": len(all_customers),
            "fetched_at": datetime.now().isoformat(),
            "country_breakdown": {},
            "customers": []
        }
        
        for c in all_customers:
            customer_info = {
                "id": c.get("id"),
                "email": c.get("email"),
                "first_name": c.get("first_name"),
                "last_name": c.get("last_name"),
                "country": c.get("billing", {}).get("country"),
                "city": c.get("billing", {}).get("city"),
                "orders_count": c.get("orders_count", 0),
                "total_spent": c.get("total_spent", "0"),
                "date_registered": c.get("date_created"),
            }
            summary["customers"].append(customer_info)
            
            country = c.get("billing", {}).get("country", "Unknown")
            summary["country_breakdown"][country] = \
                summary["country_breakdown"].get(country, 0) + 1
        
        if save:
            self._save_data("customers.json", summary)
        
        return {"success": True, "data": summary}
    
    # ==================== PAYMENT GATEWAYS ====================
    
    def get_payment_gateways(self, save=True):
        """Check which payment methods are active"""
        result = self._make_request("payment_gateways")
        if not result["success"]:
            return result
        
        gateways = []
        for g in result["data"]:
            gateway_info = {
                "id": g.get("id"),
                "title": g.get("title"),
                "description": g.get("description"),
                "enabled": g.get("enabled"),
                "method_title": g.get("method_title"),
            }
            gateways.append(gateway_info)
        
        active = [g for g in gateways if g["enabled"]]
        inactive = [g for g in gateways if not g["enabled"]]
        
        summary = {
            "total_gateways": len(gateways),
            "active": len(active),
            "inactive": len(inactive),
            "active_gateways": active,
            "inactive_gateways": inactive,
            "fetched_at": datetime.now().isoformat()
        }
        
        if save:
            self._save_data("payment_gateways.json", summary)
        
        return {"success": True, "data": summary}
    
    # ==================== STORE HEALTH ====================
    
    def full_store_audit(self):
        """Complete store health check — Run this FIRST"""
        print("🔍 Starting full store audit...")
        
        audit = {
            "audit_date": datetime.now().isoformat(),
            "site": self.site_url,
            "sections": {}
        }
        
        # 1. Products
        print("  📦 Checking products...")
        products = self.get_all_products()
        if products["success"]:
            issues = self.get_product_issues()
            audit["sections"]["products"] = {
                "total": products["data"]["total_products"],
                "issues": issues.get("data", {}) if issues["success"] else "Error"
            }
        else:
            audit["sections"]["products"] = {"error": products["error"]}
        
        # 2. Orders
        print("  🛒 Checking orders...")
        orders = self.get_orders(days_back=730)  # 2 years back
        if orders["success"]:
            audit["sections"]["orders"] = {
                "total": orders["data"]["total_orders"],
                "revenue": orders["data"]["revenue"],
                "by_country": orders["data"]["country_breakdown"],
                "by_month": orders["data"]["monthly_breakdown"],
                "by_status": orders["data"]["status_breakdown"]
            }
        else:
            audit["sections"]["orders"] = {"error": orders["error"]}
        
        # 3. Customers
        print("  👥 Checking customers...")
        customers = self.get_customers()
        if customers["success"]:
            audit["sections"]["customers"] = {
                "total": customers["data"]["total_customers"],
                "by_country": customers["data"]["country_breakdown"]
            }
        else:
            audit["sections"]["customers"] = {"error": customers["error"]}
        
        # 4. Payment Gateways
        print("  💳 Checking payment gateways...")
        payments = self.get_payment_gateways()
        if payments["success"]:
            audit["sections"]["payments"] = payments["data"]
        else:
            audit["sections"]["payments"] = {"error": payments["error"]}
        
        # 5. Site Status
        print("  🌐 Checking site status...")
        try:
            r = requests.get(self.site_url, timeout=15)
            audit["sections"]["site_status"] = {
                "online": True,
                "status_code": r.status_code,
                "response_time_ms": round(r.elapsed.total_seconds() * 1000),
                "ssl": self.site_url.startswith("https"),
                "redirect": r.url != self.site_url,
                "final_url": r.url
            }
        except Exception as e:
            audit["sections"]["site_status"] = {
                "online": False,
                "error": str(e)
            }
        
        self._save_data("full_audit.json", audit)
        
        # Generate WhatsApp-friendly summary
        summary = self._generate_audit_summary(audit)
        
        print("✅ Audit complete!")
        print(summary)
        
        return {"success": True, "data": audit, "summary": summary}
    
    def _generate_audit_summary(self, audit):
        """Human-readable audit summary for WhatsApp"""
        lines = [
            "🦅 *FALCON HERBS — STORE AUDIT*",
            f"📅 {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            "─" * 30,
        ]
        
        # Site Status
        site = audit["sections"].get("site_status", {})
        if site.get("online"):
            lines.append(
                f"🌐 Site: ✅ Online "
                f"({site.get('response_time_ms')}ms)"
            )
            lines.append(
                f"🔒 SSL: {'✅' if site.get('ssl') else '❌ NOT SECURE!'}"
            )
        else:
            lines.append(f"🌐 Site: ❌ OFFLINE — {site.get('error')}")
        
        # Products
        products = audit["sections"].get("products", {})
        if "total" in products:
            lines.append(f"\n📦 *Products:* {products['total']}")
            if isinstance(products.get("issues"), dict):
                total_issues = products["issues"].get("total_issues", 0)
                lines.append(f"   Issues found: {total_issues}")
                if total_issues > 0:
                    for issue_type, items in \
                            products["issues"].get("issues", {}).items():
                        if items:
                            lines.append(
                                f"   ⚠️ {issue_type}: {len(items)} products"
                            )
        
        # Orders
        orders = audit["sections"].get("orders", {})
        if "total" in orders:
            lines.append(f"\n🛒 *Orders (Last 2 Years):* {orders['total']}")
            rev = orders.get("revenue", {})
            lines.append(
                f"   💰 Total Revenue: "
                f"₹{rev.get('total', 0):,.0f}"
            )
            lines.append(
                f"   📊 Avg Order Value: "
                f"₹{rev.get('average_order_value', 0):,.0f}"
            )
            if orders.get("by_country"):
                top_countries = sorted(
                    orders["by_country"].items(),
                    key=lambda x: x[1], reverse=True
                )[:5]
                lines.append("   🌍 Top Countries:")
                for country, count in top_countries:
                    lines.append(f"      {country}: {count} orders")
        
        # Customers
        customers = audit["sections"].get("customers", {})
        if "total" in customers:
            lines.append(
                f"\n👥 *Total Customers:* {customers['total']}"
            )
        
        # Payments
        payments = audit["sections"].get("payments", {})
        if "active" in payments:
            lines.append(
                f"\n💳 *Payment Gateways:* "
                f"{payments['active']} active"
            )
            for g in payments.get("active_gateways", []):
                lines.append(f"   ✅ {g['title']}")
            if payments["active"] == 0:
                lines.append(
                    "   ❌ NO ACTIVE PAYMENT METHOD! "
                    "Customers CANNOT pay!"
                )
        
        lines.append("\n" + "─" * 30)
        lines.append("🤖 _Falcon Agency — Automated Audit_")
        
        return "\n".join(lines)
    
    def _save_data(self, filename, data):
        """Save data to JSON"""
        filepath = self.data_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  💾 Saved: {filepath}")


# ==================== QUICK SETUP GUIDE ====================

def setup_woocommerce_keys():
    """
    HOW TO GET WOOCOMMERCE API KEYS:
    
    1. Login to falconherbs.com/wp-admin
    2. Go to: WooCommerce → Settings → Advanced → REST API
    3. Click: "Add Key"
    4. Description: "Falcon Agency"
    5. User: Your admin user
    6. Permissions: "Read" (start with read-only!)
    7. Click: "Generate API Key"
    8. Copy Consumer Key and Consumer Secret
    9. Add to your .env file:
       WOO_SITE_URL=https://falconherbs.com
       FALCONHERBS_WC_API_KEY=ck_xxxxxxxxxxxx
       FALCONHERBS_WC_API_SECRET=cs_xxxxxxxxxxxx
    
    ⚠️ IMPORTANT: Start with READ ONLY permission!
    We upgrade to Read/Write only when needed.
    """
    print(setup_woocommerce_keys.__doc__)


# ==================== STANDALONE TEST ====================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    woo = WooCommerceConnector()
    
    if not woo.consumer_key:
        print("\n⚠️ API keys not configured!")
        setup_woocommerce_keys()
    else:
        print("\n🚀 Running full store audit...")
        result = woo.full_store_audit()
        if result["success"]:
            print("\n✅ Audit complete! Check data/woocommerce/ folder")
        else:
            print(f"\n❌ Audit failed: {result.get('error')}")
