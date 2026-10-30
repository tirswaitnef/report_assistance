"""Sequential, resumeless 2x2 collections. Artifacts stay on the local machine."""
import hashlib
import json
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import Field

from app.engine import GenerationError, SYSTEM_PROMPT, generate_report, structural_metrics
from app.models import Case, ReportRequest, StrictModel
from app.privacy import redact_value
from app.research import write_review_form
from app.settings import public_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StudyMetadata(StrictModel):
    case_id: str = Field(default="case-current", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    cluster_id: str = Field(default="cluster-current", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    split: str = Field(default="pilot", pattern=r"^(pilot|development|test)$")
    engine_version: str = Field(default="unknown", min_length=1, max_length=100)


class ExperimentRequest(StrictModel):
    case: Case
    repeats: int = Field(default=3, ge=1, le=5)
    seed: int = Field(default=491, ge=0, le=2**32 - 1)
    provider: str = Field(default="llm", pattern=r"^(llm|template)$")
    study: StudyMetadata = Field(default_factory=StudyMetadata)


class ExperimentBusy(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


class ExperimentManager:
    def __init__(self, directory: Path, kb, semaphore=None, generator=generate_report):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.kb = kb
        self.semaphore = semaphore or threading.BoundedSemaphore(2)
        self.generator = generator
        self.lock = threading.RLock()
        self.active_id = None

    def folder(self, experiment_id):
        if not re.fullmatch(r"[a-f0-9]{32}", experiment_id):
            raise FileNotFoundError("Experiment not found")
        folder = self.directory / experiment_id
        if not (folder / "status.json").exists():
            raise FileNotFoundError("Experiment not found")
        return folder

    def start(self, request: ExperimentRequest, background=True):
        with self.lock:
            if self.active_id is not None:
                raise ExperimentBusy("Một thực nghiệm đang chạy. Chờ hoàn thành trước khi tạo lượt mới.")
            settings = public_settings()
            if request.provider == "llm" and not settings["configured"]:
                raise GenerationError("Chưa cấu hình Gemini. Chạy run.py --configure-gemini trong Terminal trước.")
            experiment_id = uuid4().hex
            folder = self.directory / experiment_id
            folder.mkdir()
            (folder / "reports").mkdir()
            tasks = [(repeat, grounding, rag) for repeat in range(1, request.repeats + 1)
                     for grounding in (False, True) for rag in (False, True)]
            random.Random(request.seed).shuffle(tasks)
            runs = [{"blind_id": f"E{experiment_id[:8]}-B{i+1:04d}", "repeat": repeat,
                     "grounding": grounding, "rag": rag, "condition": f"G{int(grounding)}R{int(rag)}",
                     "status": "pending"} for i, (repeat, grounding, rag) in enumerate(tasks)]
            state = {"id": experiment_id, "status": "queued", "created_at": utc_now(), "total": len(runs),
                     "completed": 0, "succeeded": 0, "failed": 0, "current": None,
                     "runs": runs, "download_ready": False}
            case = redact_value(request.case.model_dump())
            manifest = {"schema_version": "1.0", "experiment_id": experiment_id, "created_at": state["created_at"],
                        "study": request.study.model_dump(), "provider": request.provider,
                        "llm": settings if request.provider == "llm" else None,
                        "repeats": request.repeats, "seed": request.seed, "planned_runs": len(runs),
                        "conditions": {"G": "evidence access and grounding instructions", "R": "OWASP context and source-citation instructions"},
                        "case_sha256": hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest(),
                        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                        "implementation_sha256": {
                            name: hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest()
                            for name in ["app/engine.py", "app/models.py", "app/knowledge.py", "app/settings.py",
                                         "app/experiments.py", "app/research.py", "requirements.lock.txt"]},
                        "retrieval": {"algorithm": "BM25", "top_k": 3, "max_chunk_characters": 1800,
                                      "k1": 1.5, "b": 0.75},
                        "owasp_sources": self.kb.sources,
                        "observed_model_versions": [], "semantic_scores": "not_provided; independent expert review required",
                        "raw_rejected_output": "not_retained; safe failure codes only",
                        "cost": "not_computed; quota/billing depend on Google project and returned usage",
                        "is_fixture": "not_verified; supplied case provenance is the researcher's responsibility"}
            save_json(folder / "case.json", case)
            save_json(folder / "manifest.json", manifest)
            save_json(folder / "status.json", state)
            (folder / "README.txt").write_text(
                "Each report is a model/template output, not a gold reference. expert-review.csv is intentionally blank.\n"
                "Keep failures in denominators. Citation-ID diagnostics are not factual accuracy.\n"
                "Review copies must hide condition/provider labels; this ZIP is not a blinded reviewer package.\n"
                "Raw rejected provider output is not retained. Interrupted pending runs are not attempted.\n"
                "The evidence intervention changes evidence access plus instructions.\n"
                "Do not use synthetic fixtures as a real security benchmark.\n", encoding="utf-8")
            self.active_id = experiment_id
        if background:
            threading.Thread(target=self._run, args=(experiment_id, request), daemon=True).start()
        else:
            self._run(experiment_id, request)
        return self.status(experiment_id)

    def _run(self, experiment_id, request):
        folder = self.directory / experiment_id
        try:
            with self.lock:
                state = json.loads((folder / "status.json").read_text(encoding="utf-8"))
                state["status"] = "running"
                save_json(folder / "status.json", state)
            initial = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["llm"] or public_settings()
            reports = []
            versions = set()
            for run in state["runs"]:
                run["status"] = "running"
                run["started_at"] = utc_now()
                state["current"] = {"condition": run["condition"], "repeat": run["repeat"]}
                with self.lock:
                    save_json(folder / "status.json", state)
                start = time.perf_counter()
                try:
                    now = public_settings()
                    if request.provider == "llm" and (now["backend"], now["model"]) != (initial["backend"], initial["model"]):
                        raise GenerationError("Cấu hình model thay đổi trong thực nghiệm; lượt này không được gọi API.")
                    with self.semaphore:
                        report = self.generator(ReportRequest(case=request.case, grounding=run["grounding"],
                                                             rag=run["rag"], provider=request.provider), self.kb)
                    report["experiment"] = {"id": experiment_id, "blind_id": run["blind_id"],
                                            "repeat": run["repeat"], **request.study.model_dump()}
                    save_json(folder / "reports" / f"{run['blind_id']}.json", report)
                    (folder / "reports" / f"{run['blind_id']}.md").write_text(report["markdown"], encoding="utf-8")
                    generation = report["provenance"].get("generation", {})
                    model_version = generation.get("model_resolved")
                    if model_version:
                        versions.add(model_version)
                    run.update(status="completed", report_id=report["id"], structural=structural_metrics(report),
                               generation=generation)
                    reports.append((run["blind_id"], report))
                    state["succeeded"] += 1
                except Exception as exc:
                    # No raw SDK/HTTP exception text: it may contain credentials or evidence.
                    run.update(status="failed", error_type=type(exc).__name__,
                               error_code=getattr(exc, "code", "generation_failed"),
                               provider_status=getattr(exc, "provider_status", None),
                               error=str(exc) if isinstance(exc, GenerationError) else "Generation failed; raw error withheld")
                    state["failed"] += 1
                run["latency_seconds"] = round(time.perf_counter() - start, 4)
                run["finished_at"] = utc_now()
                state["completed"] += 1
                with self.lock:
                    save_json(folder / "status.json", state)
                    self._write_runs(folder, state)
            write_review_form(folder / "expert-review.csv", reports)
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            manifest["observed_model_versions"] = sorted(versions)
            manifest["model_drift_detected"] = len(versions) > 1
            manifest["completed_at"] = utc_now()
            save_json(folder / "manifest.json", manifest)
            state.update(status="completed_with_errors" if state["failed"] else "completed",
                         current=None, download_ready=True)
        except Exception:
            # Preserve successes and attempt history, even when artifact finalization failed.
            state = json.loads((folder / "status.json").read_text(encoding="utf-8"))
            state.update(status="failed", current=None, download_ready=True,
                         error="Thực nghiệm dừng do lỗi lưu dữ liệu. Xem các lượt đã hoàn thành trong ZIP.")
            for run in state["runs"]:
                if run["status"] in {"pending", "running"}:
                    run["status"] = "not_attempted_or_interrupted"
        finally:
            with self.lock:
                save_json(folder / "status.json", state)
                self._write_runs(folder, state)
                if self.active_id == experiment_id:
                    self.active_id = None

    @staticmethod
    def _write_runs(folder, state):
        (folder / "runs.jsonl").write_text("".join(json.dumps(run, ensure_ascii=False) + "\n" for run in state["runs"]), encoding="utf-8")

    def status(self, experiment_id):
        with self.lock:
            folder = self.folder(experiment_id)
            state = json.loads((folder / "status.json").read_text(encoding="utf-8"))
            if state["status"] in {"queued", "running"} and self.active_id != experiment_id:
                state.update(status="failed", current=None, download_ready=True,
                             error="Server đã khởi động lại; các lượt chưa hoàn thành không được tự chạy lại.")
                for run in state["runs"]:
                    if run["status"] in {"pending", "running"}:
                        run["status"] = "not_attempted_or_interrupted"
                save_json(folder / "status.json", state)
                self._write_runs(folder, state)
            return state

    def archive(self, experiment_id):
        with self.lock:
            state = self.status(experiment_id)
            if not state["download_ready"]:
                raise ExperimentBusy("Thực nghiệm chưa hoàn thành; đợi trước khi tải ZIP.")
            folder = self.folder(experiment_id)
            archive = folder / "export.zip"
            with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
                for path in sorted(folder.rglob("*")):
                    if path.is_file() and path.suffix in {".json", ".jsonl", ".csv", ".md", ".txt"}:
                        output.write(path, Path(experiment_id) / path.relative_to(folder))
            return archive
