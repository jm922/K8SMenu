#!/usr/bin/env python3
"""
Common helper functions
"""

import sys
import subprocess
import tempfile
import os
from utils.color import cprint, Color
from utils.lang import t

def check_kubectl():
    try:
        subprocess.run(['kubectl', 'version', '--client'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        cprint(Color.RED, t("kubectl_check_fail"))
        sys.exit(1)

def input_required(prompt_key):
    while True:
        val = input(f"{t(prompt_key)}: ").strip()
        if val:
            return val
        cprint(Color.YELLOW, t("input_required"))

def input_with_default(prompt_key, default):
    val = input(f"{t(prompt_key)} [default: {default}]: ").strip()
    return val if val else default

def input_yes_no(prompt_key, default=False, **kwargs):
    prompt = t(prompt_key, **kwargs)
    suffix = "[y/N]" if not default else "[Y/n]"
    val = input(f"{prompt} {suffix}: ").strip().lower()
    if not val:
        return default
    return val in ['y', 'yes']

def input_yes_no_text(prompt_text, default=False):
    suffix = "[y/N]" if not default else "[Y/n]"
    val = input(f"{prompt_text} {suffix}: ").strip().lower()
    if not val:
        return default
    return val in ['y', 'yes']

def apply_yaml(yaml_content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        tmp_file = f.name
    try:
        cprint(Color.BLUE, "\nGenerated YAML configuration:")
        print(yaml_content)
        cprint(Color.BLUE, "\nApplying configuration to cluster...")
        result = subprocess.run(['kubectl', 'apply', '-f', tmp_file],
                                capture_output=True, text=True)
        if result.returncode == 0:
            cprint(Color.GREEN, t("success") + ": " + result.stdout)
        else:
            cprint(Color.RED, t("fail") + ": " + result.stderr)
    finally:
        os.unlink(tmp_file)

def delete_resource(kind, name):
    cprint(Color.YELLOW, f"\nDeleting {kind} '{name}'...")
    result = subprocess.run(['kubectl', 'delete', kind, name],
                            capture_output=True, text=True)
    if result.returncode == 0:
        cprint(Color.GREEN, t("success") + ": " + result.stdout)
    else:
        cprint(Color.RED, t("fail") + ": " + result.stderr)
