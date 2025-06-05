#!/usr/bin/env python
"""
Recompute total row count in data/mishearing/**/*.csv (excluding header lines),
write badges/records.json, and update README block if desired.
"""
import csv, glob, json, pathlib, re, sys, subprocess

SHARDS = glob.glob("data/mishearing/**/*.csv", recursive=True)
TOTAL  = 0
for path in SHARDS:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)           # skip header
        TOTAL += sum(1 for _ in reader)

# 現在のブランチ名を取得
try:
    BRANCH = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
except Exception:
    BRANCH = None

# 1) save json badge source
badge_dir = pathlib.Path("badges")
badge_dir.mkdir(exist_ok=True)
badge_json = {"count": TOTAL}
if BRANCH:
    badge_json["branch"] = BRANCH
(pathlib.Path("badges/records.json")
 .write_text(json.dumps(badge_json), encoding="utf-8"))

print(f"🔢  total rows = {TOTAL}")
if BRANCH:
    print(f"🌿  branch = {BRANCH}")

# 2) optional in-README replacement between markers
READ = pathlib.Path("README.md").read_text(encoding="utf-8")
NEW  = re.sub(
    r"(?<=<!-- RECORD_CNT_START -->)(.*?)(?=<!-- RECORD_CNT_END -->)",
    str(TOTAL),
    READ,
    flags=re.S
)
if NEW != READ:
    pathlib.Path("README.md").write_text(NEW, encoding="utf-8")
    print("📝  README updated with inline count")
else:
    print("ℹ️   README badge only")
