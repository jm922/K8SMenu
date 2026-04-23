#!/usr/bin/env python3
"""
K8S startup pre-check module.
Non-blocking startup checks before entering the main menu.
All comments and print messages are in English.
"""

import shutil
import subprocess

from utils.color import cprint, Color


def _run_cmd(cmd, timeout=10):
    """
    Run a shell command and return:
    (success: bool, stdout: str, stderr: str, returncode: int)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out", 124
    except Exception as e:
        return False, "", str(e), 1


def _simplify_error(raw_error):
    """
    Convert raw kubectl or TLS errors into short human-readable messages.
    """
    if not raw_error:
        return "Unknown error"

    err = raw_error.strip()
    lower = err.lower()

    if "x509" in lower or "certificate has expired" in lower or "tls:" in lower:
        return "TLS/certificate validation failed"
    if "connection refused" in lower:
        return "API server connection refused"
    if "context deadline exceeded" in lower or "timed out" in lower or "i/o timeout" in lower:
        return "API server request timed out"
    if "unauthorized" in lower:
        return "Authentication failed"
    if "forbidden" in lower:
        return "Authorization failed"
    if "no such host" in lower:
        return "API server host resolution failed"
    if "current-context is not set" in lower:
        return "kubectl current context is not set"
    if "not found" in lower and "kubectl" in lower:
        return "kubectl command not found"

    first_line = err.splitlines()[0].strip()
    return first_line if first_line else "Unknown error"


def _parse_node_summary(nodes_output):
    """
    Parse 'kubectl get nodes --no-headers' output and return:
    total_nodes, ready_nodes
    """
    if not nodes_output.strip():
        return 0, 0

    total = 0
    ready = 0

    for line in nodes_output.splitlines():
        line = line.strip()
        if not line:
            continue

        total += 1
        parts = line.split()
        if len(parts) >= 2:
            status_col = parts[1]
            if status_col.startswith("Ready"):
                ready += 1

    return total, ready


def _print_line(label, value, color=None):
    prefix = f"{label:<22}"
    if color:
        print(prefix, end="")
        cprint(color, value)
    else:
        print(f"{prefix}{value}")


def _print_step_header(step_no, title):
    print(f"\n[{step_no}] {title}")


def _print_command(cmd):
    command_text = " ".join(cmd)
    print(f"    Command: {command_text}")


def run_startup_precheck():
    """
    Run startup pre-check in non-blocking mode.

    Behavior:
    - HEALTHY: continue automatically
    - DEGRADED / UNAVAILABLE: show warning and require Enter to continue
    """
    status = "HEALTHY"
    notes = []

    kubectl_ok = False
    context_ok = False
    api_ok = False
    nodes_ok = False

    kubectl_version = "N/A"
    current_context = "N/A"
    api_reason = ""
    node_summary = "N/A"

    print("\n" + "=" * 48)
    cprint(Color.BOLD, "K8S Startup Pre-Check")
    print("=" * 48)

    # 1. kubectl availability
    _print_step_header("1/4", "Check kubectl client availability")
    kubectl_cmd = ["kubectl", "version", "--client"]
    _print_command(kubectl_cmd)

    kubectl_path = shutil.which("kubectl")
    if not kubectl_path:
        status = "UNAVAILABLE"
        kubectl_version = "FAILED"
        notes.append("kubectl is not installed or not in PATH.")
        cprint(Color.RED, "    Result: FAILED")
    else:
        ok, out, err, _ = _run_cmd(kubectl_cmd, timeout=8)
        if ok:
            kubectl_ok = True
            kubectl_version = out.splitlines()[0] if out else f"OK ({kubectl_path})"
            cprint(Color.GREEN, "    Result: OK")
        else:
            status = "UNAVAILABLE"
            kubectl_version = "FAILED"
            notes.append(_simplify_error(err or out))
            cprint(Color.RED, "    Result: FAILED")

    # 2. current context
    _print_step_header("2/4", "Check kubectl current context")
    context_cmd = ["kubectl", "config", "current-context"]
    _print_command(context_cmd)

    if kubectl_ok:
        ok, out, err, _ = _run_cmd(context_cmd, timeout=8)
        if ok and out:
            context_ok = True
            current_context = out
            cprint(Color.GREEN, "    Result: OK")
        else:
            if status != "UNAVAILABLE":
                status = "DEGRADED"
            current_context = "FAILED"
            notes.append(_simplify_error(err or out))
            cprint(Color.RED, "    Result: FAILED")
    else:
        cprint(Color.YELLOW, "    Result: SKIPPED")

    # 3. API server reachability
    _print_step_header("3/4", "Check API server reachability")
    api_cmd = ["kubectl", "get", "ns", "--request-timeout=5s", "--no-headers"]
    _print_command(api_cmd)

    if kubectl_ok and context_ok:
        ok, out, err, _ = _run_cmd(api_cmd, timeout=10)
        if ok:
            api_ok = True
            cprint(Color.GREEN, "    Result: OK")
        else:
            if status != "UNAVAILABLE":
                status = "DEGRADED"
            api_reason = _simplify_error(err or out)
            notes.append(api_reason)
            cprint(Color.RED, "    Result: FAILED")
    else:
        cprint(Color.YELLOW, "    Result: SKIPPED")

    # 4. Node basic state
    _print_step_header("4/4", "Check node basic status")
    nodes_cmd = ["kubectl", "get", "nodes", "--no-headers"]
    _print_command(nodes_cmd)

    if api_ok:
        ok, out, err, _ = _run_cmd(nodes_cmd, timeout=10)
        if ok:
            nodes_ok = True
            total_nodes, ready_nodes = _parse_node_summary(out)
            node_summary = f"{ready_nodes} Ready / {total_nodes} Total"

            if total_nodes == 0:
                status = "DEGRADED"
                notes.append("No nodes returned by the cluster.")
                cprint(Color.YELLOW, "    Result: DEGRADED")
            elif ready_nodes < total_nodes:
                status = "DEGRADED"
                notes.append("Not all nodes are Ready.")
                cprint(Color.YELLOW, "    Result: DEGRADED")
            else:
                cprint(Color.GREEN, "    Result: OK")
        else:
            if status != "UNAVAILABLE":
                status = "DEGRADED"
            node_summary = "FAILED"
            notes.append(_simplify_error(err or out))
            cprint(Color.RED, "    Result: FAILED")
    else:
        cprint(Color.YELLOW, "    Result: SKIPPED")

    print("\n" + "-" * 48)
    cprint(Color.BOLD, "Pre-Check Summary")
    print("-" * 48)

    _print_line("kubectl:", kubectl_version, Color.GREEN if kubectl_ok else Color.RED)
    _print_line("current context:", current_context, Color.GREEN if context_ok else Color.RED)

    if api_ok:
        _print_line("API server:", "OK", Color.GREEN)
    else:
        api_value = f"FAILED ({api_reason})" if api_reason else "FAILED"
        _print_line("API server:", api_value, Color.RED)

    if nodes_ok:
        color = Color.GREEN if status == "HEALTHY" else Color.YELLOW
        _print_line("nodes:", node_summary, color)
    else:
        _print_line("nodes:", node_summary, Color.RED if node_summary == "FAILED" else None)

    if status == "HEALTHY":
        _print_line("cluster access:", status, Color.GREEN)
    elif status == "DEGRADED":
        _print_line("cluster access:", status, Color.YELLOW)
    else:
        _print_line("cluster access:", status, Color.RED)

    if notes:
        print("\nNotes:")
        seen = set()
        for note in notes:
            if note and note not in seen:
                print(f"- {note}")
                seen.add(note)

    print("=" * 48)

    if status == "HEALTHY":
        cprint(Color.GREEN, "Startup pre-check passed. Continuing to main menu...")
    else:
        cprint(Color.YELLOW, "Startup pre-check is non-blocking. You can still enter the main menu.")
        cprint(Color.YELLOW, "K8S resource operations may fail until the cluster issue is fixed.")
        input("\nPress Enter to continue to the main menu...")

    return {
        "status": status,
        "kubectl_ok": kubectl_ok,
        "context_ok": context_ok,
        "api_ok": api_ok,
        "nodes_ok": nodes_ok,
        "kubectl_version": kubectl_version,
        "current_context": current_context,
        "api_reason": api_reason,
        "node_summary": node_summary,
        "notes": notes,
    }
