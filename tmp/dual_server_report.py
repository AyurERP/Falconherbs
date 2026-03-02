"""Generate full WHM + Oracle VPS report."""
import os, sys, requests, json, subprocess, platform
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

WHM_URL  = os.getenv("WHM_URL","").rstrip("/")
WHM_USER = os.getenv("WHM_USER","")
WHM_PASS = os.getenv("WHM_PASSWORD","")

import urllib3
urllib3.disable_warnings()

def whm(func, **params):
    params["api.version"] = 1
    try:
        r = requests.get(f"{WHM_URL}/json-api/{func}", params=params,
                         auth=(WHM_USER, WHM_PASS), verify=False, timeout=20)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

now = datetime.now().strftime("%d %b %Y  %I:%M %p")
print(f"\n{'='*60}")
print(f"  FALCON AGENCY — DUAL SERVER REPORT")
print(f"  Generated: {now} IST")
print(f"{'='*60}\n")

# ═══════════════════════════════════════════════════════
# PART 1: ORACLE VPS
# ═══════════════════════════════════════════════════════
print("┌─────────────────────────────────────────────────┐")
print("│           ORACLE VPS (Agency Brain)             │")
print("└─────────────────────────────────────────────────┘")

import psutil
from datetime import timedelta

# CPU
cpu_pct  = psutil.cpu_percent(interval=2)
cpu_count = psutil.cpu_count()

# Memory
mem = psutil.virtual_memory()
mem_used_gb  = round(mem.used / 1024**3, 2)
mem_total_gb = round(mem.total / 1024**3, 2)
mem_pct      = mem.percent

# Disk
disk = psutil.disk_usage('/')
disk_used_gb  = round(disk.used / 1024**3, 1)
disk_total_gb = round(disk.total / 1024**3, 1)
disk_pct      = disk.percent

# Uptime
boot_time = psutil.boot_time()
uptime_sec = (datetime.now().timestamp() - boot_time)
uptime_str = str(timedelta(seconds=int(uptime_sec)))

# Processes
procs = len(psutil.pids())

print(f"  OS:          {platform.system()} {platform.release()}")
print(f"  Uptime:      {uptime_str}")
print(f"  CPU:         {cpu_pct}% used ({cpu_count} cores)")
print(f"  Memory:      {mem_used_gb} GB / {mem_total_gb} GB ({mem_pct}%)")
print(f"  Disk (/):    {disk_used_gb} GB / {disk_total_gb} GB ({disk_pct}%)")
print(f"  Processes:   {procs} running")

# CPU status
cpu_status = "🟢 OK" if cpu_pct < 70 else ("🟡 HIGH" if cpu_pct < 90 else "🔴 CRITICAL")
mem_status = "🟢 OK" if mem_pct < 75 else ("🟡 HIGH" if mem_pct < 90 else "🔴 CRITICAL")
disk_status = "🟢 OK" if disk_pct < 75 else ("🟡 HIGH" if disk_pct < 90 else "🔴 CRITICAL")

print(f"\n  Status:  CPU {cpu_status}  |  RAM {mem_status}  |  Disk {disk_status}")

# Network
try:
    net = psutil.net_io_counters()
    sent_mb = round(net.bytes_sent / 1024**2, 1)
    recv_mb = round(net.bytes_recv / 1024**2, 1)
    print(f"  Network:     Sent {sent_mb} MB | Recv {recv_mb} MB")
except:
    pass

# Check if Director is running
try:
    director_running = any('director' in p.info.get('name','').lower() or 
                          'director' in ' '.join(p.info.get('cmdline',[])).lower()
                          for p in psutil.process_iter(['name','cmdline']))
    print(f"  Director:    {'🟢 RUNNING' if director_running else '🟡 NOT RUNNING (on this machine)'}")
except:
    print(f"  Director:    checking...")

# Agency files
agency_dir = Path(".")
data_dir = Path("data")
cache_files = list(Path("data/cache").glob("*.json")) if Path("data/cache").exists() else []
queue_f = Path("data/cache/write_queue.json")
pending_writes = 0
if queue_f.exists():
    try:
        q = json.loads(queue_f.read_text())
        pending_writes = sum(1 for x in q if x.get("status")=="pending")
    except: pass

print(f"\n  Agency State:")
print(f"    Cache files:    {len(cache_files)}")
print(f"    Pending writes: {pending_writes} (queued for 2 AM IST)")

# ═══════════════════════════════════════════════════════
# PART 2: WHM SHARED SERVER
# ═══════════════════════════════════════════════════════
print(f"\n┌─────────────────────────────────────────────────┐")
print(f"│       WHM SHARED SERVER (22 Websites)           │")
print(f"└─────────────────────────────────────────────────┘")

# WHM version
ver_data = whm("version")
whm_ver = ver_data.get("version", ver_data.get("error","?"))
print(f"  WHM Version: {whm_ver}")

# All accounts
accts_data = whm("listaccts")
accounts = accts_data.get("data",{}).get("acct",[])
print(f"  Total Sites: {len(accounts)}")

total_disk_mb = 0
big_sites = []
empty_sites = []
high_inodes = []

for a in accounts:
    disk_s = a.get("diskused","0M")
    try:
        if disk_s.endswith("M"):
            disk_mb = float(disk_s[:-1])
        elif disk_s.endswith("G"):
            disk_mb = float(disk_s[:-1]) * 1024
        elif disk_s.endswith("k"):
            disk_mb = float(disk_s[:-1]) / 1024
        else:
            disk_mb = 0
    except:
        disk_mb = 0

    total_disk_mb += disk_mb
    inodes = a.get("inodesused", 0)

    if disk_mb > 10240:  # >10GB
        big_sites.append((a["domain"], disk_mb, inodes))
    if disk_mb < 100:    # <100MB = empty
        empty_sites.append((a["domain"], disk_mb, inodes))
    if inodes > 200000:
        high_inodes.append((a["domain"], inodes))

total_disk_gb = round(total_disk_mb / 1024, 1)
print(f"  Total Disk:  {total_disk_gb} GB across all sites")

print(f"\n  🔴 LARGE SITES (>10 GB — causing server load):")
for domain, mb, inodes in sorted(big_sites, key=lambda x: -x[1]):
    gb = round(mb/1024,1)
    print(f"    {domain}: {gb} GB  ({inodes:,} inodes)")

print(f"\n  ⚪ NEARLY EMPTY SITES (<100 MB):")
for domain, mb, inodes in empty_sites:
    print(f"    {domain}: {mb:.0f} MB  ({inodes} inodes)")
if not empty_sites:
    print(f"    None")

print(f"\n  ⚠️  HIGH INODES (>200k — risky for shared hosting):")
for domain, inodes in sorted(high_inodes, key=lambda x: -x[1]):
    print(f"    {domain}: {inodes:,} inodes")
if not high_inodes:
    print(f"    None")

# Quick uptime check for key sites
print(f"\n  🌐 UPTIME CHECK (key sites):")
import time
key_sites = ["falconherbs.com","newyorkbannerstands.com","printpopupstands.com"]
for site in key_sites:
    try:
        t0 = time.time()
        r = requests.get(f"https://{site}", timeout=10, verify=False, 
                        allow_redirects=True, headers={"User-Agent":"Mozilla/5.0"})
        ms = int((time.time()-t0)*1000)
        icon = "🟢" if ms < 3000 else ("🟡" if ms < 6000 else "🔴")
        print(f"    {icon} {site}: {r.status_code}  {ms}ms")
    except Exception as e:
        print(f"    🔴 {site}: DOWN ({str(e)[:40]})")

# ═══════════════════════════════════════════════════════
# PART 3: HONEST AGENCY ASSESSMENT
# ═══════════════════════════════════════════════════════
print(f"\n┌─────────────────────────────────────────────────┐")
print(f"│      AGENCY READINESS — HONEST ASSESSMENT      │")
print(f"└─────────────────────────────────────────────────┘")

issues = []
if cpu_pct > 80: issues.append(f"VPS CPU high ({cpu_pct}%)")
if mem_pct > 85: issues.append(f"VPS RAM high ({mem_pct}%)")
if disk_pct > 80: issues.append(f"VPS disk high ({disk_pct}%)")
if big_sites: issues.append(f"{len(big_sites)} WHM sites >10GB causing server load")
if empty_sites: issues.append(f"{len(empty_sites)} empty sites wasting resources")
if high_inodes: issues.append(f"{len(high_inodes)} sites with dangerous inode count")

if not issues:
    print(f"  ✅ Agency can handle this well — all systems healthy")
else:
    print(f"  {'🟡' if len(issues) < 3 else '🔴'} {len(issues)} issue(s) to address:")
    for i in issues:
        print(f"    → {i}")

print(f"\n{'='*60}")
print(f"  Report complete. IST: {now}")
print(f"{'='*60}\n")
