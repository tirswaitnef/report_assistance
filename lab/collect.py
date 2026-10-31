#!/usr/bin/env python3
"""Collect read-only observations from the four repository-managed lab services.

Case JSON contains observations and neutral assessment questions. Deployment
conditions and reference candidates are separate artifacts for expert review.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SERVICES = ("pg-a", "pg-b", "mysql-a", "mysql-b")
PG_QUERY = """SELECT json_build_object(
  'server_version', current_setting('server_version'),
  'role', (SELECT json_build_object('rolname', rolname, 'rolsuper', rolsuper,
      'rolcreaterole', rolcreaterole, 'rolcreatedb', rolcreatedb)
      FROM pg_roles WHERE rolname = 'lab_app'),
  'ssl', current_setting('ssl'),
  'hba', (SELECT COALESCE(json_agg(json_build_object('type', type,
      'address', address, 'auth_method', auth_method, 'error', error)
      ORDER BY line_number), '[]'::json)
      FROM pg_hba_file_rules WHERE type <> 'local'),
  'log_connections', current_setting('log_connections'),
  'log_disconnections', current_setting('log_disconnections'),
  'fixture_rows', (SELECT count(*) FROM public.lab_records)
);"""
MYSQL_SETTINGS_QUERY = "SELECT JSON_OBJECT('server_version', VERSION(), 'require_secure_transport', @@GLOBAL.require_secure_transport, 'fixture_rows', (SELECT COUNT(*) FROM labdb.lab_records));"
MYSQL_GRANTS_QUERY = "SHOW GRANTS FOR 'lab_app'@'%';"
MYSQL_SHELL = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot --batch --raw --skip-column-names -e "$1"'


class CollectionError(ValueError):
    """Safe failure detail, without subprocess stderr or environment contents."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_command(command):
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True,
                                encoding="utf-8", errors="strict", timeout=60)
    except (subprocess.SubprocessError, OSError, UnicodeError) as exc:
        raise CollectionError("Docker/SQL command failed; raw output withheld. Check that this lab is healthy.") from exc
    return result.stdout.strip()


def parse_json_observation(text, engine):
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise CollectionError(f"{engine} returned an invalid JSON observation") from exc
    if not isinstance(value, dict) or not isinstance(value.get("server_version"), str):
        raise CollectionError(f"{engine} observation lacks a server version")
    if not isinstance(value.get("fixture_rows"), int) or isinstance(value.get("fixture_rows"), bool) or value["fixture_rows"] < 1:
        raise CollectionError(f"{engine} synthetic fixture table is missing or empty")
    return value


def parse_postgres(text):
    value = parse_json_observation(text, "PostgreSQL")
    role = value.get("role")
    if not isinstance(role, dict) or role.get("rolname") != "lab_app":
        raise CollectionError("PostgreSQL application role was not observed")
    if any(not isinstance(role.get(key), bool) for key in ("rolsuper", "rolcreaterole", "rolcreatedb")):
        raise CollectionError("PostgreSQL role flags have an unexpected format")
    if value.get("ssl") not in {"on", "off"}:
        raise CollectionError("PostgreSQL SSL setting has an unexpected format")
    if any(value.get(key) not in {"on", "off"} for key in ("log_connections", "log_disconnections")):
        raise CollectionError("PostgreSQL connection log settings have an unexpected format")
    hba = value.get("hba")
    if not isinstance(hba, list) or not hba:
        raise CollectionError("PostgreSQL remote authentication rules were not observed")
    for rule in hba:
        if not isinstance(rule, dict) or not isinstance(rule.get("type"), str) or not isinstance(rule.get("auth_method"), str):
            raise CollectionError("PostgreSQL HBA rule has an unexpected format")
        if rule.get("error") is not None:
            raise CollectionError("PostgreSQL reports an HBA parsing error")
    return value


def parse_mysql(settings_text, grants_text):
    value = parse_json_observation(settings_text, "MySQL")
    transport = value.get("require_secure_transport")
    if transport not in (0, 1, False, True, "ON", "OFF", "on", "off"):
        raise CollectionError("MySQL secure transport setting has an unexpected format")
    grants = [line.strip() for line in grants_text.splitlines() if line.strip()]
    if not grants or any(not line.upper().startswith("GRANT ") for line in grants):
        raise CollectionError("MySQL application grants were not observed")
    value["grants"] = grants
    return value


def mysql_has_global_privileges(grants):
    for line in grants:
        match = re.search(r"^GRANT\s+(.+?)\s+ON\s+\*\.\*\s+TO\s", line.replace("`", ""), re.IGNORECASE)
        if match:
            privileges = {part.strip().upper() for part in match.group(1).split(",")}
            if privileges - {"USAGE"}:
                return True
    return False


def observed_flags(engine, observation):
    if engine == "PostgreSQL":
        return {"application_role_superuser": observation["role"]["rolsuper"],
                "server_ssl_enabled": observation["ssl"] == "on",
                "remote_trust_rule_present": any(rule["auth_method"] == "trust" for rule in observation["hba"]),
                "connection_logging_enabled": observation["log_connections"] == "on" and observation["log_disconnections"] == "on"}
    return {"application_global_privileges": mysql_has_global_privileges(observation["grants"]),
            "require_secure_transport": observation["require_secure_transport"] in (1, True, "ON", "on")}


def check_expected_state(service, engine, observation):
    flags = observed_flags(engine, observation)
    control = service.endswith("-b")
    if engine == "PostgreSQL":
        expected = {"application_role_superuser": not control, "server_ssl_enabled": control,
                    "remote_trust_rule_present": not control, "connection_logging_enabled": control}
    else:
        expected = {"application_global_privileges": not control, "require_secure_transport": control}
    return {"service": service, "expected_flags": expected, "observed_flags": flags,
            "passed": flags == expected,
            "meaning": "Operational lab configuration checks only; not expert security ground truth"}


def make_case(case_id, engine, observation, collected_at):
    evidence, findings = [], []
    def add(category, title, severity, source, values, note):
        index = len(evidence) + 1
        eid, fid = f"E-{case_id}-{index:02d}", f"F-{case_id}-{index:02d}"
        evidence.append({"id": eid, "source": source,
                         "content": json.dumps(values, indent=2, ensure_ascii=False), "collected_at": collected_at})
        findings.append({"id": fid, "title": title, "category": category, "severity": severity,
                         "description": "Assess this hypothesis as supported, contradicted, or insufficient using the supplied observation. "
                         "Do not treat the assessment question or input severity as a confirmed vulnerability. " + note,
                         "asset": f"research-db/{case_id}/lab_app", "evidence_ids": [eid]})
    if engine == "PostgreSQL":
        add("excessive_privileges", "Assess application role privileges", "high",
            "Read-only pg_roles projection for lab_app", observation["role"],
            "The lab application only needs to read the synthetic lab_records table; check whether administrative privileges exceed that requirement.")
        add("tls_disabled", "Assess server transport encryption setting", "medium",
            "Read-only current_setting('ssl') projection", {"ssl": observation["ssl"]},
            "This observes server SSL configuration only, not client certificate verification, network exposure, or an eavesdropping result.")
        add("weak_auth", "Assess remote authentication rules", "high",
            "Read-only pg_hba_file_rules remote-rule projection", {"hba": observation["hba"]},
            "Consider rule order and transport type. Local administration uses a container socket and is not evidence of remote exposure.")
        add("audit_logging", "Assess connection event logging", "low",
            "Read-only current_setting connection-log projections",
            {"log_connections": observation["log_connections"], "log_disconnections": observation["log_disconnections"]},
            "These two settings concern connection events only; they do not establish complete audit coverage, retention, integrity, or compliance.")
    else:
        add("excessive_privileges", "Assess application account grants", "high",
            "Read-only SHOW GRANTS FOR lab_app", {"grants": observation["grants"]},
            "The lab application only needs SELECT on labdb.lab_records; compare global/schema grants to this documented requirement.")
        add("tls_disabled", "Assess secure transport enforcement", "medium",
            "Read-only @@GLOBAL.require_secure_transport projection",
            {"require_secure_transport": observation["require_secure_transport"]},
            "This observes the server policy only. The collector uses a local socket; no remote TLS session or certificate validation was measured.")
    return {"title": f"Database configuration assessment {case_id}", "database": engine,
            "findings": findings, "evidence": evidence}


def validate_case(case):
    try:
        from app.models import Case
    except ImportError:
        ids = {e["id"] for e in case["evidence"]}
        if any(not set(f["evidence_ids"]) <= ids for f in case["findings"]):
            raise CollectionError("Generated case has invalid evidence references")
        return "builtin reference validation; install application dependencies for full schema validation"
    Case.model_validate(case)
    return "app.models.Case (Pydantic)"


class Collector:
    def __init__(self, project="dbreport-lab", env_file=None, runner=run_command):
        if project != "dbreport-lab":
            raise CollectionError("Only the repository-managed dbreport-lab project is supported")
        self.runner = runner
        self.compose = ["docker", "compose", "--project-name", project, "--env-file",
                        str(env_file or ROOT / ".local" / "lab.env"), "-f", str(ROOT / "lab" / "compose.yaml")]

    def observe_service(self, service):
        if service not in SERVICES:
            raise CollectionError("Unknown lab service")
        if service.startswith("pg-"):
            raw = self.runner(self.compose + ["exec", "-T", service, "psql", "-X", "-U", "lab_admin", "-d", "labdb", "-At", "-c", PG_QUERY])
            return "PostgreSQL", parse_postgres(raw), {"settings": raw}
        settings = self.runner(self.compose + ["exec", "-T", service, "sh", "-c", MYSQL_SHELL, "sh", MYSQL_SETTINGS_QUERY])
        grants = self.runner(self.compose + ["exec", "-T", service, "sh", "-c", MYSQL_SHELL, "sh", MYSQL_GRANTS_QUERY])
        return "MySQL", parse_mysql(settings, grants), {"settings": settings, "grants": grants}

    def image_identity(self, service):
        container = self.runner(self.compose + ["ps", "-q", service])
        if not re.fullmatch(r"[a-f0-9]{12,64}", container):
            raise CollectionError("A single managed container was not found for a lab service")
        image_id = self.runner(["docker", "inspect", "--format", "{{.Image}}", container])
        image_ref = self.runner(["docker", "inspect", "--format", "{{.Config.Image}}", container])
        if not image_id.startswith("sha256:") or "\n" in image_ref:
            raise CollectionError("Unexpected Docker image identity")
        digests_text = self.runner(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image_id])
        try:
            digests = json.loads(digests_text) or []
        except ValueError as exc:
            raise CollectionError("Invalid Docker image digest metadata") from exc
        return {"image_id": image_id, "image_ref": image_ref, "repo_digests": digests}

    def collect(self, output, seed=491):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        run_id = uuid4().hex
        manifest = {"schema_version": "lab-collection-v1", "run_id": run_id, "status": "collecting",
                    "started_at": utc_now(), "seed": seed, "cases": [],
                    "dataset_type": "Measured observations from intentionally configured local synthetic-data lab",
                    "not_established": ["production vulnerability prevalence", "exploit success", "expert gold labels", "AI effectiveness"],
                    "queries": {"postgres": PG_QUERY, "mysql_settings": MYSQL_SETTINGS_QUERY, "mysql_grants": MYSQL_GRANTS_QUERY},
                    "query_sha256": {"postgres": sha256(PG_QUERY), "mysql_settings": sha256(MYSQL_SETTINGS_QUERY), "mysql_grants": sha256(MYSQL_GRANTS_QUERY)}}
        manifest["lab_source_sha256"] = {
            str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "lab").rglob("*"))
            if path.is_file() and path.suffix in {".py", ".sql", ".sh", ".conf", ".yaml"}}
        write_json(output / "manifest.json", manifest)
        checks, collected = [], []
        try:
            for service in SERVICES:
                engine, observation, raw = self.observe_service(service)
                timestamp = utc_now()
                check = check_expected_state(service, engine, observation)
                checks.append(check)
                image = self.image_identity(service)
                collected.append((service, engine, observation, raw, timestamp, image))
            write_json(output / "health" / "statechecks.json", {"checks": checks, "passed": all(check["passed"] for check in checks)})
            if not all(check["passed"] for check in checks):
                raise CollectionError("Observed lab settings do not match the configured control conditions; no cases exported")
            random.Random(seed).shuffle(collected)
            candidates = {"requires_expert_adjudication": True, "is_final_gold_standard": False,
                          "note": "Configuration-based reference candidates only. Review actual observations, applicability, uncertainty and acceptable controls independently before scoring model output.", "cases": []}
            for index, (service, engine, observation, raw, timestamp, image) in enumerate(collected, 1):
                case_id = f"CASE-{run_id[:8]}-{index:03d}"
                case = make_case(case_id, engine, observation, timestamp)
                validator = validate_case(case)
                path = output / "cases" / f"{case_id}.json"
                write_json(path, case)
                raw_hashes = {}
                for name, text in raw.items():
                    raw_path = output / "raw" / f"{case_id}-{name}.txt"
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_path.write_text(text + "\n", encoding="utf-8")
                    raw_hashes[name] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
                manifest["cases"].append({"case_id": case_id, "engine": engine,
                    "server_version": observation["server_version"], "captured_at": timestamp,
                    "case_file": str(path.relative_to(output)).replace("\\", "/"),
                    "case_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "evidence_sha256": {e["id"]: sha256(e["content"]) for e in case["evidence"]},
                    "raw_observation_sha256": raw_hashes, "schema_validation": validator, **image,
                    "cluster_id": f"DBLAB-v1-{'PG' if engine == 'PostgreSQL' else 'MY'}-CONFIG", "split": "pilot"})
                candidates["cases"].append({"case_id": case_id, "service": service,
                    "lab_condition": "deliberately_weak" if service.endswith("-a") else "hardened_control",
                    "observed_flags": observed_flags(engine, observation),
                    "finding_ids": [finding["id"] for finding in case["findings"]],
                    "evidence_ids": [item["id"] for item in case["evidence"]],
                    "review_required": "Assess each neutral hypothesis; absence of a weak configuration is a negative control, not a confirmed finding. Do not send this reference artifact to the generator."})
            write_json(output / "reference-candidates.json", candidates)
            manifest.update(status="completed", completed_at=utc_now(), case_count=len(manifest["cases"]))
            write_json(output / "manifest.json", manifest)
            return manifest
        except Exception as exc:
            manifest.update(status="failed", completed_at=utc_now(), observed_service_count=len(collected),
                            error=str(exc) if isinstance(exc, CollectionError) else "Collection failed; raw exception withheld")
            # Cases are created only after all observations pass. If validation/export
            # fails later, mark the collection failed and never claim a full dataset.
            write_json(output / "manifest.json", manifest)
            raise CollectionError(manifest["error"]) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New output directory; never overwritten")
    parser.add_argument("--seed", type=int, default=491)
    parser.add_argument("--project", choices=["dbreport-lab"], default="dbreport-lab")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".local" / "lab.env")
    args = parser.parse_args()
    try:
        manifest = Collector(args.project, args.env_file).collect(args.output, args.seed)
    except (CollectionError, FileExistsError) as exc:
        message = str(exc) if isinstance(exc, CollectionError) else "Output directory exists; choose a new path"
        print("Collection failed:", message, file=sys.stderr)
        return 1
    print(f"Collected {manifest['case_count']} cases from live lab observations.")
    print("Import only cases/*.json into the assistant. Reference candidates require independent expert review.")
    print("Lab states are paired variants, not independent research clusters. Preserve the mapping and split them together.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
