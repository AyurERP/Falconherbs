"""Test dashboard API data builder."""
import sys, os
sys.path.insert(0, 'F:/FALCON AGENCY')
os.chdir('F:/FALCON AGENCY')

# Import just the data builder
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("dash_srv", "dashboard/server.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

data = mod.build_api_data()

print("API data keys:", list(data.keys()))
print("Generated at:", data['generated_at'])
print("Goals:", data['goals'])
print("Memory:", data['memory']['messages'], "msgs,", 
      data['memory']['long_term_events'], "lt,", 
      data['memory']['business_facts'], "facts")
print("Schedule tasks:", data['schedule']['total_tasks'])
print("Upcoming:", [t['name'] for t in data['schedule']['upcoming'][:3]])
print("AutoPilot triggers:", data['autopilot']['triggers_fired'])
print("Cache:", data['cache'])

print()
print("ALL DATA READS OK")
