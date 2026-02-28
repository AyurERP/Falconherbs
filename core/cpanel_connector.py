import os
import requests
import json
import urllib3
from typing import Dict, List, Optional
from dotenv import load_dotenv
from core.logger import log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CPanelConnector:
    """
    Direct interface to cPanel UAPI for file management and automation.
    Requires FALCONHERBS_CPANEL_* variables in .env.
    """
    
    def __init__(self):
        self.url = os.getenv("FALCONHERBS_CPANEL_URL", "").rstrip("/")
        self.user = os.getenv("FALCONHERBS_CPANEL_USER", "")
        self.token = os.getenv("FALCONHERBS_CPANEL_PASSWORD", "")
        self._configured = all([self.url, self.user, self.token])
        
        if not self._configured:
            log.warning("CPanelConnector not fully configured. API calls will fail.")

    def _execute(self, module: str, function: str, params: Optional[Dict] = None) -> Dict:
        """Internal UAPI executor"""
        if not self._configured:
            return {"status": 0, "errors": ["CPanelConnector not configured"]}
            
        endpoint = f"{self.url}/execute/{module}/{function}"
        try:
            r = requests.get(
                endpoint,
                auth=(self.user, self.token),
                params=params or {},
                timeout=20,
                verify=False
            )
            return r.json()
        except Exception as e:
            log.error(f"cPanel UAPI error ({module}.{function}): {e}")
            return {"status": 0, "errors": [str(e)]}

    def get_file_content(self, directory: str, filename: str) -> Optional[str]:
        """Fetch raw content of a file via cPanel Fileman"""
        res = self._execute("Fileman", "get_file_content", {"dir": directory, "file": filename})
        if not res.get("status"):
            log.warning(f"Could not read cPanel file {directory}/{filename}: {res.get('errors')}")
            return None
            
        data = res.get("data")
        if isinstance(data, str):
            return data
        elif isinstance(data, dict) and "content" in data:
            return data["content"]
        elif isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, dict) and "content" in item:
                return item["content"]
            elif isinstance(item, str):
                return item
        
        log.warning(f"Unexpected data format from cPanel for {filename}: {type(data)}")
        return None

    def save_file_content(self, directory: str, filename: str, content: str) -> bool:
        """Overwrite a file's content via cPanel Fileman"""
        res = self._execute("Fileman", "save_file_content", {
            "dir": directory,
            "file": filename,
            "content": content
        })
        if res.get("status"):
            log.info(f"Successfully saved cPanel file: {directory}/{filename}")
            return True
        else:
            log.error(f"Failed to save cPanel file {directory}/{filename}: {res.get('errors')}")
            return False

    def patch_htaccess_security_headers(self) -> bool:
        """
        Permanent Auto-Fix: Adds HSTS and CSP headers to .htaccess.
        Returns True if patches were applied successfully.
        """
        log.info("Sentinel Auto-Fix: Patching .htaccess security headers...")
        content = self.get_file_content("public_html", ".htaccess")
        if content is None:
            return False
            
        # Headers to add
        headers = [
            'Header always set Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"',
            "Header always set Content-Security-Policy \"default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval';\""
        ]
        
        # Check if already present to avoid duplicates
        if "Strict-Transport-Security" in content and "Content-Security-Policy" in content:
            log.info(".htaccess security headers already present.")
            return True

        if "<IfModule mod_headers.c>" in content:
            parts = content.split("<IfModule mod_headers.c>", 1)
            insertion = "\n    " + "\n    ".join(headers)
            new_content = parts[0] + "<IfModule mod_headers.c>" + insertion + parts[1]
        else:
            insertion = "<IfModule mod_headers.c>\n    " + "\n    ".join(headers) + "\n</IfModule>\n\n"
            new_content = insertion + content
            
        return self.save_file_content("public_html", ".htaccess", new_content)

    def list_backups(self) -> List[Dict]:
        """List available backups on cPanel"""
        # UAPI Backups::list_backups
        res = self._execute("Backups", "list_backups")
        if res.get("status"):
            return res.get("data", [])
        return []

    def start_full_backup(self) -> bool:
        """Trigger a full cPanel backup to home directory"""
        # UAPI Backups::fullbackup_to_homedir
        res = self._execute("Backups", "fullbackup_to_homedir")
        if res.get("status"):
            log.info("cPanel full backup triggered successfully.")
            return True
        else:
            log.error(f"Failed to trigger cPanel backup: {res.get('errors')}")
            return False

cpanel = CPanelConnector()
