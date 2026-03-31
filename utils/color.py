#!/usr/bin/env python3
"""
Color definitions and print function
"""

class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def cprint(color, text, end='\n'):
    print(f"{color}{text}{Color.END}", end=end)
