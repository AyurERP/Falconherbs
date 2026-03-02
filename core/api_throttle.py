"""
Falcon Agency — WHM API Rate Throttle
======================================

Enforces max 5 API calls/minute per site to WHM Shared Server.
Uses a sliding window counter saved to disk (survives restarts).

Also handles retry with exponential backoff:
    Attempt 1: immediate
    Attempt 2: wait 5 seconds
    Attempt 3: wait 10 seconds
    Attempt 4: wait 20 seconds → give up

Usage (called automatically by woocommerce_connector):
    from core.api_throttle import throttle
    
    # Blocks until a call slot is available
    throttle.wait("falconherbs")
    
    # After the actual requests.get():
    throttle.record_call("falconherbs")

Or use the retry wrapper:
    result = throttle.call_with_retry(fn, site_key="falconherbs", max_attempts=4)
"""

import time
import json
from pathlib import Path
from core.ist_time import now_ist_str

# Max calls per 60-second window per site
MAX_CALLS_PER_MINUTE = 5
WINDOW_SECONDS = 60
BACKOFF_DELAYS = [0, 5, 10, 20]   # seconds before attempt 1,2,3,4


class ApiThrottle:
    """
    Per-site sliding window rate limiter.
    Call history saved in data/cache/throttle_{site_key}.json.
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._in_memory: dict = {}   # site_key → [timestamps]

    def _state_path(self, site_key: str) -> Path:
        return self.cache_dir / f"throttle_{site_key}.json"

    def _load_calls(self, site_key: str) -> list:
        """Load call timestamps from disk (floats)."""
        if site_key in self._in_memory:
            return self._in_memory[site_key]
        path = self._state_path(site_key)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                calls = data.get("calls", [])
                self._in_memory[site_key] = calls
                return calls
            except Exception:
                pass
        self._in_memory[site_key] = []
        return []

    def _save_calls(self, site_key: str, calls: list) -> None:
        """Persist call timestamps to disk."""
        self._in_memory[site_key] = calls
        path = self._state_path(site_key)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"site": site_key, "calls": calls, "updated_at": now_ist_str()}, f)
            tmp.replace(path)
        except Exception:
            tmp.unlink(missing_ok=True)

    def _get_recent_calls(self, site_key: str) -> list:
        """Return only calls within the last 60 seconds."""
        now = time.monotonic()
        calls = self._load_calls(site_key)
        recent = [t for t in calls if (now - t) < WINDOW_SECONDS]
        return recent

    def get_call_count(self, site_key: str) -> int:
        """How many calls used in current window."""
        return len(self._get_recent_calls(site_key))

    def is_throttled(self, site_key: str, max_calls: int = MAX_CALLS_PER_MINUTE) -> bool:
        """True if site has hit the call limit for this window."""
        return len(self._get_recent_calls(site_key)) >= max_calls

    def wait(self, site_key: str, max_calls: int = MAX_CALLS_PER_MINUTE) -> float:
        """
        Block until a call slot is available.
        Returns seconds waited.
        """
        waited = 0.0
        while self.is_throttled(site_key, max_calls):
            recent = self._get_recent_calls(site_key)
            # Oldest call + window — that's when next slot opens
            oldest = min(recent)
            now = time.monotonic()
            sleep_for = max(0.1, WINDOW_SECONDS - (now - oldest) + 0.5)
            print(f"  🛑 [Throttle] {site_key} at limit ({max_calls}/min). "
                  f"Waiting {sleep_for:.1f}s...")
            time.sleep(sleep_for)
            waited += sleep_for
        return waited

    def record_call(self, site_key: str) -> None:
        """Record a call for this site. Call AFTER making the request."""
        recent = self._get_recent_calls(site_key)
        recent.append(time.monotonic())
        self._save_calls(site_key, recent)

    def reset(self, site_key: str) -> None:
        """Clear call history (for testing or after errors)."""
        self._in_memory[site_key] = []
        self._state_path(site_key).unlink(missing_ok=True)

    def call_with_retry(
        self,
        fn,
        site_key: str,
        max_calls: int = MAX_CALLS_PER_MINUTE,
        max_attempts: int = 4,
    ):
        """
        Execute fn() with throttle + exponential backoff.
        
        fn must return a dict with {"success": bool, "data": ..., "error": ...}.
        
        Retries on timeout/connection errors with delays:
            [0s, 5s, 10s, 20s] before each attempt.
        
        Returns the first successful response, or last error response.
        """
        last_result = {"success": False, "error": "No attempts made"}
        
        for attempt in range(max_attempts):
            delay = BACKOFF_DELAYS[min(attempt, len(BACKOFF_DELAYS) - 1)]
            if delay > 0:
                print(f"  ⏳ [Throttle] Retry {attempt}/{max_attempts-1} "
                      f"for {site_key} — waiting {delay}s...")
                time.sleep(delay)

            # Block until quota available
            self.wait(site_key, max_calls)

            try:
                result = fn()
                self.record_call(site_key)
                
                if result.get("success"):
                    if attempt > 0:
                        print(f"  ✅ [Throttle] {site_key} succeeded on attempt {attempt + 1}")
                    return result
                
                # Retry-able errors: connection, timeout, 5xx
                err = str(result.get("error", ""))
                if any(k in err for k in ["connect", "timeout", "503", "502", "504", "Cannot"]):
                    print(f"  ⚠️ [Throttle] {site_key} transient error on attempt {attempt+1}: {err[:60]}")
                    last_result = result
                    continue
                
                # Non-retryable (e.g. 404, 401) — return immediately
                return result
                
            except Exception as e:
                last_result = {"success": False, "error": str(e)}
                print(f"  ⚠️ [Throttle] {site_key} exception on attempt {attempt+1}: {str(e)[:60]}")
                self.record_call(site_key)  # Count even failed calls
                continue
        
        print(f"  🚨 [Throttle] {site_key} failed after {max_attempts} attempts. "
              f"Last error: {last_result.get('error', '')[:80]}")
        return last_result

    def status_report(self, site_key: str) -> str:
        """Human-readable throttle status for WhatsApp/logs."""
        count = self.get_call_count(site_key)
        return (
            f"🛡️ API Throttle [{site_key}]: "
            f"{count}/{MAX_CALLS_PER_MINUTE} calls used in last 60s"
        )


# Module-level singleton
throttle = ApiThrottle()
