#!/usr/bin/env python
## @file manage.py
#  @brief Django management utility entry point.
#
#  Standard Django `manage.py` generated for the weatherview_project.
#  Run Django management commands with `python manage.py <command>`.
#
#  @author Jari Jankkila
#  @date 2026

import os
import sys


def main():
    """@brief Run administrative tasks via the Django management framework."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weatherview_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
