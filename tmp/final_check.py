import sys, os
sys.path.insert(0, '.')
os.chdir('F:/FALCON AGENCY')

errors = []

# 1. All new modules import cleanly
try:
    from core.ist_time import now_ist, now_ist_str, IST
    from core.cache_manager import cache
    from core.api_throttle import throttle
    from core.write_scheduler import write_scheduler
    from core.site_loader import site_loader
    print('OK: All 5 new modules import clean')
except Exception as e:
    errors.append(f'Import error: {e}')

# 2. IST time correct
t = now_ist()
assert t.tzinfo is not None
assert '+05:30' in now_ist_str()
print(f'OK: IST = {now_ist_str()}')

# 3. Cache TTLs
from core.cache_manager import TTL_PRODUCTS, TTL_BLOGS, TTL_CATEGORIES
assert TTL_PRODUCTS == 7200 and TTL_BLOGS == 21600 and TTL_CATEGORIES == 86400
print('OK: Cache TTLs = 2h / 6h / 24h')

# 4. Throttle
from core.api_throttle import MAX_CALLS_PER_MINUTE
assert MAX_CALLS_PER_MINUTE == 5
print('OK: Throttle = 5 calls/min per site')

# 5. Write window
from core.ist_time import is_write_window, minutes_until_write_window
assert not is_write_window()
mins = minutes_until_write_window()
print(f'OK: Write window closed, opens in {mins//60}h {mins%60}m (2 AM IST)')

# 6. Site loader
cfg = site_loader.get_site('falconherbs')
assert cfg.get('url') == 'https://falconherbs.com'
assert site_loader.get_max_calls('falconherbs') == 5
print('OK: Site loader = ' + cfg['url'])

# 7. Director schedule IST fix
from core.director_schedule import ExtendedSchedule
s = ExtendedSchedule()
tasks = s.schedule['tasks']
assert 'whm_write_queue' in tasks
assert tasks['whm_write_queue']['time'] == '02:00'
assert tasks['morning_report']['time'] == '06:00'
print(f'OK: Schedule = {len(tasks)} tasks, write queue at 02:00 IST')

# 8. WooCommerce connector has throttle + cache
import inspect
from core.woocommerce_connector import WooCommerceConnector
src = inspect.getsource(WooCommerceConnector._make_request)
assert 'call_with_retry' in src
src2 = inspect.getsource(WooCommerceConnector.get_all_products)
assert 'cache' in src2 and 'force_refresh' in src2
print('OK: WooCommerce = throttled + cached')

if errors:
    print('ERRORS:', errors)
    sys.exit(1)

print()
print('ALL 8 CHECKS PASSED')
print('VPS optimization complete - ready to commit')
