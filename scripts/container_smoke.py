#!/usr/bin/env python3
"""Isolated demo container acceptance; never deploy or inspect real credentials.

Build images first with build_images.sh. Only this script's randomly named
Compose project and synthetic named volume are stopped/deleted. An older backend
image may be supplied to rehearse additive-schema application rollback.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-port", type=int, default=18080)
    parser.add_argument("--web-port", type=int, default=13030)
    parser.add_argument("--previous-backend", default="")
    parser.add_argument("--previous-frontend", default="")
    parser.add_argument("--swap-image-archives", action="store_true", help="Low-disk vfs rehearsal: verified private gzip archives, one loaded image generation at a time")
    args = parser.parse_args()
    project = "learningos-release-check-" + uuid.uuid4().hex[:10]
    private = ROOT / ".runtime" / project
    private.mkdir(parents=True, mode=0o700)
    override = private / "override.yml"
    override.write_text(f"""services:
  backend:
    ports: !override ['127.0.0.1:{args.api_port}:8000']
  frontend:
    ports: !override ['127.0.0.1:{args.web_port}:3000']
""")
    command = ["docker", "compose", "-p", project, "-f", str(ROOT / "deploy/compose.demo.yml"), "-f", str(override)]
    image_ids = {name: subprocess.check_output(["docker", "image", "inspect", f"learningos-{name}:demo", "--format", "{{.Id}}"], text=True).strip() for name in ("backend", "frontend")}
    previous_ids = {name: subprocess.check_output(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], text=True).strip() for name, tag in (("backend", args.previous_backend), ("frontend", args.previous_frontend)) if tag}
    if args.swap_image_archives and (not args.previous_backend.startswith('learningos-backend:') or not args.previous_frontend.startswith('learningos-frontend:') or any(previous_ids[name] == image_ids[name] for name in image_ids)):
        raise ValueError('Archive swap requires two distinct owned Learning OS image generations')
    result = {"project": project, "mode": "synthetic offline demo", "publication": "not performed", "image_ids": image_ids, "source_manifest": "docs/evidence/container-source-manifest.json", "checks": []}
    log = (private / "compose.log").open("w")

    def compose(*arguments):
        subprocess.run(command + list(arguments), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

    current_tags = ['learningos-backend:demo', 'learningos-frontend:demo']
    previous_tags = [args.previous_backend, args.previous_frontend]
    current_archive, previous_archive = private / 'current-images.tar.gz', private / 'previous-images.tar.gz'

    def archive(tags, path):
        process = subprocess.Popen(['docker', 'save', *tags], stdout=subprocess.PIPE, stderr=log)
        try:
            with gzip.open(path, 'wb', compresslevel=1) as output:
                shutil.copyfileobj(process.stdout, output, length=1024 * 1024)
        finally:
            process.stdout.close()
        if process.wait():
            raise RuntimeError('Owned image archive export failed')
        digest = hashlib.sha256()
        with path.open('rb') as content:
            for block in iter(lambda: content.read(1024 * 1024), b''):
                digest.update(block)
        return {'path': str(path.relative_to(ROOT)), 'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}

    def loaded(tag):
        return subprocess.run(['docker', 'image', 'inspect', tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

    def unload(tags):
        existing = [tag for tag in tags if tag and loaded(tag)]
        if existing:
            subprocess.run(['docker', 'image', 'rm', *existing], stdout=log, stderr=subprocess.STDOUT, check=True)

    def load(path, expected):
        with gzip.open(path, 'rb') as content:
            process = subprocess.Popen(['docker', 'load'], stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
            try:
                shutil.copyfileobj(content, process.stdin, length=1024 * 1024)
            finally:
                process.stdin.close()
            if process.wait():
                raise RuntimeError('Owned image archive load failed')
        for name, identifier in expected.items():
            actual = subprocess.check_output(['docker', 'image', 'inspect', identifier, '--format', '{{.Id}}'], text=True).strip()
            if actual != identifier:
                raise AssertionError('Reloaded immutable image ID changed')

    def record(label, **detail):
        result["checks"].append({"check": label, "status": "passed", **detail})

    def wait_ready():
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            try:
                health = httpx.get(f"http://127.0.0.1:{args.api_port}/api/v1/ready", timeout=5)
                web = httpx.get(f"http://127.0.0.1:{args.web_port}/api/v1/dashboard", timeout=5)
                if health.status_code == 200 and web.status_code == 200:
                    assert web.json()["learner"]["id"]
                    return health.json()
            except httpx.HTTPError:
                pass
            time.sleep(1)
        raise RuntimeError("Isolated API/worker/frontend readiness deadline exceeded")

    def wait_job(client, job_id):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            response = client.get(f"/api/v1/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            if job["state"] == "succeeded":
                return job
            if job["state"] in {"failed", "needs-attention"}:
                raise AssertionError(f"Synthetic container job failed: {job['error_code']}")
            time.sleep(.2)
        raise RuntimeError("Container job deadline exceeded")

    try:
        if args.swap_image_archives:
            result['image_archives'] = {'previous': archive(previous_tags, previous_archive), 'current': archive(current_tags, current_archive)}
            unload(previous_tags)
        compose("config", "--quiet")
        compose("up", "-d", "--no-build")
        wait_ready()
        record("migrate+seed, API readiness, worker heartbeat and standalone frontend same-origin proxy")
        with httpx.Client(base_url=f"http://127.0.0.1:{args.web_port}", timeout=30) as client:
            home = client.get("/")
            home.raise_for_status()
            assets = sorted({url for url in re.findall(r'(?:src|href)="([^\"]+)"', home.text) if url.startswith('/_next/static/')})
            assert any(url.endswith('.css') for url in assets) and any(url.endswith('.js') for url in assets)
            for asset in assets:
                response = client.get(asset)
                response.raise_for_status()
                assert response.content
            fonts = sorted((ROOT / 'frontend/public/fonts/files').glob('*.woff2'))
            for family in ('noto-sans-arabic', 'noto-sans-sc', 'noto-sans-jp'):
                font = next(path for path in fonts if path.name.startswith(family + '-'))
                assert client.get('/fonts/files/' + font.name).content == font.read_bytes()
            record('standalone HTML, JavaScript/CSS chunks and Arabic/Chinese/Japanese local fonts served intact', static_asset_count=len(assets), font_families=3)
            response = client.post("/api/v1/collections", json={"name": "Synthetic container persistence", "storage_mode": "local"})
            response.raise_for_status()
            cid = response.json()["id"]
            original = b"# Synthetic container original\n\n## Atomic number\nThe atomic number equals the number of protons in an atom's nucleus.\n"
            upload = client.post(f"/api/v1/collections/{cid}/materials", files={"file": ("container-original.md", original, "text/markdown")}, data={"source_language": "en"}, headers={"Idempotency-Key": uuid.uuid4().hex})
            upload.raise_for_status()
            assert upload.json()["source_language"] == "en"
            wait_job(client, upload.json()["job_id"])
            material_id = upload.json()["material_id"]
            correction = client.patch(f"/api/v1/materials/{material_id}/source-language", json={"source_language": "en-US"})
            correction.raise_for_status()
            assert correction.json()["source_language"] == "en-US"
            outline = client.get(f"/api/v1/collections/{cid}/outline").json()
            chunk = outline["materials"][0]["chunks"][0]
            citation = client.get(f"/api/v1/citations/{chunk['citation_ids'][0]}").json()
            assert citation["excerpt"] in original.decode()
            revision = upload.json()["revision_id"]
            assert client.get(f"/api/v1/material-revisions/{revision}/original").content == original
            assert client.get(f"/api/v1/materials/{material_id}").json()["source_language"] == "en-US"
            scope = client.post(f"/api/v1/collections/{cid}/scope", json={"chunk_ids": [chunk["id"]], "expected_version": outline["version"]})
            scope.raise_for_status()
            active = client.get(f"/api/v1/collections/{cid}").json()["active_scope"]
            session = client.post("/api/v1/sessions", json={"collection_id": cid, "scope_revision_id": active["id"], "mode": "study"}, headers={"Idempotency-Key": uuid.uuid4().hex})
            session.raise_for_status()
            sid = session.json()["id"]
            wait_job(client, session.json()["job_id"])
            turn = client.get(f"/api/v1/sessions/{sid}/next").json()
            assert turn["question"] and turn["citation_ids"] and "expected_answer" not in turn
            answer = client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": turn["item_id"], "answer": "Atomic number equals the proton count.", "confidence": 4, "expected_version": turn["version"]}, headers={"Idempotency-Key": uuid.uuid4().hex})
            answer.raise_for_status()
            wait_job(client, answer.json()["job_id"])
            assert client.get(f"/api/v1/collections/{cid}/history").json()["total"] == 1
            record("real multipart original, extraction/citation, frozen scope, cited turn, answer and persisted history", original_sha256=hashlib.sha256(original).hexdigest())
            compose("down")
            compose("up", "-d", "--no-build")
            wait_ready()
            assert client.get(f"/api/v1/material-revisions/{revision}/original").content == original
            assert client.get(f"/api/v1/collections/{cid}/history").json()["total"] == 1
            assert client.get(f"/api/v1/sessions/{sid}").status_code == 200
            record("down/up named-volume persistence preserves private original, selected scope, session and one history event")
            if args.previous_backend:
                previous_id = previous_ids['backend']
                rollback = private / "previous-backend.yml"
                previous_frontend_id = previous_ids.get('frontend')
                rollback.write_text(f"services:\n  backend:\n    image: {previous_id}\n  worker:\n    image: {previous_id}\n" + (f"  frontend:\n    image: {previous_frontend_id}\n" if previous_frontend_id else ""))
                services = ["backend", "worker"] + (["frontend"] if previous_frontend_id else [])
                # This is a deliberately cold isolated rehearsal: remove this
                # project's current containers first, preserving its named data
                # volume, instead of retaining two large image snapshots while
                # Compose concurrently creates replacement containers.
                compose("rm", "--stop", "--force", *services, "migrate")
                if args.swap_image_archives:
                    unload(current_tags)
                    load(previous_archive, previous_ids)
                rollback_cmd = command + ["-f", str(rollback), "up", "-d", "--no-build", "--no-deps"] + services
                subprocess.run(rollback_cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
                wait_ready()
                assert client.get(f"/api/v1/collections/{cid}/history").json()["total"] == 1
                assert client.get(f"/api/v1/material-revisions/{revision}/original").content == original
                assert client.get(f"/api/v1/sessions/{sid}/next").status_code == 200
                record("previous image rollback reads current additive schema, original, session and history without DB downgrade", backend_image_id=previous_id, frontend_image_id=previous_frontend_id, frontend="previous standalone image" if previous_frontend_id else "current standalone image; an older frontend image was unavailable")
                compose("rm", "--stop", "--force", *services)
                if args.swap_image_archives:
                    unload(previous_tags)
                    load(current_archive, image_ids)
                compose("up", "-d", "--no-build", "--no-deps", *services)
                wait_ready()
                assert client.get(f"/api/v1/materials/{material_id}").json()["source_language"] == "en-US"
                record("forward return to current backend+worker images")
        result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["error_class"] = type(exc).__name__
        raise
    finally:
        try:
            compose("down", "--volumes", "--remove-orphans")
            result["cleanup"] = "isolated project and synthetic named volume removed"
            if args.swap_image_archives:
                unload(previous_tags)
                if not all(loaded(tag) for tag in current_tags):
                    load(current_archive, image_ids)
                result['archive_swap'] = 'both generations archived with SHA256; reloaded immutable image IDs verified; current tags restored; previous archives retained privately; no real data modified'
        finally:
            log.close()
            (ROOT / "docs/evidence/container-flow.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "checks": len(result["checks"]), "evidence": "docs/evidence/container-flow.json"}))


if __name__ == "__main__":
    main()
