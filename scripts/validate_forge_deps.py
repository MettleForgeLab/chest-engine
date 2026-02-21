#!/usr/bin/env python3
import argparse, sys, json, yaml
from jsonschema import Draft202012Validator

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest", default="forge-deps.yaml")
    ap.add_argument("--schema", default="forge-deps.schema.json")
    args=ap.parse_args()

    m=yaml.safe_load(open(args.manifest,"r",encoding="utf-8"))
    s=json.load(open(args.schema,"r",encoding="utf-8"))

    v=Draft202012Validator(s)
    errs=sorted(v.iter_errors(m), key=lambda e: e.path)
    if errs:
        print("[deps] FAIL")
        for e in errs:
            path=".".join(map(str,e.path)) or "(root)"
            print(f"- {path}: {e.message}")
        sys.exit(1)

    det=m.get("determinism") or {}
    if "required" not in det:
        print("[deps] FAIL: determinism.required must be declared")
        sys.exit(1)

    print("[deps] PASS")
    sys.exit(0)

if __name__=="__main__":
    main()