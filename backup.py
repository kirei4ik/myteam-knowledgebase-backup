#!/usr/bin/env python3
"""Entrypoint модуля резервного копирования базы знаний «МояКоманда».

Запуск: python backup.py [--dry-run] [--output DIR]
"""
import sys

from app.runner import main

if __name__ == "__main__":
    sys.exit(main())