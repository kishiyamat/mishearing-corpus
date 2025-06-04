#!/usr/bin/env python
"""
Generate datapackage.json with the current CSV shards.
Run this *before* frictionless validate.
"""

import json, glob, pathlib

SCHEMA = "schema/mishearing.schema.json"
PATTERN = "data/mishearing/**/*.csv"  # 再帰的に全サブディレクトリを対象

resources = [{
    "name": "mishearing",
    "profile": "tabular-data-resource",
    "path": sorted(glob.glob(PATTERN, recursive=True)),   # full list, no wildcard
    "schema": SCHEMA
}]

dp = {
    "profile": "tabular-data-package",
    "resources": resources
}

pathlib.Path("datapackage.json").write_text(
    json.dumps(dp, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"✅  datapackage.json updated ({len(resources[0]['path'])} shard(s))")
