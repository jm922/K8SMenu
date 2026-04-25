#!/usr/bin/env python3
"""
Node management functions
"""

import json
import subprocess

from utils.color import cprint, Color


def _pause():
    input("\nPress Enter to continue...")


def _input_required(prompt):
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        cprint(Color.YELLOW, "Input cannot be empty.")


def _truncate(text, length):
    text = "" if text is None else str(text)
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def _print_command(cmd):
    print("\n" + "-" * 72)
    cprint(Color.BOLD + Color.YELLOW, "Executing command")
    cprint(Color.YELLOW, " ".join(cmd))
    print("-" * 72)


def _run_kubectl_json(args):
    cmd = ["kubectl"] + args + ["-o", "json"]
    _print_command(cmd)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()

    try:
        return json.loads(result.stdout), None
    except Exception as e:
        return None, str(e)


def _run_kubectl_text(args):
    cmd = ["kubectl"] + args
    _print_command(cmd)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()

    return result.stdout, None


def _extract_node_roles(labels):
    roles = []
    for key in labels.keys():
        if key.startswith("node-role.kubernetes.io/"):
            role = key.split("/")[-1]
            roles.append(role if role else "control-plane")

    if not roles:
        return "<none>"

    return ",".join(sorted(set(roles)))


def _parse_k8s_quantity_to_decimal_bytes(value):
    """
    Convert common Kubernetes storage/memory quantity strings into decimal bytes.
    Supports:
    - Ki, Mi, Gi, Ti, Pi, Ei
    - K, M, G, T, P, E
    - plain integer bytes
    Returns int bytes or None
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    binary_units = {
        "Ki": 1024,
        "Mi": 1024 ** 2,
        "Gi": 1024 ** 3,
        "Ti": 1024 ** 4,
        "Pi": 1024 ** 5,
        "Ei": 1024 ** 6,
    }

    decimal_units = {
        "K": 1000,
        "M": 1000 ** 2,
        "G": 1000 ** 3,
        "T": 1000 ** 4,
        "P": 1000 ** 5,
        "E": 1000 ** 6,
    }

    for unit, multiplier in binary_units.items():
        if text.endswith(unit):
            number = text[:-len(unit)].strip()
            try:
                return int(float(number) * multiplier)
            except ValueError:
                return None

    for unit, multiplier in decimal_units.items():
        if text.endswith(unit):
            number = text[:-len(unit)].strip()
            try:
                return int(float(number) * multiplier)
            except ValueError:
                return None

    try:
        return int(text)
    except ValueError:
        return None


def _format_decimal_bytes_human(value):
    """
    Display bytes in decimal GB/MB for easier reading.
    - >= 1 GB => GB
    - otherwise => MB
    """
    byte_value = _parse_k8s_quantity_to_decimal_bytes(value)
    if byte_value is None:
        return str(value) if value is not None else "-"

    gb = 1000 ** 3
    mb = 1000 ** 2

    if byte_value >= gb:
        return f"{byte_value / gb:.2f} GB"
    return f"{byte_value / mb:.2f} MB"


def _format_reserved_decimal_bytes(capacity, allocatable):
    cap_bytes = _parse_k8s_quantity_to_decimal_bytes(capacity)
    all_bytes = _parse_k8s_quantity_to_decimal_bytes(allocatable)

    if cap_bytes is None or all_bytes is None:
        return "-"

    reserved = cap_bytes - all_bytes
    if reserved < 0:
        reserved = 0

    gb = 1000 ** 3
    mb = 1000 ** 2

    if reserved >= gb:
        return f"{reserved / gb:.2f} GB"
    return f"{reserved / mb:.2f} MB"


def list_nodes_with_numbers():
    """
    Show numbered node list and return:
    - numbered_list
    - node_map
    """
    print("\n--- Current Node List ---")

    data, err = _run_kubectl_json(["get", "nodes"])
    if err:
        cprint(Color.RED, f"Failed to list nodes: {err}")
        return None, None

    items = data.get("items", [])
    if not items:
        cprint(Color.YELLOW, "No nodes found.")
        return [], {}

    node_data = []

    for item in items:
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        spec = item.get("spec", {})

        name = metadata.get("name", "")
        labels = metadata.get("labels", {})
        node_info = status.get("nodeInfo", {})
        conditions = status.get("conditions", [])

        ready_status = "Unknown"
        for cond in conditions:
            if cond.get("type") == "Ready":
                ready_status = cond.get("status", "Unknown")
                break

        status_text = "Ready" if ready_status == "True" else "NotReady"
        if spec.get("unschedulable"):
            status_text += ",SchedulingDisabled"

        roles = _extract_node_roles(labels)
        version = node_info.get("kubeletVersion", "Unknown")
        os_image = node_info.get("osImage", "Unknown")
        internal_ip = ""
        addresses = status.get("addresses", [])
        for addr in addresses:
            if addr.get("type") == "InternalIP":
                internal_ip = addr.get("address", "")
                break

        node_data.append(
            {
                "name": name,
                "status": status_text,
                "roles": roles,
                "version": version,
                "ip": internal_ip,
                "os": os_image,
            }
        )

    print(
        f"{Color.BOLD}{Color.CYAN}"
        f"{'#':<4} {'Name':<25} {'Status':<24} {'Roles':<20} {'Version':<12} {'InternalIP':<16} {'OS':<35}"
        f"{Color.END}"
    )
    print("-" * 150)

    for idx, item in enumerate(node_data, 1):
        print(
            f"{Color.GREEN}{idx:<4}{Color.END} "
            f"{item['name']:<25} "
            f"{item['status']:<24} "
            f"{_truncate(item['roles'], 20):<20} "
            f"{item['version']:<12} "
            f"{item['ip']:<16} "
            f"{_truncate(item['os'], 35):<35}"
        )

    numbered_list = []
    node_map = {}

    for idx, item in enumerate(node_data, 1):
        numbered_list.append((idx, item["name"], item))
        node_map[str(idx)] = item["name"]
        node_map[item["name"]] = item["name"]

    return numbered_list, node_map


def _select_node():
    numbered_list, node_map = list_nodes_with_numbers()
    if numbered_list is None:
        _pause()
        return None
    if not numbered_list:
        _pause()
        return None

    identifier = _input_required("Enter node number or name")
    node_name = node_map.get(identifier)

    if not node_name:
        cprint(Color.RED, f"Node not found: {identifier}")
        _pause()
        return None

    return node_name


def describe_node():
    node_name = _select_node()
    if not node_name:
        return

    print(f"\nFetching details for node '{node_name}'...")
    output, err = _run_kubectl_text(["describe", "node", node_name])

    if err:
        cprint(Color.RED, f"Failed to describe node: {err}")
    else:
        print(output)

    _pause()


def view_node_conditions():
    node_name = _select_node()
    if not node_name:
        return

    data, err = _run_kubectl_json(["get", "node", node_name])
    if err:
        cprint(Color.RED, f"Failed to get node conditions: {err}")
        _pause()
        return

    conditions = data.get("status", {}).get("conditions", [])

    print(f"\n--- Node Conditions: {node_name} ---")

    if not conditions:
        cprint(Color.YELLOW, "No node conditions found.")
        _pause()
        return

    print(
        f"{Color.BOLD}{Color.CYAN}"
        f"{'Type':<20} {'Status':<10} {'Reason':<28} {'Message':<70}"
        f"{Color.END}"
    )
    print("-" * 130)

    for cond in conditions:
        cond_type = cond.get("type", "")
        status = cond.get("status", "")
        reason = cond.get("reason", "")
        message = _truncate(cond.get("message", ""), 70)

        color = Color.GREEN if status == "True" and cond_type == "Ready" else Color.YELLOW
        print(
            f"{cond_type:<20} "
            f"{color}{status:<10}{Color.END} "
            f"{_truncate(reason, 28):<28} "
            f"{message:<70}"
        )

    _pause()


def view_node_resource_summary():
    node_name = _select_node()
    if not node_name:
        return

    data, err = _run_kubectl_json(["get", "node", node_name])
    if err:
        cprint(Color.RED, f"Failed to get node resource summary: {err}")
        _pause()
        return

    status = data.get("status", {})
    capacity = status.get("capacity", {})
    allocatable = status.get("allocatable", {})

    print(f"\n--- Node Resource Summary: {node_name} ---")

    print(
        f"{Color.BOLD}{Color.CYAN}"
        f"{'Resource':<22} {'Capacity':<18} {'Allocatable':<18} {'Reserved':<18}"
        f"{Color.END}"
    )
    print("-" * 80)

    shown = False

    resource_order = [
        "cpu",
        "memory",
        "ephemeral-storage",
        "pods",
        "hugepages-1Gi",
        "hugepages-2Mi",
        "nvidia.com/gpu",
    ]

    for resource in resource_order:
        if resource not in capacity and resource not in allocatable:
            continue

        cap_val = capacity.get(resource, "-")
        all_val = allocatable.get(resource, "-")

        if resource == "cpu":
            cap_show = f"{cap_val} cores"
            all_show = f"{all_val} cores"
            try:
                reserved = str(float(cap_val) - float(all_val)).rstrip("0").rstrip(".")
            except Exception:
                reserved = "-"
            res_show = f"{reserved} cores" if reserved != "-" else "-"
        elif resource == "pods":
            cap_show = f"{cap_val} pods"
            all_show = f"{all_val} pods"
            try:
                reserved = str(int(cap_val) - int(all_val))
            except Exception:
                reserved = "-"
            res_show = f"{reserved} pods" if reserved != "-" else "-"
        elif resource in ("memory", "ephemeral-storage"):
            cap_show = _format_decimal_bytes_human(cap_val)
            all_show = _format_decimal_bytes_human(all_val)
            res_show = _format_reserved_decimal_bytes(cap_val, all_val)
        else:
            cap_show = str(cap_val)
            all_show = str(all_val)
            res_show = "-"

        print(
            f"{resource:<22} "
            f"{cap_show:<18} "
            f"{all_show:<18} "
            f"{res_show:<18}"
        )
        shown = True

    extra_keys = sorted(set(capacity.keys()) | set(allocatable.keys()))
    for resource in extra_keys:
        if resource in resource_order:
            continue

        cap_val = capacity.get(resource, "-")
        all_val = allocatable.get(resource, "-")

        print(
            f"{resource:<22} "
            f"{str(cap_val):<18} "
            f"{str(all_val):<18} "
            f"{'-':<18}"
        )
        shown = True

    if not shown:
        cprint(Color.YELLOW, "No resource data found.")
        _pause()
        return

    print("\nNote:")
    print("- Memory and storage are shown in decimal units (GB/MB) for easier reading.")
    print("- CPU is shown as logical cores available on the node.")
    print("- Pods means the maximum number of Pods allowed on this node.")

    _pause()


def node_menu():
    while True:
        print("\n--- Node Management ---")
        print("1. List Nodes (overview)")
        print("2. Describe Node (kubectl describe)")
        print("3. View Node Conditions")
        print("4. View Node Resource Summary")
        print("5. Back (return)")

        choice = input("Choose (1-5): ").strip()

        if choice == "1":
            list_nodes_with_numbers()
            _pause()
        elif choice == "2":
            describe_node()
        elif choice == "3":
            view_node_conditions()
        elif choice == "4":
            view_node_resource_summary()
        elif choice == "5":
            break
        else:
            cprint(Color.RED, "Invalid option.")
