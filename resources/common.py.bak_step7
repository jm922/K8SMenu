#!/usr/bin/env python3
"""
Common functions for resources (Pod, Deployment)
"""

import subprocess
import json
from utils.color import cprint, Color
from utils.lang import t

def get_pod_list_with_numbers():
    result = subprocess.run(['kubectl', 'get', 'pods', '-o', 'wide'], capture_output=True, text=True)
    if result.returncode != 0:
        return None, None, result.stderr
    lines = result.stdout.strip().split('\n')
    if len(lines) <= 1:
        return [], {}, None
    pod_names = []
    pod_data = []
    for line in lines[1:]:
        if line.strip():
            parts = line.split()
            if len(parts) >= 7:
                pod_names.append(parts[0])
                pod_data.append({
                    'name': parts[0],
                    'ready': parts[1],
                    'status': parts[2],
                    'restarts': parts[3],
                    'age': parts[4],
                    'ip': parts[5],
                    'node': parts[6]
                })
    pod_map = {}
    numbered_list = []
    for idx, name in enumerate(pod_names, 1):
        pod_map[str(idx)] = name
        pod_map[name] = name
        numbered_list.append((idx, name, pod_data[idx-1]))
    return numbered_list, pod_map, result.stdout

def get_deployment_list_with_numbers():
    result = subprocess.run(['kubectl', 'get', 'deployments', '-o', 'wide'], capture_output=True, text=True)
    if result.returncode != 0:
        return None, None, result.stderr
    lines = result.stdout.strip().split('\n')
    if len(lines) <= 1:
        return [], {}, None
    dep_names = []
    dep_data = []
    for line in lines[1:]:
        if line.strip():
            parts = line.split()
            if len(parts) >= 7:
                dep_names.append(parts[0])
                dep_data.append({
                    'name': parts[0],
                    'ready': parts[1],
                    'up_to_date': parts[2],
                    'available': parts[3],
                    'age': parts[4],
                    'containers': parts[5] if len(parts) > 5 else '',
                    'images': parts[6] if len(parts) > 6 else ''
                })
    dep_map = {}
    numbered_list = []
    for idx, name in enumerate(dep_names, 1):
        dep_map[str(idx)] = name
        dep_map[name] = name
        numbered_list.append((idx, name, dep_data[idx-1]))
    return numbered_list, dep_map, result.stdout

def get_deployment_replicaset_pod_info():
    rs_cmd = subprocess.run(['kubectl', 'get', 'rs', '-o', 'json'], capture_output=True, text=True)
    if rs_cmd.returncode != 0:
        return {}
    rs_data = json.loads(rs_cmd.stdout)
    
    pod_cmd = subprocess.run(['kubectl', 'get', 'pods', '-o', 'json'], capture_output=True, text=True)
    if pod_cmd.returncode != 0:
        return {}
    pod_data = json.loads(pod_cmd.stdout)
    
    rs_pod_names = {}
    for item in pod_data.get('items', []):
        owner_refs = item.get('metadata', {}).get('ownerReferences', [])
        for ref in owner_refs:
            if ref.get('kind') == 'ReplicaSet':
                rs_uid = ref.get('uid')
                if rs_uid not in rs_pod_names:
                    rs_pod_names[rs_uid] = []
                rs_pod_names[rs_uid].append(item.get('metadata', {}).get('name'))
    
    dep_to_rss = {}
    for item in rs_data.get('items', []):
        owner_refs = item.get('metadata', {}).get('ownerReferences', [])
        for ref in owner_refs:
            if ref.get('kind') == 'Deployment':
                dep_uid = ref.get('uid')
                rs_name = item.get('metadata', {}).get('name')
                creation = item.get('metadata', {}).get('creationTimestamp', '')
                rs_uid = item.get('metadata', {}).get('uid')
                if dep_uid not in dep_to_rss:
                    dep_to_rss[dep_uid] = []
                dep_to_rss[dep_uid].append((creation, rs_name, rs_uid))
    
    dep_name_to_uid = {}
    for item in rs_data.get('items', []):
        for ref in item.get('metadata', {}).get('ownerReferences', []):
            if ref.get('kind') == 'Deployment':
                dep_name = ref.get('name')
                dep_uid = ref.get('uid')
                dep_name_to_uid[dep_name] = dep_uid
                break
    
    result = {}
    for dep_uid, rs_list in dep_to_rss.items():
        if not rs_list:
            continue
        rs_list.sort(key=lambda x: x[0], reverse=True)
        newest_rs_name = rs_list[0][1]
        newest_rs_uid = rs_list[0][2]
        pod_names = rs_pod_names.get(newest_rs_uid, [])
        total = len(pod_names)
        display_names = pod_names[:3]
        pod_names_str = ', '.join(display_names)
        if total > 3:
            pod_names_str += f' ... (total {total})'
        for name, uid in dep_name_to_uid.items():
            if uid == dep_uid:
                result[name] = {
                    'replicaset': newest_rs_name,
                    'pod_names': pod_names_str,
                    'total_pods': total
                }
                break
    return result

def resolve_pod_identifier(identifier, pod_map):
    if identifier in pod_map:
        return pod_map[identifier]
    return None

def resolve_deployment_identifier(identifier, dep_map):
    if identifier in dep_map:
        return dep_map[identifier]
    return None
