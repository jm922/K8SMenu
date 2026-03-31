#!/usr/bin/env python3
"""
YAML editing, validation, and vim installation helpers
"""

import os
import subprocess
import yaml
import re
from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import input_yes_no

def check_and_install_vim():
    try:
        subprocess.run(['vim', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        cprint(Color.YELLOW, t("yaml_editor_not_found"))
        if input_yes_no("yaml_editor_install_prompt", default=False):
            cprint(Color.BLUE, t("yaml_editor_installing"))
            try:
                if os.path.exists('/usr/bin/apt-get'):
                    subprocess.run(['sudo', 'apt-get', 'update'], check=True)
                    subprocess.run(['sudo', 'apt-get', 'install', '-y', 'vim'], check=True)
                elif os.path.exists('/usr/bin/yum'):
                    subprocess.run(['sudo', 'yum', 'install', '-y', 'vim'], check=True)
                elif os.path.exists('/usr/bin/dnf'):
                    subprocess.run(['sudo', 'dnf', 'install', '-y', 'vim'], check=True)
                elif os.path.exists('/usr/bin/pacman'):
                    subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'vim'], check=True)
                else:
                    cprint(Color.RED, "Unknown package manager. Please install vim manually.")
                    return False
                cprint(Color.GREEN, t("yaml_editor_install_success"))
                return True
            except subprocess.CalledProcessError as e:
                cprint(Color.RED, t("yaml_editor_install_failed"))
                cprint(Color.RED, f"Error: {e}")
                return False
        else:
            return False

def edit_yaml_with_vim(filename):
    cprint(Color.BLUE, t("yaml_editor_open", file=filename))
    cprint(Color.BLUE, t("yaml_editor_edit_hint"))
    input(t("yaml_editor_press_enter"))
    try:
        subprocess.run(['vim', filename])
        return True
    except Exception as e:
        cprint(Color.RED, f"Failed to open vim: {e}")
        return False

def validate_yaml_syntax(filename):
    cprint(Color.BLUE, t("yaml_validate"))
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            yaml.safe_load(content)
        cprint(Color.GREEN, t("yaml_validate_success"))
        return True, None, content
    except yaml.YAMLError as e:
        if hasattr(e, 'problem_mark'):
            line = e.problem_mark.line + 1
            error_msg = str(e).split('\n')[0]
            cprint(Color.RED, t("yaml_validate_fail", line=line, error=error_msg))
            return False, line, None
        else:
            cprint(Color.RED, f"YAML Error: {e}")
            return False, None, None

def validate_with_kubectl(filename):
    cprint(Color.BLUE, t("kubectl_validate"))
    try:
        result = subprocess.run(['kubectl', 'apply', '--dry-run=client', '-f', filename],
                                capture_output=True, text=True)
        if result.returncode == 0:
            cprint(Color.GREEN, t("kubectl_validate_success"))
            return True, None
        else:
            cprint(Color.RED, t("kubectl_validate_fail", error=result.stderr))
            return False, result.stderr
    except Exception as e:
        cprint(Color.RED, f"Validation error: {e}")
        return False, str(e)

def apply_yaml_file(filename):
    cprint(Color.BLUE, t("apply_pod"))
    try:
        result = subprocess.run(['kubectl', 'apply', '-f', filename],
                                capture_output=True, text=True)
        if result.returncode == 0:
            match = re.search(r'(pod|deployment\.apps)/([^ ]+)', result.stdout)
            if match:
                resource_type, name = match.groups()
                cprint(Color.GREEN, t("apply_success", name=name))
            else:
                cprint(Color.GREEN, t("apply_success", name="unknown"))
            return True
        else:
            cprint(Color.RED, t("apply_fail", error=result.stderr))
            return False
    except Exception as e:
        cprint(Color.RED, t("apply_fail", error=str(e)))
        return False
