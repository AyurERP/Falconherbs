import sys, os
sys.path.insert(0, 'F:/FALCON AGENCY')
os.chdir('F:/FALCON AGENCY')

print('=== TEST 1: IST Time ===')
from core.ist_time import now_ist, now_ist_str, today_ist, is_write_window, minutes_until_write_window, IST
dt = now_ist()
print(f'  Current IST: {now_ist_str()}')
print(f'  Today IST:   {today_ist()}')
print(f'  Write window open: {is_write_window()}')
print(f'  Minutes until write window: {minutes_until_write_window()}')
print('  PASS')

print()
print('=== TEST 2: Cache Manager ===')
from core.cache_manager import cache, TTL_PRODUCTS
cache.set('test_key', {'hello': 'world'}, ttl=60)
val = cache.get('test_key')
assert val == {'hello': 'world'}, f'Got {val}'
cache.invalidate('test_key')
assert cache.get('test_key') is None
prod_map = cache.get_product_modified_map('falconherbs')
assert isinstance(prod_map, dict)
stats = cache.get_stats()
print('  Cache dir:', stats['cache_dir'])
print('  Entries:', stats['total_entries'])
print('  PASS')

print()
print('=== TEST 3: API Throttle ===')
from core.api_throttle import throttle, MAX_CALLS_PER_MINUTE
print(f'  Max calls/min: {MAX_CALLS_PER_MINUTE}')
throttle.reset('test_site')
count = throttle.get_call_count('test_site')
assert count == 0
throttle.record_call('test_site')
throttle.record_call('test_site')
assert throttle.get_call_count('test_site') == 2
throttle.reset('test_site')
print('  PASS')

print()
print('=== TEST 4: Write Scheduler ===')
from core.write_scheduler import write_scheduler
r = write_scheduler.queue('falconherbs', 9999, {'description': 'test'}, reason='unit_test')
print('  Queued:', r)
assert r.get('queued') == True
status = write_scheduler.get_status()
assert status['pending'] >= 1
# Clean up test entry
import json
from pathlib import Path
q = json.loads(Path('data/cache/write_queue.json').read_text())
q = [x for x in q if x.get('product_id') != 9999]
Path('data/cache/write_queue.json').write_text(json.dumps(q, indent=2))
print('  PASS')

print()
print('=== TEST 5: Site Loader ===')
from core.site_loader import site_loader
sites = site_loader.list_sites()
print('  Sites configured:', sites)
config = site_loader.get_active_site()
print('  Active site:', config.get('name'), config.get('url'))
print('  Max calls/min:', site_loader.get_max_calls('falconherbs'))
print('  PASS')

print()
print('=== TEST 6: Director Schedule uses IST ===')
from core.director_schedule import ExtendedSchedule
sched = ExtendedSchedule()
tasks = sched.schedule.get('tasks', {})
print('  Total tasks configured:', len(tasks))
assert 'whm_write_queue' in tasks, 'whm_write_queue task missing!'
wq = tasks['whm_write_queue']
assert wq['time'] == '02:00', f"Write queue time wrong: {wq['time']}"
print('  whm_write_queue at 02:00 IST: OK')
print('  PASS')

print()
print('=== ALL TESTS PASSED ===')
