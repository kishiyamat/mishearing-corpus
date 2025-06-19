#!/usr/bin/env python3
import re, sys, pathlib
# 修正された正規表現: 日付部分を削除し、アスタリスクやドットなどの特殊文字を避ける
PATTERN = re.compile(r"^[A-Za-z0-9-]+\.csv$")

def main(paths):
    bad = []
    for p in paths:
        p = pathlib.Path(p)
        if p.suffix == ".csv":  # Removed the condition checking for 'mishearing' in path
            if not PATTERN.match(p.name):
                bad.append(str(p))
    if bad:
        print("Invalid CSV filenames:\n " + "\n ".join(bad))
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1:])
