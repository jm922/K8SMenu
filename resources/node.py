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


def _input_yes_no(prompt, default=False):
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        value = input(f"{prompt} {suffix}: ").strip().lower()
        if value == "":
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        cprint(Color.YELLOW, "Please enter y or n.")


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


def _run_kubectl_apply(args):
    cmd = ["kubectl"] + args
    _print_command(cmd)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    ok = result.returncode == 0
    output = (result.stdout or result.stderr or "").strip()
    return ok, output


def _extract_node_roles(labels):
    roles = []
    for key in labels.keys():
        if key.startswith("node-role.kubernetes.io/"):
            role = key.split("/")[-1]
            roles.append(role if role else "control-plane")

    if not roles:
        return "<none>"

    return ",".join(sorted(set(roles)))


def _get_ready_condition_status(node_obj):
    conditions = node_obj.get("status", {}).get("conditions", [])
    for cond in conditions:
        if cond.get("type") == "Ready":
            return cond.get("status", "Unknown")
    return "Unknown"


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
        ready_status = _get_ready_condition_status(item)

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
                "unschedulable": spec.get("unschedulable", False),
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


def _get_pods_on_node(node_name):
    data, err = _run_kubectl_json([
        "get", "pods", "-A",
        "--field-selector", f"spec.nodeName={node_name}"
    ])
    if err:
        return None, err

    items = data.get("items", [])
    total = len(items)
    system_pods = 0
    workload_pods = 0

    for item in items:
        ns = item.get("metadata", {}).get("namespace", "")
        if ns == "kube-system":
            system_pods += 1
        else:
            workload_pods += 1

    return {
        "total": total,
        "system": system_pods,
        "workload": workload_pods,
    }, None


def _get_cluster_node_summary():
    data, err = _run_kubectl_json(["get", "nodes"])
    if err:
        return None, err

    items = data.get("items", [])

    total_nodes = len(items)
    ready_nodes = 0
    schedulable_nodes = 0

    for item in items:
        ready_status = _get_ready_condition_status(item)
        if ready_status == "True":
            ready_nodes += 1

        if not item.get("spec", {}).get("unschedulable", False):
            schedulable_nodes += 1

    return {
        "total_nodes": total_nodes,
        "ready_nodes": ready_nodes,
        "schedulable_nodes": schedulable_nodes,
    }, None


def _evaluate_cordon_risk(node_obj, pod_summary, cluster_summary):
    labels = node_obj.get("metadata", {}).get("labels", {})
    roles = _extract_node_roles(labels)
    is_control_plane = (
        "control-plane" in roles
        or "master" in roles
    )

    schedulable_now = cluster_summary["schedulable_nodes"]
    already_unschedulable = node_obj.get("spec", {}).get("unschedulable", False)
    schedulable_after = schedulable_now if already_unschedulable else max(schedulable_now - 1, 0)

    workload_pods = pod_summary["workload"]

    risk = "LOW"
    notes = []

    if is_control_plane:
        risk = "HIGH"
        notes.append("This node appears to be a control-plane node.")

    if workload_pods > 0 and risk != "HIGH":
        risk = "MEDIUM"
        notes.append("This node currently has workload pods running on it.")

    if schedulable_after <= 1 and risk == "LOW":
        risk = "MEDIUM"
        notes.append("Few schedulable nodes will remain after cordon.")
    elif schedulable_after <= 1 and risk == "MEDIUM":
        risk = "HIGH"
        notes.append("Very few schedulable nodes will remain after cordon.")

    if already_unschedulable:
        notes.append("This node is already cordoned.")

    notes.append("Existing pods will keep running.")
    notes.append("New pods will not be scheduled to this node after cordon.")

    return risk, notes, schedulable_after


def _show_cordon_precheck(node_name):
    print(f"\n--- Cordon Pre-Check: {node_name} ---")

    node_obj, err = _run_kubectl_json(["get", "node", node_name])
    if err:
        cprint(Color.RED, f"Failed to collect node information: {err}")
        return None

    pod_summary, err = _get_pods_on_node(node_name)
    if err:
        cprint(Color.RED, f"Failed to collect pod placement summary: {err}")
        return None

    cluster_summary, err = _get_cluster_node_summary()
    if err:
        cprint(Color.RED, f"Failed to collect cluster node summary: {err}")
        return None

    labels = node_obj.get("metadata", {}).get("labels", {})
    roles = _extract_node_roles(labels)
    already_unschedulable = node_obj.get("spec", {}).get("unschedulable", False)
    ready_status = _get_ready_condition_status(node_obj)
    current_status = "Ready" if ready_status == "True" else "NotReady"

    risk, notes, schedulable_after = _evaluate_cordon_risk(
        node_obj,
        pod_summary,
        cluster_summary
    )

    print(f"Node role:                {roles}")
    print(f"Already cordoned:         {'Yes' if already_unschedulable else 'No'}")
    print(f"Current status:           {current_status}")
    print(f"Pods on this node:        {pod_summary['total']} total")
    print(f"System pods:              {pod_summary['system']}")
    print(f"Workload pods:            {pod_summary['workload']}")
    print(f"Ready nodes:              {cluster_summary['ready_nodes']} / {cluster_summary['total_nodes']}")
    print(f"Schedulable nodes now:    {cluster_summary['schedulable_nodes']}")
    print(f"Schedulable after cordon: {schedulable_after}")
    print(f"Risk level:               {risk}")

    print("\nNote:")
    for note in notes:
        print(f"- {note}")

    return {
        "already_unschedulable": already_unschedulable,
        "risk": risk,
        "schedulable_after": schedulable_after,
    }


def cordon_node():
    node_name = _select_node()
    if not node_name:
        return

    precheck = _show_cordon_precheck(node_name)
    if precheck is None:
        _pause()
        return

    if precheck["already_unschedulable"]:
        cprint(Color.YELLOW, "This node is already cordoned. No action is required.")
        _pause()
        return

    print(f"\n--- Cordon Node: {node_name} ---")
    print("This will mark the node as unschedulable.")
    print("New Pods will not be scheduled onto this node.")
    print("Existing Pods will continue running.")

    if not _input_yes_no("Proceed with cordon?", default=False):
        cprint(Color.YELLOW, "Cordon cancelled.")
        _pause()
        return

    ok, output = _run_kubectl_apply(["cordon", node_name])

    if ok:
        cprint(Color.GREEN, "Node cordon command succeeded.")
        if output:
            print(output)
    else:
        cprint(Color.RED, "Node cordon command failed.")
        if output:
            print(output)

    _pause()


def uncordon_node():
    node_name = _select_node()
    if not node_name:
        return

    print(f"\n--- Uncordon Node: {node_name} ---")
    print("This will mark the node as schedulable again.")
    print("New Pods may be scheduled onto this node.")

    if not _input_yes_no("Proceed with uncordon?", default=False):
        cprint(Color.YELLOW, "Uncordon cancelled.")
        _pause()
        return

    ok, output = _run_kubectl_apply(["uncordon", node_name])

    if ok:
        cprint(Color.GREEN, "Node uncordon command succeeded.")
        if output:
            print(output)
    else:
        cprint(Color.RED, "Node uncordon command failed.")
        if output:
            print(output)

    _pause()


def drain_node_preview_placeholder():
    print("\n--- Drain Node (Under Development) ---")
    cprint(Color.YELLOW, "This feature is under development.")
    print("Drain requires broader validation because:")
    print("- Deployment workflows are still being updated.")
    print("- Other workload modules are not fully implemented yet.")
    print("- Drain behavior is harder to validate safely in the current stage.")
    print("\nPlanned direction:")
    print("- Drain pre-check")
    print("- Pod impact summary")
    print("- Risk analysis")
    print("- Full drain command preview before execution")
    _pause()


def node_menu():
    while True:
        print("\n--- Node Management ---")
        print("1. List Nodes (overview)")
        print("2. Describe Node (kubectl describe)")
        print("3. View Node Conditions")
        print("4. View Node Resource Summary")
        print("5. Cordon Node (mark unschedulable)")
        print("6. Uncordon Node (mark schedulable)")
        print("7. Drain Node (under development)")
        print("8. Back (return)")

        choice = input("Choose (1-8): ").strip()

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
            cordon_node()
        elif choice == "6":
            uncordon_node()
        elif choice == "7":
            drain_node_preview_placeholder()
        elif choice == "8":
            break
        else:
            cprint(Color.RED, "Invalid option.")
