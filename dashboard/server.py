"""
dashboard/server.py — Falcon Agency Local Dashboard Server
============================================================
Run: python dashboard/server.py
Opens: http://localhost:7474
"""

import http.server
import json
import os
import sqlite3
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent          # F:/FALCON AGENCY
DATA = ROOT / "data"
PORT = 7474


def _read(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _db_query(sql: str, params=()) -> list:
    db = DATA / "falcon.db"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(str(db))
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def build_api_data() -> dict:
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)

    # ── Goals ──────────────────────────────────────────────────────────────
    goals_raw = _read(DATA / "goals.json", [])
    goals = {
        "pending":     sum(1 for g in goals_raw if g.get("status") == "pending"),
        "in_progress": sum(1 for g in goals_raw if g.get("status") == "in_progress"),
        "complete":    sum(1 for g in goals_raw if g.get("status") == "complete"),
        "failed":      sum(1 for g in goals_raw if g.get("status") == "failed"),
        "auto":        sum(1 for g in goals_raw if g.get("auto")),
        "list":        goals_raw[-10:][::-1],
    }

    # ── Spend ───────────────────────────────────────────────────────────────
    spend_raw = _read(DATA / "spend.json", {})
    spend = {
        "today": round(spend_raw.get("daily_spend", 0), 4),
        "month": round(spend_raw.get("monthly_spend", 0), 4),
    }

    # ── Cache ───────────────────────────────────────────────────────────────
    cache_dir  = DATA / "cache"
    cache_files = list(cache_dir.glob("*.json")) if cache_dir.exists() else []
    write_queue_raw = _read(cache_dir / "write_queue.json", [])
    pending_writes  = sum(1 for x in write_queue_raw if x.get("status") == "pending")

    # ── AutoPilot state ─────────────────────────────────────────────────────
    ap_state = _read(cache_dir / "autopilot_state.json", {})
    last_fired = ap_state.get("last_fired", {})
    ap_triggers = []
    for trigger, ts in last_fired.items():
        try:
            mins_ago = int((time.time() - ts) / 60)
            ap_triggers.append({"name": trigger, "mins_ago": mins_ago})
        except Exception:
            pass
    ap_triggers.sort(key=lambda x: x["mins_ago"])

    # ── Schedule ────────────────────────────────────────────────────────────
    schedule_raw = _read(DATA / "extended_schedule.json", {})
    tasks = schedule_raw.get("tasks", {})
    upcoming = []
    current_hour = now_ist.hour
    for name, cfg in tasks.items():
        task_time = cfg.get("time", "")
        if task_time:
            try:
                th, tm = map(int, task_time.split(":"))
                mins_away = ((th * 60 + tm) - (current_hour * 60 + now_ist.minute)) % (24 * 60)
                upcoming.append({
                    "name": name,
                    "time": task_time,
                    "mins_away": mins_away,
                    "last_run": cfg.get("last_run", "never"),
                })
            except Exception:
                pass
    upcoming.sort(key=lambda x: x["mins_away"])

    # ── Memory stats ─────────────────────────────────────────────────────────
    msg_count  = _db_query("SELECT COUNT(*) FROM messages")[0][0] if _db_query("SELECT COUNT(*) FROM messages") else 0
    lt_count   = _db_query("SELECT COUNT(*) FROM long_term")[0][0] if _db_query("SELECT COUNT(*) FROM long_term") else 0
    fact_count = _db_query("SELECT COUNT(*) FROM business_facts")[0][0] if _db_query("SELECT COUNT(*) FROM business_facts") else 0
    recent_msgs = _db_query(
        "SELECT role, content, timestamp FROM messages ORDER BY timestamp DESC LIMIT 5"
    )

    # Recent long-term events
    lt_events = _db_query(
        "SELECT category, title, timestamp, importance FROM long_term ORDER BY timestamp DESC LIMIT 8"
    )

    # Business facts
    biz_facts = _db_query("SELECT key, value, updated_at FROM business_facts ORDER BY updated_at DESC")
    biz_facts = [{"key": r[0], "value": json.loads(r[1]), "updated": r[2][:10]} for r in biz_facts]

    # ── Daily progress ───────────────────────────────────────────────────────
    progress = _read(DATA / "daily_progress.json", {})

    # ── Ideas ────────────────────────────────────────────────────────────────
    ideas = _read(DATA / "ideas.json", [])

    # ── Write window ─────────────────────────────────────────────────────────
    write_open = 2 <= now_ist.hour < 4
    mins_to_write = ((2 * 60) - (now_ist.hour * 60 + now_ist.minute)) % (24 * 60)

    return {
        "generated_at": now_ist.strftime("%d %b %Y %I:%M %p IST"),
        "ist_time":     now_ist.strftime("%H:%M"),
        "ist_date":     now_ist.strftime("%A, %d %b %Y"),
        "goals": goals,
        "spend": spend,
        "cache": {
            "files": len(cache_files),
            "pending_writes": pending_writes,
            "write_window_open": write_open,
            "mins_to_write_window": mins_to_write,
        },
        "schedule": {
            "total_tasks": len(tasks),
            "upcoming": upcoming[:8],
        },
        "memory": {
            "messages": msg_count,
            "long_term_events": lt_count,
            "business_facts": fact_count,
            "recent_msgs": [
                {"role": r[0], "content": r[1][:80], "time": r[2][11:16]} for r in recent_msgs
            ],
            "lt_events": [
                {"category": r[0], "title": r[1], "date": r[2][:10], "importance": r[3]}
                for r in lt_events
            ],
            "biz_facts": biz_facts,
        },
        "autopilot": {
            "triggers_fired": len(ap_triggers),
            "recent": ap_triggers[:6],
        },
        "progress": progress,
        "ideas_count": len(ideas) if isinstance(ideas, list) else 0,
    }


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Falcon Agency — Command Centre</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0a0a0f;
  --surface: #12121a;
  --surface2: #1a1a26;
  --border: #2a2a3d;
  --accent: #6c63ff;
  --accent2: #00d4aa;
  --accent3: #ff6b6b;
  --accent4: #ffa94d;
  --text: #e8e8f0;
  --muted: #666680;
  --green: #00d4aa;
  --red: #ff6b6b;
  --yellow: #ffa94d;
  --blue: #6c63ff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  min-height: 100vh;
}
/* Header */
.header {
  background: linear-gradient(135deg, #0d0d1a 0%, #1a1030 50%, #0d1a20 100%);
  border-bottom: 1px solid var(--border);
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky; top: 0; z-index: 100;
  backdrop-filter: blur(20px);
}
.logo {
  display: flex; align-items: center; gap: 12px;
}
.logo-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 700;
  box-shadow: 0 0 20px rgba(108,99,255,0.4);
}
.logo-text { font-size: 16px; font-weight: 700; letter-spacing: -0.3px; }
.logo-sub { font-size: 11px; color: var(--muted); font-weight: 400; }
.header-right { display: flex; align-items: center; gap: 16px; }
.time-display {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px; color: var(--accent2);
  background: rgba(0,212,170,0.1);
  padding: 6px 12px; border-radius: 8px;
  border: 1px solid rgba(0,212,170,0.2);
}
.refresh-btn {
  background: var(--accent); border: none; color: white;
  padding: 7px 14px; border-radius: 8px; cursor: pointer;
  font-family: 'Inter', sans-serif; font-size: 13px; font-weight: 500;
  transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.refresh-btn:hover { background: #8077ff; transform: translateY(-1px); }
.pulse { width:8px; height:8px; border-radius:50%; background:var(--green);
  animation: pulse 2s infinite; }
@keyframes pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(0,212,170,0.6); }
  50% { box-shadow: 0 0 0 6px rgba(0,212,170,0); }
}
/* Grid */
.grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 16px;
  padding: 20px 24px; }
.grid-6 { grid-template-columns: repeat(6,1fr); }
.col-2 { grid-column: span 2; }
.col-3 { grid-column: span 3; }
.col-4 { grid-column: span 4; }
.col-6 { grid-column: span 6; }
/* Cards */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px; padding: 18px;
  transition: border-color 0.2s, transform 0.2s;
}
.card:hover { border-color: rgba(108,99,255,0.4); transform: translateY(-1px); }
.card-title {
  font-size: 11px; font-weight: 600; letter-spacing: 0.8px;
  text-transform: uppercase; color: var(--muted); margin-bottom: 12px;
  display: flex; align-items: center; gap: 6px;
}
.card-title .icon { font-size: 14px; }
/* Stat cards */
.stat-value {
  font-size: 32px; font-weight: 700; letter-spacing: -1px;
  line-height: 1; margin-bottom: 4px;
}
.stat-label { font-size: 12px; color: var(--muted); }
.stat-green { color: var(--green); }
.stat-red { color: var(--red); }
.stat-yellow { color: var(--yellow); }
.stat-blue { color: var(--blue); }
.stat-white { color: var(--text); }
/* Status row */
.status-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 0; border-bottom: 1px solid var(--border);
}
.status-row:last-child { border-bottom: none; }
.status-label { color: var(--muted); font-size: 12px; }
.status-value { font-weight: 500; font-size: 13px; font-family: 'JetBrains Mono', monospace; }
/* Badge */
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 20px;
  font-size: 11px; font-weight: 600;
}
.badge-green { background: rgba(0,212,170,0.15); color: var(--green); }
.badge-red { background: rgba(255,107,107,0.15); color: var(--red); }
.badge-yellow { background: rgba(255,169,77,0.15); color: var(--yellow); }
.badge-blue { background: rgba(108,99,255,0.15); color: var(--blue); }
.badge-muted { background: rgba(102,102,128,0.2); color: var(--muted); }
/* Mini list */
.mini-list { display: flex; flex-direction: column; gap: 6px; }
.mini-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px 10px; background: var(--surface2);
  border-radius: 8px; border: 1px solid var(--border);
  font-size: 12px; line-height: 1.4;
}
.mini-item .dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; margin-top: 4px;
}
.dot-green { background: var(--green); }
.dot-red { background: var(--red); }
.dot-yellow { background: var(--yellow); }
.dot-blue { background: var(--blue); }
.dot-muted { background: var(--muted); }
/* Timeline */
.timeline { display: flex; flex-direction: column; gap: 4px; }
.tl-item {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
}
.tl-time {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; color: var(--accent2); min-width: 40px;
}
.tl-name { font-size: 12px; flex: 1; }
.tl-away { font-size: 11px; color: var(--muted); }
/* Progress bar */
.progress-wrap { margin-top: 8px; }
.progress-bar {
  height: 4px; background: var(--surface2); border-radius: 2px; overflow: hidden;
}
.progress-fill { height: 100%; border-radius: 2px; transition: width 0.4s; }
.fill-green { background: linear-gradient(90deg, var(--green), #00ffcc); }
.fill-blue { background: linear-gradient(90deg, var(--blue), #a89cff); }
.fill-yellow { background: linear-gradient(90deg, var(--yellow), #ffcc80); }
.fill-red { background: linear-gradient(90deg, var(--red), #ff9393); }
/* Memory chat */
.chat-bubble {
  padding: 8px 12px; border-radius: 10px; margin: 4px 0; font-size: 12px;
  max-width: 90%; line-height: 1.4;
}
.chat-user { background: rgba(108,99,255,0.15); border: 1px solid rgba(108,99,255,0.2); align-self: flex-end; margin-left: auto; }
.chat-director { background: var(--surface2); border: 1px solid var(--border); }
.chat-time { font-size: 10px; color: var(--muted); margin-top: 2px; }
.chat-wrap { display: flex; flex-direction: column; gap: 4px; max-height: 160px; overflow-y: auto; }
/* Section label */
.section-label { font-size: 11px; color: var(--muted); text-transform: uppercase; 
  letter-spacing: 1px; font-weight: 600; padding: 0 24px; margin: 4px 0 -8px; }
/* Glow effect */
.glow-green { box-shadow: 0 0 20px rgba(0,212,170,0.1); }
.glow-blue { box-shadow: 0 0 20px rgba(108,99,255,0.1); }
/* Fact table */
.fact-table { width: 100%; border-collapse: collapse; }
.fact-table td { padding: 6px 8px; font-size: 12px; border-bottom: 1px solid var(--border); }
.fact-table td:first-child { color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.fact-table td:last-child { color: var(--accent2); font-weight: 500; text-align: right; }
.fact-table tr:last-child td { border-bottom: none; }
/* Footer */
.footer { text-align: center; color: var(--muted); font-size: 11px; 
  padding: 16px; border-top: 1px solid var(--border); margin-top: 8px; }
/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <div class="logo-icon">F</div>
    <div>
      <div class="logo-text">Falcon Agency</div>
      <div class="logo-sub">Command Centre</div>
    </div>
  </div>
  <div class="header-right">
    <div class="pulse"></div>
    <div class="time-display" id="live-time">Loading...</div>
    <button class="refresh-btn" onclick="loadData()">⟳ Refresh</button>
  </div>
</div>

<!-- STATS ROW -->
<div class="grid grid-6" style="padding-bottom:0">

  <div class="card glow-blue" id="stat-goals">
    <div class="card-title"><span class="icon">🎯</span> Active Goals</div>
    <div class="stat-value stat-blue" id="val-goals">—</div>
    <div class="stat-label">pending + in progress</div>
  </div>

  <div class="card" id="stat-complete">
    <div class="card-title"><span class="icon">✅</span> Completed</div>
    <div class="stat-value stat-green" id="val-complete">—</div>
    <div class="stat-label">goals done</div>
  </div>

  <div class="card" id="stat-auto">
    <div class="card-title"><span class="icon">🤖</span> AutoPilot Goals</div>
    <div class="stat-value stat-blue" id="val-auto">—</div>
    <div class="stat-label">injected automatically</div>
  </div>

  <div class="card" id="stat-memory">
    <div class="card-title"><span class="icon">🧠</span> Memory</div>
    <div class="stat-value stat-blue" id="val-memory">—</div>
    <div class="stat-label">messages stored</div>
  </div>

  <div class="card" id="stat-writes">
    <div class="card-title"><span class="icon">📝</span> Write Queue</div>
    <div class="stat-value" id="val-writes">—</div>
    <div class="stat-label" id="lbl-writes">pending for 2 AM IST</div>
  </div>

  <div class="card" id="stat-spend">
    <div class="card-title"><span class="icon">💰</span> AI Spend</div>
    <div class="stat-value stat-green" id="val-spend">—</div>
    <div class="stat-label" id="lbl-spend">today / month</div>
  </div>

</div>

<!-- MAIN CONTENT -->
<div class="grid grid-6">

  <!-- Goals list -->
  <div class="card col-2">
    <div class="card-title"><span class="icon">🎯</span> Recent Goals</div>
    <div class="mini-list" id="goals-list"></div>
  </div>

  <!-- Schedule -->
  <div class="card col-2">
    <div class="card-title"><span class="icon">📅</span> Upcoming Schedule (IST)</div>
    <div class="timeline" id="schedule-list"></div>
  </div>

  <!-- AutoPilot -->
  <div class="card col-2">
    <div class="card-title"><span class="icon">🤖</span> AutoPilot Activity</div>
    <div class="mini-list" id="ap-list"></div>
    <div style="margin-top:12px">
      <div class="status-row">
        <span class="status-label">Write Window</span>
        <span class="status-value" id="write-window-status">—</span>
      </div>
      <div class="status-row">
        <span class="status-label">Cache Files</span>
        <span class="status-value" id="cache-files">—</span>
      </div>
    </div>
  </div>

  <!-- Memory: recent chat -->
  <div class="card col-3">
    <div class="card-title"><span class="icon">💬</span> Recent Conversation</div>
    <div class="chat-wrap" id="chat-list"></div>
  </div>

  <!-- Memory: long-term events -->
  <div class="card col-3">
    <div class="card-title"><span class="icon">📌</span> Long-Term Memory</div>
    <div class="mini-list" id="lt-list"></div>
  </div>

  <!-- Business facts -->
  <div class="card col-3">
    <div class="card-title"><span class="icon">📊</span> Business Facts</div>
    <table class="fact-table" id="facts-table"></table>
    <div style="margin-top:10px;color:var(--muted);font-size:11px" id="facts-empty"></div>
  </div>

  <!-- Memory stats -->
  <div class="card col-3">
    <div class="card-title"><span class="icon">🧠</span> Memory Stats</div>
    <div class="status-row">
      <span class="status-label">Total Messages</span>
      <span class="status-value stat-blue" id="m-msgs">—</span>
    </div>
    <div class="status-row">
      <span class="status-label">Long-term Events</span>
      <span class="status-value stat-blue" id="m-lt">—</span>
    </div>
    <div class="status-row">
      <span class="status-label">Business Facts</span>
      <span class="status-value stat-blue" id="m-facts">—</span>
    </div>
    <div class="status-row">
      <span class="status-label">Scheduled Tasks</span>
      <span class="status-value" id="m-sched">—</span>
    </div>
    <div class="status-row">
      <span class="status-label">Ideas Captured</span>
      <span class="status-value" id="m-ideas">—</span>
    </div>
    <div class="progress-wrap" style="margin-top:12px">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px">
        <span style="font-size:11px;color:var(--muted)">Memory usage</span>
        <span style="font-size:11px;color:var(--muted)" id="mem-pct-lbl">—</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill fill-blue" id="mem-bar" style="width:0%"></div>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  Falcon Agency Dashboard · Last updated: <span id="last-update">—</span> ·
  <a href="/api" style="color:var(--muted)">Raw JSON</a>
</div>

<script>
const CAT_COLORS = {
  revenue: 'green', order: 'green', error: 'red', decision: 'blue',
  milestone: 'blue', content: 'yellow', seo: 'yellow', security: 'red',
  product: 'blue', customer: 'green',
};
const IMP_ICON = { 1: '⚪', 2: '🟡', 3: '🔴' };

function dot(color) {
  return `<span class="dot dot-${color}"></span>`;
}
function badge(text, color) {
  return `<span class="badge badge-${color}">${text}</span>`;
}
function el(id) { return document.getElementById(id); }

async function loadData() {
  try {
    const res = await fetch('/api');
    const d = await res.json();

    // Header time
    el('live-time').textContent = d.ist_date + ' · ' + d.ist_time + ' IST';
    el('last-update').textContent = d.generated_at;

    // Stats
    const activeGoals = (d.goals.pending || 0) + (d.goals.in_progress || 0);
    el('val-goals').textContent = activeGoals;
    el('val-complete').textContent = d.goals.complete || 0;
    el('val-auto').textContent = d.goals.auto || 0;
    el('val-memory').textContent = d.memory.messages;
    el('val-writes').textContent = d.cache.pending_writes;
    el('val-writes').className = 'stat-value ' + (d.cache.pending_writes > 0 ? 'stat-yellow' : 'stat-muted');
    el('val-spend').textContent = '$' + (d.spend.today || 0).toFixed(4);
    el('lbl-spend').textContent = 'today / $' + (d.spend.month || 0).toFixed(4) + ' month';

    // Write window
    el('write-window-status').innerHTML = d.cache.write_window_open
      ? badge('OPEN NOW', 'green')
      : badge('In ' + d.cache.mins_to_write_window + 'm', 'muted');

    el('cache-files').textContent = d.cache.files + ' files';

    // Goals list
    const goalsList = el('goals-list');
    goalsList.innerHTML = '';
    if (d.goals.list && d.goals.list.length > 0) {
      d.goals.list.slice(0,8).forEach(g => {
        const statusColor = {pending:'yellow',in_progress:'blue',complete:'green',failed:'red'}[g.status] || 'muted';
        const auto = g.auto ? ' 🤖' : '';
        goalsList.innerHTML += `<div class="mini-item">
          ${dot(statusColor)}
          <div>
            <div>${(g.description||'').slice(0,60)}${auto}</div>
            <div style="margin-top:2px">${badge(g.status, statusColor)} ${g.agent ? badge(g.agent,'muted') : ''}</div>
          </div>
        </div>`;
      });
    } else {
      goalsList.innerHTML = '<div style="color:var(--muted);font-size:12px">No goals yet</div>';
    }

    // Schedule
    const schedList = el('schedule-list');
    schedList.innerHTML = '';
    (d.schedule.upcoming || []).forEach(t => {
      const h = Math.floor(t.mins_away / 60);
      const m = t.mins_away % 60;
      const away = h > 0 ? `${h}h ${m}m` : `${m}m`;
      schedList.innerHTML += `<div class="tl-item">
        <span class="tl-time">${t.time}</span>
        <span class="tl-name">${t.name.replace(/_/g,' ')}</span>
        <span class="tl-away">${away}</span>
      </div>`;
    });

    // AutoPilot
    const apList = el('ap-list');
    apList.innerHTML = '';
    if (d.autopilot.recent && d.autopilot.recent.length > 0) {
      d.autopilot.recent.forEach(t => {
        const h = Math.floor(t.mins_ago / 60);
        const m = t.mins_ago % 60;
        const ago = h > 0 ? `${h}h ${m}m ago` : `${m}m ago`;
        apList.innerHTML += `<div class="mini-item">
          ${dot('blue')}
          <div>
            <div>${t.name.replace(/_/g,' ')}</div>
            <div style="margin-top:2px;color:var(--muted);font-size:11px">${ago}</div>
          </div>
        </div>`;
      });
    } else {
      apList.innerHTML = '<div style="color:var(--muted);font-size:12px">No triggers fired yet</div>';
    }

    // Chat
    const chatWrap = el('chat-list');
    chatWrap.innerHTML = '';
    (d.memory.recent_msgs || []).reverse().forEach(m => {
      const cls = m.role === 'user' ? 'chat-user' : 'chat-director';
      const who = m.role === 'user' ? '👤 You' : '🤖 Director';
      chatWrap.innerHTML += `<div class="chat-bubble ${cls}">
        <div style="font-size:10px;color:var(--muted);margin-bottom:2px">${who} · ${m.time}</div>
        ${m.content}
      </div>`;
    });
    if (!d.memory.recent_msgs || d.memory.recent_msgs.length === 0) {
      chatWrap.innerHTML = '<div style="color:var(--muted);font-size:12px">No messages yet</div>';
    }

    // Long-term events
    const ltList = el('lt-list');
    ltList.innerHTML = '';
    if (d.memory.lt_events && d.memory.lt_events.length > 0) {
      d.memory.lt_events.forEach(e => {
        const c = CAT_COLORS[e.category] || 'muted';
        const imp = IMP_ICON[e.importance] || '⚪';
        ltList.innerHTML += `<div class="mini-item">
          ${dot(c)}
          <div>
            <div>${imp} ${e.title.slice(0,55)}</div>
            <div style="margin-top:2px">${badge(e.category, c)} <span style="color:var(--muted);font-size:10px">${e.date}</span></div>
          </div>
        </div>`;
      });
    } else {
      ltList.innerHTML = '<div style="color:var(--muted);font-size:12px">No long-term events yet — use memory.remember() to log milestones</div>';
    }

    // Business facts
    const ft = el('facts-table');
    ft.innerHTML = '';
    if (d.memory.biz_facts && d.memory.biz_facts.length > 0) {
      d.memory.biz_facts.forEach(f => {
        ft.innerHTML += `<tr><td>${f.key}</td><td style="color:var(--muted);font-size:10px">${f.updated}</td><td>${f.value}</td></tr>`;
      });
      el('facts-empty').textContent = '';
    } else {
      el('facts-empty').textContent = 'No facts stored yet — use memory.set_fact("key", value)';
    }

    // Memory stats
    el('m-msgs').textContent = d.memory.messages;
    el('m-lt').textContent = d.memory.long_term_events;
    el('m-facts').textContent = d.memory.business_facts;
    el('m-sched').textContent = d.schedule.total_tasks;
    el('m-ideas').textContent = d.ideas_count;

    const memPct = Math.min(100, Math.round(d.memory.messages / 5));
    el('mem-bar').style.width = memPct + '%';
    el('mem-pct-lbl').textContent = d.memory.messages + ' / 500';

  } catch(e) {
    console.error('Failed to load data:', e);
  }
}

// Live clock
function updateClock() {
  // IST = UTC + 5:30
  const now = new Date(new Date().getTime() + 5.5*3600*1000);
  const h = String(now.getUTCHours()).padStart(2,'0');
  const m = String(now.getUTCMinutes()).padStart(2,'0');
  const s = String(now.getUTCSeconds()).padStart(2,'0');
  const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const day = days[now.getUTCDay()];
  const date = now.getUTCDate();
  const mon = months[now.getUTCMonth()];
  const yr = now.getUTCFullYear();
  el('live-time').textContent = `${day}, ${date} ${mon} ${yr} · ${h}:${m}:${s} IST`;
}

// Init
loadData();
setInterval(updateClock, 1000);
setInterval(loadData, 30000); // auto-refresh every 30s
</script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress access logs

    def do_GET(self):
        if self.path == "/api":
            data = build_api_data()
            body = json.dumps(data, ensure_ascii=False, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


def main():
    os.chdir(ROOT)
    server = http.server.HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"\n🦅 Falcon Agency Dashboard")
    print(f"   URL: http://localhost:{PORT}")
    print(f"   API: http://localhost:{PORT}/api")
    print(f"   Auto-refreshes every 30s\n")
    print("   Press Ctrl+C to stop\n")

    # Open browser after 1s
    def _open():
        time.sleep(1)
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Dashboard stopped.")


if __name__ == "__main__":
    main()
