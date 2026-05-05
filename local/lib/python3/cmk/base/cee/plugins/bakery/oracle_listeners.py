#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# Reference for details:
# https://docs.checkmk.com/latest/en/bakery_api.html
# ---------------------------------------------------------------------------

from pathlib import Path

from .bakery_api.v1 import (
    OS,
    Plugin,
    PluginConfig,
    register,
    FileGenerator,
)

DEBUG = False  # Set to True to enable debug output

def get_oracle_listeners_plugin_files(conf: dict) -> FileGenerator:
    if DEBUG: print(f"Generating Oracle Listeners plugin files for configuration: {conf}")

    if conf.get('enabled', False):
        for base_os in (OS.LINUX, OS.AIX):
            yield Plugin(
                base_os = base_os,
                source = Path("oracle_listeners.pl"),
                target = Path("oracle_listeners.pl"),
            )

        exclude_list = conf.get('exclude', [])
        if exclude_list:
            lines = [f"EXCLUDE = {entry}" for entry in exclude_list]
            for base_os in (OS.LINUX, OS.AIX):
                yield PluginConfig(
                    base_os = base_os,
                    lines = lines,
                    target = Path("oracle_listeners.cfg"),
                )

register.bakery_plugin(
    name = "oracle_listeners",
    files_function = get_oracle_listeners_plugin_files,
)
