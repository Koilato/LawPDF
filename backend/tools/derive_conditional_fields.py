"""Compatibility wrapper around build_logical_json for older imports."""

from __future__ import annotations

from independent_case_pipeline.backend.tools.build_logical_json import build_logical as build_derived_fields
from independent_case_pipeline.backend.tools.build_logical_json import build_logical_from_config as build_derived_fields_from_config
from independent_case_pipeline.backend.tools.build_logical_json import main, parse_args, read_json, read_rules_config, write_json

__all__ = [
    'build_derived_fields',
    'build_derived_fields_from_config',
    'main',
    'parse_args',
    'read_json',
    'read_rules_config',
    'write_json',
]
