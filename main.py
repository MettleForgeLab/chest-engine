#!/usr/bin/env python3
import os, json, time, hashlib
from typing import Dict, Any, Optional as Opt, List
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# -------------------- Storage --------------------
REF_DIR = Path(os.getenv("REF_DIR", "./chest_memory"))
REF_DIR.mkdir(parents=True, exist_ok=True)
REFLECT_PATH = REF_DIR / "reflection.jsonl"

VERSION_FILE = Path("/app/VERSION.json")

app = FastAPI(title="Chest Engine (v0.1 minimal)", version="0.1.0")

# -------------------- In-memory registries (v0.1) --------------------
DOMAIN_REGISTRY: Dict[str, Dict[str, Any]] = {}
DOMAIN_CONTEXT = {"bundle_id": None, "bundle_version": None}
SEEN_EVENT_IDS = set()

# -------------------- Helpers --------------------
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _append_reflection(entry: Dict[str, Any]) -> None:
    entry = {**entry, "t": entry.get("t") or _now()}
    with REFLECT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_canon(obj: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()

def commit_hash_from_commit(commit: Dict[str, Any]) -> str:
    # Deterministic hash excludes event_id and volatile fields
    c = dict(commit)
    c.pop("event_id", None)
    c.pop("t", None)
    c.pop("timestamp", None)
    return sha256_canon(c)

def commit_write_once(event_id: str) -> None:
    if event_id in SEEN_EVENT_IDS:
        raise HTTPException(409, f"event_id already committed: {event_id}")
    SEEN_EVENT_IDS.add(event_id)

def _bundle_context() -> Dict[str, Any]:
    return {"bundle_id": DOMAIN_CONTEXT.get("bundle_id"), "bundle_version": DOMAIN_CONTEXT.get("bundle_version")}

def _resolve_context(role_ctx: Opt[List[str]] = None) -> Dict[str, Any]:
    # Derive from loaded bundle if available
    bundle_id = DOMAIN_CONTEXT.get("bundle_id")
    roles_avail = []
    domains_avail = []
    if bundle_id and bundle_id in DOMAIN_REGISTRY:
        roles_avail = DOMAIN_REGISTRY[bundle_id].get("role_ids", [])
        domains_avail = [d["domain_id"] for d in DOMAIN_REGISTRY[bundle_id].get("domains", [])]

    # Default role selection
    if role_ctx is None:
        if "ROLE:KINFORM" in roles_avail:
            role_ctx = ["ROLE:KINFORM"]
        elif "ROLE:HOME" in roles_avail:
            role_ctx = ["ROLE:HOME"]
        else:
            role_ctx = ["ROLE:HOME"]  # conservative fallback

    # Validate requested roles exist when we have inventory
    if roles_avail:
        for r in role_ctx:
            if r not in roles_avail:
                raise HTTPException(400, f"role_context contains unknown role: {r}")

    return {
        "bundle_context": _bundle_context(),
        "role_context": role_ctx,
        "domain_context": domains_avail,
        "roles_available": roles_avail,
        "domains_available": domains_avail,
    }

def predecode_freeze(payload: Dict[str, Any], role_ctx: List[str]) -> Dict[str, Any]:
    # Minimal deterministic predecode snapshot
    config_snapshot = payload.get("config_snapshot") or {"routing": "dual", "mode": "softfold"}
    config_hash = payload.get("config_hash") or sha256_canon(config_snapshot)

    seed = payload.get("seed")
    if seed is None:
        raise HTTPException(400, "seed required")

    routes = payload.get("routes") or {}
    routing_decision = {"mode": "dual", "a": routes.get("a"), "b": routes.get("b")}

    gating_params = payload.get("gating_params") or {"mode": "softfold", "readiness": 0.72, "gain": 1.0}

    param_block_hash = sha256_canon({
        "config_hash": config_hash,
        "seed": seed,
        "routing_decision": routing_decision,
        "gating_params": gating_params,
        "bundle_context": _bundle_context(),
        "role_context": role_ctx
    })

    telemetry_sources = [
        {"name": "config_hash", "hash": config_hash, "binding": True},
        {"name": "param_block_hash", "hash": param_block_hash, "binding": True},
    ]

    models = payload.get("models") or {}
    model_ids = {"A": (models.get("A") or {}).get("id"), "B": (models.get("B") or {}).get("id")}
    model_build_id = {
        "A": (models.get("A") or {}).get("build_id", "unknown"),
        "B": (models.get("B") or {}).get("build_id", "unknown"),
    }

    tolerance = payload.get("tolerance") or {"version": "v1", "bounds": {"floats": "1e-6"}}

    return {
        "config_hash": config_hash,
        "param_block_hash": param_block_hash,
        "seed": seed,
        "routing_decision": routing_decision,
        "gating_params": gating_params,
        "telemetry_sources": telemetry_sources,
        "model_ids": model_ids,
        "model_build_id": model_build_id,
        "tolerance": tolerance,
        "determinism_profile": "control-plane",
    }

# -------------------- Endpoints --------------------
@app.get("/version")
async def version():
    base = {}
    if VERSION_FILE.exists():
        try:
            base = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    return {
        "service": base.get("service", "chest-engine"),
        "version": base.get("version", "0.1.0"),
        "git_head": base.get("git_head", "unknown"),
        "build": {"image": base.get("image_tag", "unknown"), "digest": base.get("image_digest", "unknown")},
        "deps": base.get("deps", {}),
        "runtime": _bundle_context(),
    }

@app.get("/api/reflection/tail")
async def reflection_tail(n: int = 20):
    if not REFLECT_PATH.exists():
        return []
    lines = [ln for ln in REFLECT_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(l) for l in lines[-max(1, min(200, n)):]]


def _load_bundle_manifest(bundle_dir: Path) -> Dict[str, Any]:
    mf = bundle_dir / "bundle.yaml"
    if not mf.exists():
        raise HTTPException(404, f"bundle.yaml not found at {mf}")
    d = yaml.safe_load(mf.read_text(encoding="utf-8"))
    for k in ["bundle_id", "version", "contents"]:
        if k not in d:
            raise HTTPException(400, f"bundle.yaml missing required key: {k}")
    return d

@app.post("/api/domain/load")
async def domain_load(payload: Dict[str, Any]):
    bundle_path = payload.get("bundle_path")
    if not bundle_path:
        raise HTTPException(400, "missing bundle_path")

    bundle_dir = Path(bundle_path).resolve()
    if not bundle_dir.exists():
        raise HTTPException(404, f"bundle_path does not exist: {bundle_dir}")

    manifest = _load_bundle_manifest(bundle_dir)
    bundle_id = manifest["bundle_id"]
    contents = manifest.get("contents", {})

    # Extract role_ids, domain priorities, ritual_ids, atlas_ids
    role_ids = []
    for rel in contents.get("roles", []):
        rd = yaml.safe_load((bundle_dir / rel).read_text(encoding="utf-8"))
        role_ids.append(rd.get("role_id"))

    domains = []
    for rel in contents.get("domains", []):
        dd = yaml.safe_load((bundle_dir / rel).read_text(encoding="utf-8"))
        did = dd.get("domain_id")
        pr = int((dd.get("load_order") or {}).get("priority", 999))
        domains.append({"domain_id": did, "priority": pr})
    domains.sort(key=lambda x: x["priority"])

    ritual_ids = []
    for rel in contents.get("rituals", []):
        rd = yaml.safe_load((bundle_dir / rel).read_text(encoding="utf-8"))
        ritual_ids.append(rd.get("ritual_id"))

    atlas_ids = []
    for rel in contents.get("atlases", []):
        ad = yaml.safe_load((bundle_dir / rel).read_text(encoding="utf-8"))
        atlas_ids.append(ad.get("atlas_id"))

    DOMAIN_REGISTRY[bundle_id] = {
        "bundle_id": bundle_id,
        "version": manifest.get("version"),
        "path": str(bundle_dir),
        "role_ids": role_ids,
        "domains": domains,
        "ritual_ids": ritual_ids,
        "atlas_ids": atlas_ids,
        "contents": contents,
    }

    DOMAIN_CONTEXT["bundle_id"] = bundle_id
    DOMAIN_CONTEXT["bundle_version"] = manifest.get("version")

    _append_reflection({
        "event": "domain.load",
        "bundle_context": _bundle_context(),
        "role_context": ["ROLE:HOME"],
        "domain_context": [d["domain_id"] for d in domains],
    })

    return {"ok": True, "bundle_id": bundle_id, "version": manifest.get("version")}

@app.get("/api/domain/list")
async def domain_list():
    return {"ok": True, "bundles": list(DOMAIN_REGISTRY.values())}

@app.get("/api/domain/map")
async def domain_map():
    out=[]
    for b in DOMAIN_REGISTRY.values():
        out.append({
            "bundle_id": b["bundle_id"],
            "version": b["version"],
            "roles": b.get("role_ids", []),
            "domains": b.get("domains", []),
            "rituals": b.get("ritual_ids", []),
            "atlases": b.get("atlas_ids", []),
        })
    return {"ok": True, "map": out}

@app.post("/replay/run")
async def replay_run(payload: Dict[str, Any]):
    if "input_text" not in payload:
        raise HTTPException(400, "input_text required")
    if "seed" not in payload:
        raise HTTPException(400, "seed required")

    ctx = _resolve_context(payload.get("role_context"))
    role_ctx = ctx["role_context"]

    snap = predecode_freeze(payload, role_ctx)

    event_id = payload.get("event_id") or f"replay_{int(time.time()*1e9)}"
    deterministic_commit = {
        "event_id": event_id,
        "model_ids": snap["model_ids"],
        "model_build_id": snap["model_build_id"],
        "config_hash": snap["config_hash"],
        "param_block_hash": snap["param_block_hash"],
        "seed": snap["seed"],
        "routing_decision": snap["routing_decision"],
        "gating_params": snap["gating_params"],
        "telemetry_sources": snap["telemetry_sources"],
        "tolerance": snap["tolerance"],
        "bundle_context": ctx["bundle_context"],
        "role_context": ctx["role_context"],
        "domain_context": ctx["domain_context"],
        "determinism_profile": snap["determinism_profile"],
    }

    commit_write_once(event_id)
    commit_hash = commit_hash_from_commit(deterministic_commit)

    _append_reflection({
        "event": "replay.finish",
        "commit_hash": commit_hash,
        "bundle_context": ctx["bundle_context"],
        "role_context": ctx["role_context"],
        "domain_context": ctx["domain_context"],
    })

    return {"commit_hash": commit_hash, "deterministic_commit": deterministic_commit}

# Minimal /api/chat/dual stub: logs context only (v0.1)
@app.post("/api/chat/dual")
async def chat_dual(body: Dict[str, Any]):
    ctx = _resolve_context(body.get("role_context"))
    _append_reflection({
        "event": "chat.dual.finish",
        "bundle_context": ctx["bundle_context"],
        "role_context": ctx["role_context"],
        "domain_context": ctx["domain_context"],
        "chars": 0
    })
    return JSONResponse({"ok": True})