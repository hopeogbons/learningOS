"""Isolated PostgreSQL/loopback metadata benchmark; never calls live providers.

Run with backend/.venv/bin/python tests/performance_probe.py. TEST_POSTGRES_URL
must identify a disposable integration database with schema-creation privileges.
The probe migrates and deletes only its own random schema. Fixture sessions test
the real opaque-session authentication boundary, not an actual OIDC sign-in.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def percentile(values, fraction):
    ordered = sorted(values)
    return round(ordered[max(0, min(len(ordered) - 1, int(len(ordered) * fraction)))], 2) if ordered else None


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def hardware_limits():
    """Record actual container capacity as well as host-visible CPU count."""
    limits = {}
    for name in ("cpu.max", "memory.max", "cpuset.cpus.effective"):
        try:
            limits[name] = (Path("/sys/fs/cgroup") / name).read_text().strip()
        except OSError:
            limits[name] = "unavailable"
    quota = limits["cpu.max"].split()
    if len(quota) == 2 and quota[0] != "max":
        limits["cpu_quota_cores"] = round(int(quota[0]) / int(quota[1]), 3)
    if limits["memory.max"].isdigit():
        limits["memory_limit_bytes"] = int(limits["memory.max"])
    return limits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--clients", type=int, default=50)
    parser.add_argument("--think-ms", type=int, default=100)
    parser.add_argument("--api-workers", type=int, default=2)
    parser.add_argument("--output", default=str(ROOT / "docs/evidence/performance-postgres.json"))
    args = parser.parse_args()
    if args.seconds < 1 or not 1 <= args.clients <= 50 or args.think_ms < 0 or not 1 <= args.api_workers <= 16:
        parser.error("Positive duration, 1..50 clients, 1..16 API workers and nonnegative think time required")
    base = os.environ.get("TEST_POSTGRES_URL")
    if not base or not base.startswith("postgresql"):
        parser.error("TEST_POSTGRES_URL must be a disposable PostgreSQL integration database")
    schema = "performance_probe_" + uuid4().hex
    url = base + ("&" if "?" in base else "?") + urlencode({"options": "-csearch_path=" + schema})
    admin = create_engine(base)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    report = {"schema_version": 1, "database": "PostgreSQL isolated random schema",
              "network": "loopback HTTP; local DB, no WAN/TLS edge", "provider": "no live AI, Drive or speech",
              "authentication": "real opaque DB sessions, synthetic preauthenticated learners; no OIDC exchange",
              "dataset": {"learners": 50, "collections": 50, "materials": 250, "titles": 5000, "concepts": 50000},
              "api_workers": args.api_workers, "clients": args.clients, "duration_requested_seconds": args.seconds,
              "think_time_ms_per_user": args.think_ms, "source_jobs_initial": 20,
              "source_job_note": "20 actual text-ingestion jobs with two offline workers; initial concurrent queue, not maintained for five minutes",
              "hardware": {"cpu_count_visible": os.cpu_count(), "platform": platform.platform(),
                           "python": platform.python_version(), "cgroup": hardware_limits()}, "thresholds": {"p95_ms": 500, "error_rate": 0.01}}
    report["source_sha256_at_start"] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                         for path in sorted((BACKEND / "app").rglob("*.py"))}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    report["git_head_at_start"] = commit.stdout.strip() if commit.returncode == 0 else "unavailable"
    report["working_tree_note"] = "Source hashes identify the reviewed working-tree implementation; HEAD alone may predate uncommitted files."
    report["dataset"]["initial_titles_per_collection"] = 100
    report["hardware"]["shared_host_note"] = "Other development checks may share this cloud host; not a dedicated production benchmark host."
    processes = []
    engine = None
    try:
        with tempfile.TemporaryDirectory(prefix="learningos-performance-") as temporary:
            environment = {**os.environ, "DATABASE_URL": url, "APP_MODE": "live",
                           "PRIVATE_STORAGE_DIR": str(Path(temporary) / "private"),
                           "SESSION_SIGNING_KEY": secrets.token_urlsafe(48)}
            # Settings are imported only after binding our owned isolated schema.
            os.environ.update({key: environment[key] for key in ("DATABASE_URL", "APP_MODE", "PRIVATE_STORAGE_DIR", "SESSION_SIGNING_KEY")})
            migration = subprocess.run([str(BACKEND / ".venv/bin/alembic"), "upgrade", "head"],
                                       cwd=BACKEND, env=environment, capture_output=True, text=True)
            if migration.returncode:
                raise RuntimeError("isolated migration failed; no connection string printed")
            from app.db import utcnow
            from app.models import (Learner, AuthSession, Collection, Material, MaterialRevision, Chunk,
                                    Concept, Citation, ScopeRevision, ScopeItem, Job)
            from app.storage import LocalStorage
            engine = create_engine(url, pool_size=5, max_overflow=5)
            factory = sessionmaker(engine, expire_on_commit=False)
            owners = []
            seed_started = time.monotonic()
            with engine.begin() as db:
                for learner_index in range(50):
                    learner_id, collection_id, scope_id = str(uuid4()), str(uuid4()), str(uuid4())
                    opaque = secrets.token_urlsafe(48)
                    owners.append({"id": learner_id, "collection_id": collection_id, "cookie": opaque})
                    db.execute(insert(Learner), [{"id": learner_id, "display_name": f"Synthetic {learner_index}", "is_demo": False}])
                    db.execute(insert(AuthSession), [{"learner_id": learner_id, "token_hash": hashlib.sha256(opaque.encode()).hexdigest(),
                                                      "csrf_hash": hashlib.sha256(b"synthetic-csrf").hexdigest(),
                                                      "expires_at": utcnow() + timedelta(hours=1)}])
                    db.execute(insert(Collection), [{"id": collection_id, "learner_id": learner_id, "name": f"Synthetic collection {learner_index}"}])
                    db.execute(insert(ScopeRevision), [{"id": scope_id, "learner_id": learner_id, "collection_id": collection_id, "revision_number": 1}])
                    for material_index in range(5):
                        material_id, revision_id = str(uuid4()), str(uuid4())
                        db.execute(insert(Material), [{"id": material_id, "learner_id": learner_id, "collection_id": collection_id,
                                                       "title": f"Synthetic material {material_index}", "position": material_index, "status": "ready"}])
                        db.execute(insert(MaterialRevision), [{"id": revision_id, "learner_id": learner_id, "collection_id": collection_id,
                                                              "material_id": material_id, "content_hash": hashlib.sha256(str(material_index).encode()).hexdigest(),
                                                              "extracted_text": "Synthetic benchmark source."}])
                        db.execute(Material.__table__.update().where(Material.id == material_id).values(current_revision_id=revision_id))
                        chunks, concepts, citations, scope_items = [], [], [], []
                        for chunk_index in range(20):
                            chunk_id, citation_id = str(uuid4()), str(uuid4())
                            position = material_index * 20 + chunk_index
                            chunks.append({"id": chunk_id, "learner_id": learner_id, "material_revision_id": revision_id,
                                           "title": f"Synthetic title {position}", "text": "Synthetic benchmark source.", "position": chunk_index})
                            citations.append({"id": citation_id, "learner_id": learner_id, "revision_id": revision_id,
                                              "locator_kind": "text", "locator_json": {"line_start": position + 1},
                                              "excerpt": "Synthetic benchmark source.", "excerpt_hash": hashlib.sha256(b"Synthetic benchmark source.").hexdigest()})
                            scope_items.append({"learner_id": learner_id, "scope_revision_id": scope_id, "chunk_id": chunk_id, "position": position})
                            for concept_index in range(10):
                                concepts.append({"learner_id": learner_id, "chunk_id": chunk_id,
                                                 "text": f"Synthetic concept {concept_index}.", "citation_ids": [citation_id], "position": concept_index})
                        db.execute(insert(Chunk), chunks)
                        db.execute(insert(Citation), citations)
                        db.execute(insert(Concept), concepts)
                        db.execute(insert(ScopeItem), scope_items)
            report["seed_seconds"] = round(time.monotonic() - seed_started, 2)
            with engine.connect() as db:
                report["seed_verified"] = {"titles": db.scalar(select(func.count()).select_from(Chunk)),
                                           "concepts": db.scalar(select(func.count()).select_from(Concept))}
            report["direct_query_profile"] = profile_queries(engine, factory, owners[0])
            with socket.socket() as port_socket:
                port_socket.bind(("127.0.0.1", 0))
                port = port_socket.getsockname()[1]
            log_path = Path(temporary) / "api.log"
            with log_path.open("w") as log:
                api = subprocess.Popen([str(BACKEND / ".venv/bin/python"), "-m", "uvicorn", "app.main:app",
                                        "--host", "127.0.0.1", "--port", str(port), "--workers", str(args.api_workers), "--no-access-log"],
                                       cwd=BACKEND, env=environment, stdout=log, stderr=log)
                processes.append(api)
                origin = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    try:
                        if httpx.get(origin + "/api/v1/health", timeout=1).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if api.poll() is not None:
                        raise RuntimeError("isolated API startup failed")
                    time.sleep(.2)
                else:
                    raise RuntimeError("isolated API readiness timeout")
                # Auth/tenant assertions exercise the actual API before timing begins.
                for index, owner in enumerate(owners):
                    response = httpx.get(origin + "/api/v1/collections", cookies={"learningos_session": owner["cookie"]})
                    response.raise_for_status()
                    assert [item["id"] for item in response.json()["items"]] == [owner["collection_id"]]
                report["fixture_auth_tenant_checks"] = 50
                assert httpx.get(origin + "/api/v1/me").status_code == 401
                foreign = httpx.get(origin + f"/api/v1/collections/{owners[1]['collection_id']}",
                                    cookies={"learningos_session": owners[0]["cookie"]})
                assert foreign.status_code == 404
                # Warm the exact measured read paths before starting source work.
                asyncio.run(run_clients(origin, owners[:args.clients], 5, args.think_ms))
                report["warmup_seconds"] = 5
                store = LocalStorage(environment["PRIVATE_STORAGE_DIR"])
                with factory() as db:
                    for index, owner in enumerate(owners[:20]):
                        source = f"# Source work {index}\nThis is synthetic benchmark ingestion content.".encode()
                        material = Material(learner_id=owner["id"], collection_id=owner["collection_id"], title=f"Ingest work {index}", position=5)
                        db.add(material); db.flush()
                        revision = MaterialRevision(learner_id=owner["id"], collection_id=owner["collection_id"], material_id=material.id,
                                                    content_hash=hashlib.sha256(source).hexdigest(), size=len(source),
                                                    private_blob_key=store.put(owner["id"], source), metadata_json={"filename": "source.md"})
                        db.add(revision); db.flush()
                        db.add(Job(learner_id=owner["id"], kind="ingest-material", payload={"revision_id": revision.id}))
                    db.commit()
                worker_program = "from app.worker import load_handlers;from app.jobs import run_once;load_handlers();\nwhile run_once():pass"
                jobs_started = time.monotonic()
                worker_logs = []
                for index in range(2):
                    worker_log = (Path(temporary) / f"worker-{index}.log").open("w")
                    worker_logs.append(worker_log)
                    processes.append(subprocess.Popen([str(BACKEND / ".venv/bin/python"), "-c", worker_program], cwd=BACKEND,
                                                       env={**environment, "APP_MODE": "demo"}, stdout=worker_log, stderr=worker_log))
                print("Running isolated PostgreSQL metadata probe: 50 fixture learners, 5,000 titles, 50,000 concepts.", flush=True)
                report.update(asyncio.run(run_clients(origin, owners[:args.clients], args.seconds, args.think_ms)))
                for worker in processes[1:]:
                    worker.wait(timeout=20)
                for worker_log in worker_logs:
                    worker_log.close()
                with factory() as db:
                    jobs = list(db.scalars(select(Job)))
                    report["source_jobs"] = {"total": len(jobs), "succeeded": sum(j.state == "succeeded" for j in jobs),
                                             "failed_or_attention": sum(j.state in {"failed", "needs-attention"} for j in jobs),
                                             "all_attempts_once": all(j.attempts == 1 for j in jobs),
                                             "completion_observed_within_seconds": round(time.monotonic() - jobs_started, 2)}
                expected_endpoints = {"dashboard", "collections", "outline", "progress", "review/due", "search"}
                report["endpoint_targets"] = {
                    name: {"p95_passed": values["p95_ms"] is not None and values["p95_ms"] < 500,
                           "error_rate_passed": values["error_rate"] < .01}
                    for name, values in report["endpoints"].items()
                }
                report["all_endpoint_targets_passed"] = (
                    set(report["endpoints"]) == expected_endpoints
                    and all(all(checks.values()) for checks in report["endpoint_targets"].values())
                )
                report["targets_passed"] = (report["overall"]["p95_ms"] is not None
                    and report["overall"]["p95_ms"] < 500 and report["overall"]["error_rate"] < .01
                    and report["all_endpoint_targets_passed"])
                report["full_five_minute_target_run"] = args.seconds >= 300 and args.clients == 50
    except Exception as exc:
        report["probe_failure"] = type(exc).__name__ + ": " + str(exc) if isinstance(exc, (AssertionError, RuntimeError)) else type(exc).__name__
    finally:
        for process in reversed(processes):
            stop(process)
        if engine:
            engine.dispose()
        # Schema identifier is generated here, never accepted from a caller.
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
        report["cleanup"] = "Only owned random probe schema and temporary private files removed"
        report["source_files_changed_during_run"] = [path for path, digest in report["source_sha256_at_start"].items()
                                                     if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest]
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"evidence": str(output.relative_to(ROOT)), "overall": report.get("overall"),
                          "targets_passed": report.get("targets_passed"), "probe_failure": report.get("probe_failure")}), flush=True)
    return 0 if report.get("targets_passed") and report.get("source_jobs", {}).get("succeeded") == 20 else 1


def profile_queries(engine, factory, owner):
    """One-user function calls expose SQL count; this is not HTTP latency."""
    from sqlalchemy import event
    from app import core_api
    from app.models import Learner
    counter = {"sql_count": 0, "sql_ms": 0.0}
    def before(connection, cursor, statement, params, context, many):
        context._benchmark_started = time.perf_counter()
    def after(connection, cursor, statement, params, context, many):
        counter["sql_count"] += 1
        counter["sql_ms"] += (time.perf_counter() - context._benchmark_started) * 1000
    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    results = {}
    try:
        with factory() as db:
            learner = db.get(Learner, owner["id"])
            calls = {"dashboard": lambda: core_api.dashboard(learner=learner, db=db),
                     "collections": lambda: core_api.collections(cursor=0, limit=50, learner=learner, db=db),
                     "outline": lambda: core_api.outline(owner["collection_id"], learner=learner, db=db),
                     "progress": lambda: core_api.collection_progress(owner["collection_id"], learner=learner, db=db),
                     "search": lambda: core_api.search(q="Synthetic", collection_id=None, cursor=0, limit=50, learner=learner, db=db)}
            for name, call in calls.items():
                counter.update(sql_count=0, sql_ms=0.0)
                started = time.perf_counter()
                output = call()
                serialized = json.dumps(output.model_dump() if hasattr(output, "model_dump") else output, default=str)
                results[name] = {"sql_count": counter["sql_count"], "sql_ms": round(counter["sql_ms"], 2),
                                 "direct_function_ms": round((time.perf_counter() - started) * 1000, 2),
                                 "serialized_payload_bytes": len(serialized.encode())}
    finally:
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)
    return {"note": "Single-user direct function profile excludes authentication, ASGI/thread serialization and pool acquisition", "endpoints": results}


async def run_clients(origin, owners, seconds, think_ms):
    samples, errors = {}, {}
    in_flight, maximum = 0, 0
    # Construct TLS-capable clients before the measured interval; construction is
    # synchronous and otherwise delays already-issued requests on the event loop.
    clients = [httpx.AsyncClient(base_url=origin + "/api/v1", cookies={"learningos_session": owner["cookie"]}, timeout=20) for owner in owners]
    started = time.monotonic()
    deadline = started + seconds
    async def user(owner, client):
        nonlocal in_flight, maximum
        paths = ["/dashboard", "/collections", f"/collections/{owner['collection_id']}/outline",
                 f"/collections/{owner['collection_id']}/progress", "/review/due", "/search?q=Synthetic"]
        async with client:
            index = 0
            while time.monotonic() < deadline:
                path = paths[index % len(paths)]
                category = "outline" if path.endswith("/outline") else "progress" if path.endswith("/progress") else path.split("?")[0].strip("/")
                then = time.monotonic()
                in_flight += 1
                maximum = max(maximum, in_flight)
                error = False
                try:
                    response = await client.get(path)
                    error = response.status_code != 200
                    if not error:
                        response.json()  # Include client-side JSON decode in metadata latency.
                except (httpx.HTTPError, ValueError):
                    error = True
                finally:
                    in_flight -= 1
                samples.setdefault(category, []).append((time.monotonic() - then) * 1000)
                errors[category] = errors.get(category, 0) + int(error)
                index += 1
                await asyncio.sleep(think_ms / 1000)
    await asyncio.gather(*(user(owner, client) for owner, client in zip(owners, clients)))
    elapsed = time.monotonic() - started
    all_values = [value for values in samples.values() for value in values]
    total_errors = sum(errors.values())
    return {"elapsed_seconds": round(elapsed, 2), "maximum_in_flight_requests": maximum,
            "overall": {"requests": len(all_values), "errors": total_errors,
                        "error_rate": round(total_errors / len(all_values), 6), "p50_ms": percentile(all_values, .5),
                        "p95_ms": percentile(all_values, .95), "p99_ms": percentile(all_values, .99),
                        "requests_per_second": round(len(all_values) / elapsed, 2)},
            "endpoints": {name: {"requests": len(values), "errors": errors.get(name, 0),
                                 "error_rate": round(errors.get(name, 0) / len(values), 6),
                                 "p50_ms": percentile(values, .5), "p95_ms": percentile(values, .95),
                                 "p99_ms": percentile(values, .99)} for name, values in samples.items()}}


if __name__ == "__main__":
    raise SystemExit(main())
