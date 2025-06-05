#!/usr/bin/env python3
import re, sys, pathlib
PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(?:_[A-Za-z0-9_-]+)?\.csv$")
def main(paths):
    bad=[]
    for p in paths:
        p=pathlib.Path(p)
        if p.suffix==".csv" and p.parent.name=="mishearing":
            if not PATTERN.match(p.name):
                bad.append(str(p))
    if bad:
        print("Invalid CSV filenames:\n "+"\n ".join(bad))
        sys.exit(1)
if __name__=="__main__":
    main(sys.argv[1:])
