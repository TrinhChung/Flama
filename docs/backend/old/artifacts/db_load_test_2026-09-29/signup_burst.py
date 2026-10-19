"""Fire N concurrent registrations at Gunicorn and report outcomes + deadlocks."""
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

import requests

BASE = "http://127.0.0.1:4789"
SOCK = os.environ.get("MYSQL_SOCKET", "/var/run/mysqld/mysqld.sock")


def deadlocks():
    out = subprocess.run(["mysql", f"--socket={SOCK}", "-uroot", "-N", "-e",
                          "SELECT count FROM information_schema.innodb_metrics WHERE name='lock_deadlocks'"],
                         capture_output=True, text=True).stdout.strip()
    return int(out or 0)


def main():
    n = int(sys.argv[1])
    outcomes = Counter()
    barrier = threading.Barrier(n)
    lock = threading.Lock()

    def one():
        s = requests.Session()
        token = s.get(f"{BASE}/api/session", timeout=60).json()["csrf_token"]
        tag = uuid4().hex[:10]
        barrier.wait()
        started = time.perf_counter()
        try:
            r = s.post(f"{BASE}/api/auth/register", timeout=120, headers={"X-CSRF-Token": token}, json={
                "email": f"{tag}@signup.test", "username": f"u{tag}", "password": "Password123!",
                "confirm_password": "Password123!"})
            key = r.status_code if r.status_code >= 400 else 302
            if r.status_code >= 400:
                key = f"{r.status_code}:{r.text[:80]}"
        except Exception as exc:  # noqa: BLE001
            key = type(exc).__name__
        with lock:
            outcomes[f"{key} ({time.perf_counter() - started:.1f}s)" if key != 302 else 302] += 1

    before = deadlocks()
    threads = [threading.Thread(target=one) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"{n} concurrent signups -> {dict(outcomes)}; InnoDB deadlocks +{deadlocks() - before}")
    out = subprocess.run(["mysql", f"--socket={SOCK}", "-uroot", "-e", "SHOW ENGINE INNODB STATUS\\G"],
                         capture_output=True, text=True).stdout
    if "LATEST DETECTED DEADLOCK" in out:
        section = out.split("LATEST DETECTED DEADLOCK")[1].split("------------\nTRANSACTIONS")[0]
        for line in section.splitlines():
            if any(k in line for k in ("SQL", "INSERT", "SELECT", "lock_mode", "WE ROLL BACK", "index")):
                print("  ", line.strip()[:200])


if __name__ == "__main__":
    main()
