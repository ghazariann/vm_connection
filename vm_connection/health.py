# src/vmcontrol/health.py
from __future__ import annotations

import errno
import math
import platform
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from typing import Dict

@dataclass
class ProbeResult:
    ok: bool
    reason: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None

@dataclass
class IsAliveResult:
    alive: bool
    reasons: Dict[str, str]

def udp_probe(host: str, port: int = 53, timeout_ms: int = 300) -> ProbeResult:
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout_ms / 1000.0)
    try:
        # Send a blank packet to the given UDP port
        sock.sendto(b'', (host, port))
        elapsed = (time.perf_counter() - start) * 1000.0
        return ProbeResult(True, f"{port} ok", latency_ms=elapsed)
    except socket.timeout:
        return ProbeResult(False, f"{port} timeout", error="timeout")
    except OSError as e:
        return ProbeResult(False, f"{port} os error", error=f"{e.__class__.__name__}: {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass
        
def tcp_probe(host: str, port: int = 22, timeout_ms: int = 300) -> ProbeResult:
    """
    Try a TCP connect() to (host, port).
    ok=True when:
      - connect succeeds (service listening), OR
      - we get ECONNREFUSED (RST) quickly → host stack is alive but port closed/sshd down.
    ok=False on timeouts or network failures.
    """
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_ms / 1000.0)
    try:
        code = sock.connect_ex((host, port))  # 0 = success; errno on failure
        elapsed = (time.perf_counter() - start) * 1000.0
        if code == 0:
            return ProbeResult(True, f"{port} ok", latency_ms=elapsed)
        # Refused = host responded with RST → stack alive, service closed
        if code in (errno.ECONNREFUSED, 111, 61, 10061):
            return ProbeResult(True, f"{port} refused", latency_ms=elapsed)
        # Immediate unreachable or other error codes
        return ProbeResult(False, f"{port} error {code}", latency_ms=elapsed, error=str(code))
    except socket.timeout:
        return ProbeResult(False, f"{port} timeout", error="timeout")
    except OSError as e:
        return ProbeResult(False, f"{port} os error", error=f"{e.__class__.__name__}: {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass


def icmp_probe(host: str, timeout_ms: int = 300) -> ProbeResult:
    """
    Send a single ping using the system 'ping' command (works without raw-socket privileges).
    ok=True if the command reports success. Note many networks block ICMP → failure isn't fatal.
    """
    system = platform.system().lower()
    if "windows" in system:
        # -n 1 = one echo; -w timeout_ms (milliseconds)
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        # -c 1 = one echo; -W timeout (seconds, int); -n = numeric output
        sec = max(1, math.ceil(timeout_ms / 1000.0))
        cmd = ["ping", "-c", "1", "-W", str(sec), "-n", host]

    start = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = (time.perf_counter() - start) * 1000.0
        if p.returncode == 0:
            return ProbeResult(True, "icmp ok", latency_ms=elapsed)
        # Nonzero return code → could be timeout or admin‑prohibited
        reason = "no reply"
        # if p.stderr:
        #     reason += f" ({p.stderr.strip()[:80]})"
        # elif p.stdout:
        #     reason += f" ({p.stdout.strip().splitlines()[-1][:80]})"
        return ProbeResult(False, reason, latency_ms=elapsed)
    except FileNotFoundError:
        # 'ping' not available in PATH
        return ProbeResult(False, "unavailable (no 'ping' command)")
    except Exception as e:
        return ProbeResult(False, "error", error=f"{e.__class__.__name__}: {e}")

