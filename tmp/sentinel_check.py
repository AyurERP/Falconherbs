import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.sentinel import Sentinel
from core.approval import ApprovalSystem
from core.whatsapp import WhatsAppNotifier
from core.logger import log

def main():
    print("🛡️ RUNNING SENTINEL SECURITY DIAGNOSTICS...")
    # Mock approval system for local run
    from core.approval import ApprovalSystem
    approval = ApprovalSystem()
    sentinel = Sentinel(approval)
    
    report = sentinel.run_scan("https://falconherbs.com")
    
    print("\n📊 SCAN REPORT:")
    print(f"Total Findings: {report.get('total_findings')}")
    print(f"Highest Severity: {report.get('highest_severity')}")
    print("\n🔍 KEY FINDINGS:")
    for f in report.get("findings", []):
        print(f"  [{f['severity']}] {f['title']} - {f['category']}")
        if f.get('recommendation'):
            print(f"    Rec: {f['recommendation']}")

if __name__ == "__main__":
    main()
