import json
import os
import sqlite3
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from app.engine import GenerationError, generate_report, llm_configured, structural_metrics
from app.knowledge import KnowledgeBase, ROOT
from app.models import Case, ReportRequest, StrictModel
from app.settings import public_settings
from app.experiments import ExperimentManager, ExperimentRequest, ExperimentBusy

app = FastAPI(title="DB Security Report Assistant", version="0.1.0")
kb = KnowledgeBase()
DATA_DIR = Path(os.getenv("DB_REPORT_DATA_DIR", str(ROOT / ".local")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "reports.sqlite3"
with sqlite3.connect(DB_PATH) as connection:
    connection.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

# Avoid unbounded concurrent paid generations in this local research prototype.
generation_lock = threading.BoundedSemaphore(2)
experiments = ExperimentManager(DATA_DIR / "experiments", kb, generation_lock)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Reject oversized bodies even if a client omits Content-Length.
    if request.method in {"POST", "PUT", "PATCH"}:
        total = 0
        body = []
        async for chunk in request.stream():
            total += len(chunk)
            if total > 1_000_000:
                return JSONResponse(status_code=413, content={"detail": "Request exceeds 1 MB"})
            body.append(chunk)
        request._body = b"".join(body)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    response.headers["Cache-Control"] = "no-store"
    return response


def load_cases() -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "data" / "cases").glob("*.json"))}


def read_report(report_id: str) -> dict:
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute("SELECT payload FROM reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    return json.loads(row[0])


@app.get("/api/health")
def health():
    settings = public_settings()
    return {"status": "ok", "provider": "template", "llm_configured": llm_configured(),
            "llm_backend": settings["backend"], "llm_model": settings["model"],
            "credential_source": settings["credential_source"],
            "case_count": len(load_cases()), "corpus_chunks": len(kb.chunks),
            "semantic_validation": False}


@app.get("/api/cases")
def cases():
    return [{"id": key, "title": value["title"], "description": f"Synthetic fixture · {value['database']} · not a research dataset",
             "finding_count": len(value["findings"])} for key, value in load_cases().items()]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    value = load_cases().get(case_id)
    if value is None:
        raise HTTPException(404, "Case not found")
    return Case.model_validate(value).model_dump()


@app.get("/api/knowledge")
def knowledge():
    return {"sources": kb.sources, "chunks": len(kb.chunks), "retrieval": "BM25; lexical, offline",
            "license": "CC-BY-SA-4.0", "attribution": "OWASP Cheat Sheet Series contributors"}


@app.post("/api/reports", status_code=201)
def create_report(request: ReportRequest):
    if request.provider == "llm" and not llm_configured():
        raise HTTPException(503, "Gemini chưa được cấu hình. Chạy run.py --configure-gemini hoặc đặt GEMINI_API_KEY và GEMINI_MODEL ở server.")
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(429, "Two generations are already running; retry after they complete")
    try:
        report = generate_report(request, kb)
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute("INSERT INTO reports (id,payload) VALUES (?,?)",
                               (report["id"], json.dumps(report, ensure_ascii=False)))
        return report
    except GenerationError as exc:
        raise HTTPException(502, str(exc)) from exc
    finally:
        generation_lock.release()


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    return read_report(report_id)


@app.get("/api/reports/{report_id}/markdown")
def get_markdown(report_id: str):
    report = read_report(report_id)
    return Response(report["markdown"], media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="report-{report["id"]}.md"'})


class EvaluationRequest(StrictModel):
    report_id: str = Field(min_length=1, max_length=80)


@app.post("/api/evaluate")
def evaluate(request: EvaluationRequest):
    return structural_metrics(read_report(request.report_id))


@app.post("/api/experiments", status_code=202)
def start_experiment(request: ExperimentRequest):
    try:
        return experiments.start(request)
    except ExperimentBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/experiments/{experiment_id}")
def experiment_status(experiment_id: str):
    try:
        return experiments.status(experiment_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Experiment not found") from exc


@app.get("/api/experiments/{experiment_id}/download")
def experiment_download(experiment_id: str):
    try:
        path = experiments.archive(experiment_id)
        return FileResponse(path, media_type="application/zip", filename=f"experiment-{experiment_id}.zip")
    except FileNotFoundError as exc:
        raise HTTPException(404, "Experiment not found") from exc
    except ExperimentBusy as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "app" / "static", check_dir=False), name="static")
