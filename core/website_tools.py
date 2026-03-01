"""Website Tools — Crawl, Search, Scan for Health Claims"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin, urlparse
import json

class WebsiteTools:
    """Real website interaction tools"""
    
    def __init__(self, base_url: str = "https://falconherbs.com"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'FalconAgency/1.0 (Website Audit Bot)'
        })
        self.timeout = 15
    
    def set_site(self, url: str) -> None:
        """Change target website"""
        self.base_url = url.rstrip('/')
    
    def crawl_all_pages(self, max_pages: int = 50) -> List[Dict]:
        """Crawl entire website and extract content"""
        visited = set()
        to_visit = [self.base_url]
        pages = []
        
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                    element.decompose()
                
                # Extract page info
                page_data = {
                    "url": url,
                    "title": soup.title.string.strip() if soup.title else "",
                    "content": soup.get_text(separator=' ', strip=True)[:8000],
                    "meta_description": "",
                    "h1": [],
                    "h2": [],
                    "images": []
                }
                
                # Meta description
                meta = soup.find('meta', attrs={'name': 'description'})
                if meta:
                    page_data["meta_description"] = meta.get('content', '')
                
                # Headers
                for h1 in soup.find_all('h1'):
                    page_data["h1"].append(h1.get_text(strip=True))
                for h2 in soup.find_all('h2'):
                    page_data["h2"].append(h2.get_text(strip=True))
                
                # Images
                for img in soup.find_all('img')[:10]:
                    src = img.get('src', '')
                    if src:
                        page_data["images"].append({
                            "src": urljoin(url, src),
                            "alt": img.get('alt', '')
                        })
                
                pages.append(page_data)
                visited.add(url)
                
                # Find internal links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)
                    
                    # Only internal links
                    if parsed.netloc == urlparse(self.base_url).netloc:
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if clean_url not in visited and clean_url not in to_visit:
                            to_visit.append(clean_url)
                
            except Exception as e:
                continue
        
        return pages
    
    def search_products(self, query: str) -> List[Dict]:
        """Search WooCommerce products"""
        try:
            search_url = f"{self.base_url}/?s={query}&post_type=product"
            response = self.session.get(search_url, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            products = []
            for product in soup.select('.product, .type-product, .product-item'):
                name_el = product.select_one('.woocommerce-loop-product__title, .product-title, h2, h3')
                link_el = product.select_one('a[href]')
                img_el = product.select_one('img')
                price_el = product.select_one('.price, .woocommerce-Price-amount')
                
                if name_el:
                    products.append({
                        "name": name_el.get_text(strip=True),
                        "url": link_el.get('href') if link_el else None,
                        "image": img_el.get('src') if img_el else None,
                        "price": price_el.get_text(strip=True) if price_el else None
                    })
            
            return products
        except Exception as e:
            return [{"error": str(e)}]
    
    def find_similar_products(self, partial_name: str) -> List[Dict]:
        """Find products with fuzzy matching"""
        # Common abbreviation expansions
        expansions = {
            "zh": ["zhi", "ashwa"],
            "tr": ["triphala", "trikatu", "tribulus"],
            "ash": ["ashwagandha", "ashoka"],
            "bra": ["brahmi"],
            "sha": ["shatavari", "shankhpushpi"],
            "amo": ["amla", "amalaki"],
            "tur": ["turmeric", "haldi"],
            "gin": ["ginger", "adrak"],
            "tul": ["tulsi", "holy basil"]
        }
        
        suggestions = []
        partial_lower = partial_name.lower()
        
        # Check abbreviations
        for abbr, full_names in expansions.items():
            if abbr in partial_lower:
                suggestions.extend(full_names)
        
        # Search website
        search_results = self.search_products(partial_name)
        for result in search_results[:5]:
            if 'name' in result and 'error' not in result:
                suggestions.append(result['name'])
        
        return list(set(suggestions))
    
    def get_product_image(self, product_name: str) -> Optional[str]:
        """Get product image URL"""
        products = self.search_products(product_name)
        for p in products:
            if p.get('image') and 'error' not in p:
                return p['image']
        return None
    
    def scan_health_claims(self, content: str) -> List[Dict]:
        """Detect FDA/FTC health claim violations"""
        
        claims = []
        content_lower = content.lower()
        
        # HIGH RISK — Disease claims (FSSAI/FDA violations)
        high_risk_patterns = [
            (r'\b(cures?|treats?|heals?)\s+\w+', 'Direct disease cure claim'),
            (r'\b(prevents?|fights?)\s+(cancer|diabetes|heart|hiv|aids|stroke|infection)', 'Disease prevention claim'),
            (r'\banti[-\s]?(cancer|diabetic|viral|bacterial|inflammatory)\b', 'Anti-disease name claim'),
            (r'\b(reverses?|stops?)\s+(aging|diabetes|cancer|stroke)', 'Disease reversal claim'),
            (r'\bdiagnose[s]?\b', 'Diagnostic claim'),
            (r'\btherapeutic\b', 'Therapeutic claim'),
        ]
        
        # MEDIUM RISK — Medical authority or proof claims
        medium_risk_patterns = [
            (r'\b(clinically|scientifically)\s+proven\b', 'Medical proof claim'),
            (r'\bguaranteed\s+results?\b', 'Guarantee claim'),
            (r'\bmedically\s+tested\b', 'Medical test claim'),
            (r'\bFDA\s+approved\b', 'Agency approval claim'),
            (r'\bdoctor\s+recommended\b', 'Medical recommendation claim'),
        ]
        
        # LOW RISK — Only absolute claims like 'miracle'
        low_risk_patterns = [
            (r'\b(miracle|magic|instant|overnight)\s+(cure|results?|healing)\b', 'Absolute claim'),
        ]
        
        def find_claims(patterns, risk_level):
            for pattern, issue in patterns:
                for match in re.finditer(pattern, content_lower):
                    # Get surrounding context (50 chars each side)
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end]
                    
                    claims.append({
                        "matched_text": match.group(),
                        "context": f"...{context}...",
                        "risk_level": risk_level,
                        "issue": issue,
                        "position": match.start()
                    })
        
        find_claims(high_risk_patterns, "HIGH")
        find_claims(medium_risk_patterns, "MEDIUM")
        find_claims(low_risk_patterns, "LOW")
        
        return claims
    
    def full_health_audit(self, max_pages: int = 30) -> Dict:
        """Complete health claims audit of website"""
        pages = self.crawl_all_pages(max_pages)
        
        audit_result = {
            "site": self.base_url,
            "pages_scanned": len(pages),
            "total_claims": 0,
            "high_risk": [],
            "medium_risk": [],
            "low_risk": [],
            "clean_pages": [],
            "summary": {}
        }
        
        for page in pages:
            claims = self.scan_health_claims(page["content"])
            
            if not claims:
                audit_result["clean_pages"].append(page["url"])
                continue
            
            for claim in claims:
                claim["page_url"] = page["url"]
                claim["page_title"] = page["title"]
                audit_result["total_claims"] += 1
                
                if claim["risk_level"] == "HIGH":
                    audit_result["high_risk"].append(claim)
                elif claim["risk_level"] == "MEDIUM":
                    audit_result["medium_risk"].append(claim)
                else:
                    audit_result["low_risk"].append(claim)
        
        audit_result["summary"] = {
            "total_pages": len(pages),
            "pages_with_issues": len(pages) - len(audit_result["clean_pages"]),
            "clean_pages": len(audit_result["clean_pages"]),
            "high_risk_count": len(audit_result["high_risk"]),
            "medium_risk_count": len(audit_result["medium_risk"]),
            "low_risk_count": len(audit_result["low_risk"]),
            "compliance_score": round((len(audit_result["clean_pages"]) / len(pages)) * 100, 1) if pages else 0
        }
        
        return audit_result

# Global instance
website_tools = WebsiteTools()
