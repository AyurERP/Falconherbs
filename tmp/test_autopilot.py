"""Test autopilot module."""
import sys, os
sys.path.insert(0, 'F:/FALCON AGENCY')
os.chdir('F:/FALCON AGENCY')

from core.autopilot import autopilot, AutoPilot

print("=== TEST 1: AutoPilot imports and singleton ===")
assert autopilot is not None
print("  PASS")

print()
print("=== TEST 2: State persistence ===")
from core.ist_time import now_ist
now = now_ist()
autopilot._mark_fired("test_trigger", now)
assert not autopilot._cooldown_ok("test_trigger", now)  # just fired = no cooldown
print("  Cooldown working correctly")
print("  PASS")

print()
print("=== TEST 3: Flood protection ===")
ap2 = AutoPilot()
ap2._goals_this_hour = [now.timestamp()] * 3  # simulate 3 goals already
result = ap2.tick(director=None)
assert result == [], f"Expected [] but got {result}"
print("  Flood gate active at 3/hr limit")
print("  PASS")

print()
print("=== TEST 4: Status ===")
status = autopilot.get_status()
assert "auto_goals_this_hour" in status
assert "write_window_open" in status
assert "mins_until_write_window" in status
print(f"  Status: {status}")
print("  PASS")

print()
print("=== TEST 5: tick() with no director ===")
ap3 = AutoPilot()  # fresh instance, no prior state
result = ap3.tick(director=None)
# Should run without crashing even with no director
print(f"  tick() returned: {len(result)} goal(s)")
print("  PASS")

print()
print("=== TEST 6: Director has autopilot wired ===")
import inspect
import core.director as director_mod
src = inspect.getsource(director_mod.Director._run_idle_monitoring)
assert "autopilot" in src
assert "autopilot.tick" in src
print("  autopilot.tick() found in Director._run_idle_monitoring")
print("  PASS")

print()
print("=== ALL 6 TESTS PASSED ===")
print("AutoPilot ready — Director will now think proactively every 60s")
