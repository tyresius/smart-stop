"""
Environment configuration for Smart Stop project.
Detects where code is running and sets paths accordingly.

Usage:
    from config import OUTPUT_DIR, RESULTS_FILE, ENVIRONMENT

    # Use these variables instead of hardcoded paths
    json_file = RESULTS_FILE
    output_folder = OUTPUT_DIR
"""

import os
import sys


def get_environment_paths():
    """
    Determine which environment we're in and return appropriate paths.

    Returns:
        dict: Configuration with OUTPUT_DIR, RESULTS_FILE, and ENVIRONMENT
    """

    home_dir = os.path.expanduser('~')

    # Check if we're on local system (PyCharm)
    if 'patricktyler' in home_dir or os.path.exists(os.path.expanduser('~/PycharmProjects/ClaudeStop')):
        return {
            'OUTPUT_DIR': os.path.expanduser('~/PycharmProjects/ClaudeStop/output'),
            'RESULTS_FILE': os.path.expanduser('~/PycharmProjects/ClaudeStop/comparison_results.json'),
            'COMPARISON_REPORT_TXT': os.path.expanduser('~/PycharmProjects/ClaudeStop/comparison_report.txt'),
            'COMPARISON_REPORT_JSON': os.path.expanduser('~/PycharmProjects/ClaudeStop/comparison_report.json'),
            'ENVIRONMENT': 'local'
        }

    # Check if we're in cloud (Claude environment)
    elif os.path.exists('/mnt/project'):
        return {
            'OUTPUT_DIR': '/mnt/project/output',
            'RESULTS_FILE': '/mnt/project/comparison_results.json',
            'COMPARISON_REPORT_TXT': '/mnt/project/comparison_report.txt',
            'COMPARISON_REPORT_JSON': '/mnt/project/comparison_report.json',
            'ENVIRONMENT': 'cloud'
        }

    # Fallback: use current directory
    else:
        return {
            'OUTPUT_DIR': './output',
            'RESULTS_FILE': './comparison_results.json',
            'COMPARISON_REPORT_TXT': './comparison_report.txt',
            'COMPARISON_REPORT_JSON': './comparison_report.json',
            'ENVIRONMENT': 'unknown'
        }


# Get paths for current environment
_PATHS = get_environment_paths()

# Export these for use in other modules
OUTPUT_DIR = _PATHS['OUTPUT_DIR']
RESULTS_FILE = _PATHS['RESULTS_FILE']
COMPARISON_REPORT_TXT = _PATHS['COMPARISON_REPORT_TXT']
COMPARISON_REPORT_JSON = _PATHS['COMPARISON_REPORT_JSON']
ENVIRONMENT = _PATHS['ENVIRONMENT']


# ─── Physical scale ────────────────────────────────────────────────────────
# 1 grid unit (path-coordinate unit) is defined to equal one car length so
# that the rendered intersection geometry reads naturally. With a vehicle
# length of 4.5 m, this makes 1 grid unit = 4.5 m. Path lengths under the
# current geometry (extended approach/exit segments):
#   NS/S: 6 grid units    = 27.0 m  ≈ 6.0 car lengths
#   L   : 6.785 grid u.   = 30.5 m  ≈ 6.8 car lengths
#   R   : 4.785 grid u.   = 21.5 m  ≈ 4.8 car lengths (R is naturally shortest
#                                   because the curve cuts the corner)
# All physical quantities (vehicle.max_speed, max_acceleration,
# safety_margin, etc.) are stored in real units (m, m/s, m/s²); the
# simulation converts between grid-unit path coordinates and meters via
# this constant.
METERS_PER_UNIT = 4.5


# Create output directory if it doesn't exist
def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")
    return OUTPUT_DIR


# Print configuration on import (for debugging)
if __name__ == "__main__" or os.environ.get('DEBUG_CONFIG'):
    print(f"Smart Stop Configuration")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Results file: {RESULTS_FILE}")
    print(f"Report (txt): {COMPARISON_REPORT_TXT}")
    print(f"Report (json): {COMPARISON_REPORT_JSON}")