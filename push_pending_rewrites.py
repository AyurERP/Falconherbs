"""
Push all pending_approval product descriptions to WooCommerce.
Run: python push_pending_rewrites.py
"""
import sys, json, os
from pathlib import Path
from datetime import datetime

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.append('.')
from core.integration_bridge import IntegrationBridge

bridge = IntegrationBridge()
woo = bridge.tools.get('woocommerce')

REWRITES_DIR = Path('data/content/product_rewrites')
SKIP = {'last_scan.json', 'page_scan.json', 'blog_scan.json', 'category_scan.json'}

files = [p for p in REWRITES_DIR.glob('[0-9]*.json') if p.name not in SKIP]

pending = []
for f in sorted(files, key=lambda x: int(x.stem)):
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
        if d.get('status') == 'pending_approval' and d.get('rewritten_description'):
            pending.append((f, d))
    except Exception as e:
        print(f'  ⚠️ Skip {f.name}: {e}')

print(f'\nFound {len(pending)} pending_approval products to push\n')
if not pending:
    print('Nothing to push.')
    sys.exit(0)

success = 0
failed = []
for f, d in pending:
    pid = d['product_id']
    name = d.get('name', '')[:50]
    desc = d['rewritten_description']
    print(f'  Pushing ID {pid}: {name}...')
    res = woo.update_product(pid, {'description': desc})
    if res.get('success'):
        d['status'] = 'applied'
        d['applied_at'] = datetime.now().isoformat()
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'    OK')
        success += 1
    else:
        err = res.get('error', res.get('message', 'unknown'))
        print(f'    FAILED: {err}')
        failed.append((pid, name, err))

print(f'\n========================================')
print(f'Done: {success}/{len(pending)} pushed successfully')
if failed:
    print(f'Failed ({len(failed)}):')
    for pid, name, err in failed:
        print(f'   ID {pid} - {name}: {err}')
print(f'========================================\n')
