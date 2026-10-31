# Implementation validation

These are **software checks**, not empirical answers to the three research questions.

## Typed Gemini output format (0.2.2)

- The user reported HTTP200 for both `text_minimal` and `typed_report_schema` against `gemini-3.1-flash-lite`, while the older application continued returning HTTP400. These are user-run parameter-acceptance observations, not a live end-to-end report run from this workspace.
- The application now defaults to the same inline native `responseSchema` structure as the accepted typed probe. `GEMINI_SCHEMA_MODE=json_schema` is an explicit alternative; there is no automatic retry, provider/model substitution or format fallback. Full local Pydantic and citation validation remain unchanged.
- **143 tests passed** after integration, including equality between the production schema and successful probe shape, format-selection isolation, response validation and refusal to mix schema modes within an experiment. Wire format/profile, request hash and app version are recorded for reproducibility.
- The `/api/health` response reports `app_version=0.2.2` and `llm_schema_mode`. Failed generation messages also identify the schema profile/version, allowing stale running processes to be distinguished from an updated application. Complete report generation with the user's account still requires a fresh application request after updating.

## Database research lab

- Windows native-CLI fix: user diagnostics showed PowerShell Docker succeeds but Python's `shutil.which('docker')` selects an extensionless Docker Desktop file. Startup and collection now resolve `docker.exe` explicitly on Windows, preserve argument-array invocation and do not fall back to the extensionless file. Safe OS codes replace the generic process-launch error. **132 tests passed**, including Windows-resolution regression mocks; this workspace does not provide a native Windows runtime.

- **129 tests passed** in the full suite after adding 24 lab lifecycle/collector tests. Docker and SQL unit-test calls are mocked; the live checks below are additional runtime evidence.
- Pulled official PostgreSQL/MySQL images with registry TLS and checksum verification, then pinned the tested manifest digests in `lab/compose.yaml`. Actual observed versions were PostgreSQL **16.15** and MySQL **8.4.13** in this instance.
- Started all four containers with the documented `lab.py up`; all reached healthy. Confirmed no host port bindings. The Compose network is internal and containers have no privileged/host-network/socket mounts.
- Collected four live cases (12 assessment hypotheses) from the configured weak/control databases. All operational state checks passed, Pydantic accepted every case, and raw-file/case/source hashes were verified. Fixed scenario cluster IDs are retained across captures.
- Functional local reads confirmed: PostgreSQL A permits app access without a password; B refuses passwordless access and accepts a read with certificate-verified lab TLS. MySQL A permits a plaintext read; B rejects plaintext with ERROR3159 and accepts an encrypted read. MySQL plaintext authentication probes used its supported RSA public-key exchange (`--get-server-public-key`) for caching_sha2 authentication; no credentials were logged. These are narrow lab behavior checks, not exploit or production-safety claims.
- All four collected cases imported through the actual report API and generated template reports (HTTP201), without Gemini calls. Stopping and restarting the lab retained volumes, all four services became healthy again, and collection succeeded again. Only this lab's containers were stopped after validation; evidence and volumes were retained locally.
- The three fixture rows per database are synthetic. Configuration evidence is actually observed at collection time; `reference-candidates.json` is a provisional lab reference, not independently adjudicated gold. Four cases from two scenario families are a pilot, not the planned research dataset. Collected outputs and local database credentials are excluded from GitHub source delivery.
- User-facing reproduction and research guidance: `docs/LAB_RESEARCH_GUIDE.vi.md`. Docker Desktop/WSL2 on the user's Windows machine has not been tested from this workspace. The user's Gemini HTTP400 remains under separate diagnosis; collecting lab evidence does not require a model or API key.

## HTTP 400 compatibility update (0.2.1)

- Added `scripts/probe_gemini.py` for isolated synthetic native requests: plain text, temperature, output budget, JSON MIME, minimal/full/inline schemas, system instruction and the combined application request. It makes no production fallback and does not mutate report settings. It stops on baseline/access/quota errors and can select a single probe. Candidate contents and credentials are not printed or saved. Live account-specific diagnosis still requires the user to run it with their own key.

- **97 tests passed** after this update (mocked Gemini; no live key).

- Google documents a subset for `responseJsonSchema`; the wire schema now omits unsupported `minLength`, `maxLength` and `default` hints while preserving the full Pydantic schema for local validation. Structured JSON output and citation guards remain enabled. Source: [official SDK schema field documentation](https://github.com/googleapis/python-genai/blob/main/google/genai/types.py).
- Provider errors are classified using known reason codes and canonical field roots; no raw provider error text, unknown field name or evidence is echoed. A generic HTTP400 alone does not establish its cause; this compatibility change does not prove the user's account-specific error was caused by schema constraints.
- `py -3.12 run.py --diagnose-gemini` checks the configured model's metadata and submits one synthetic structured request. It can consume API quota, never submits imported findings/evidence, and reports only safe diagnostic information.
- The wire schema profile and revised code hashes are recorded for reproducibility. Do not merge pre/post-update research batches without declaring the configuration change. No live API credential was available for verification in this workspace.

## Gemini update

- Native Google Gemini REST generation implemented using structured JSON output, server-side key configuration and the fixed Google API endpoint. `run.py --configure-gemini` prompts for a hidden key and model, saves them locally, then starts the web application. The local settings file is excluded from downloadable source archives.
- **79 tests passed** after integration, including native Gemini request/response mocks, provider blocks/quota/timeouts, model/token provenance, experiment failure accounting and ZIP exports, launcher credential privacy, plus the prior reporting tests. Real Gemini API calls have **not** been made: no key is configured in this workspace. Mocks establish software behavior, not service access or model quality.
- Real Chromium integration against the updated application verified missing-key guidance, template report generation, four-condition experiment progress, refresh recovery by experiment ID, and a valid downloadable ZIP. Gemini-configured UI states were checked with mocked responses. No dummy key was sent to Google.
- Real web API smoke: 12/12 template runs on one synthetic case (3 repetitions × 4 conditions); archive contains case/manifest/status/runs, report JSON+Markdown and blank expert coding CSV. Verified study IDs and metadata are exported. Source and prompt hashes, OWASP provenance and retrieval parameters are captured. No semantic research scores were generated.
- The requested model alias defaults to `gemini-flash-latest`, based on the official Google SDK documentation examples. Availability depends on the user's Google project; a fixed supported model ID is recommended for a research batch. Successful generations retain requested and provider-resolved model versions and token counts when returned.

The baseline section below records the earlier prototype validation. Its 44-test count predates this update. Current installation and research instructions are in `HUONG_DAN_SU_DUNG.md` and `docs/GEMINI_RESEARCH_GUIDE.vi.md`.

## Verified in this workspace

- Python 3.12 virtual environment created; dependencies installed with TLS verification from the package registry. `requirements.lock.txt` captures the tested full dependency set; `requirements.txt` records direct dependencies.
- **44 unittest tests passed** in the isolated virtual environment: 13 API tests, 13 input/privacy/retrieval tests, 18 engine/provider tests. Provider tests use mocks, not a paid model.
- Local Uvicorn service started and exercised through Chromium. All four grounding/RAG configurations returned HTTP 201, produced reports with the requested flags, and rendered successfully. Structural evaluation, evidence inspection, JSON editing/import, OWASP/research views and Markdown/JSON download were exercised.
- Browser checked safe text rendering for an HTML-shaped input, invalid-JSON feedback, no JS runtime errors, and no horizontal overflow at widths 390, 680, 900, 1180 and 1440. This is a smoke check, not a formal accessibility audit or penetration test.
- Offline experiment smoke: **12/12 runs completed**, using three synthetic fixtures × four conditions, one repetition. Findings with no evidence remained review-required; G0 excluded evidence context, R0 excluded OWASP context. Human annotation scores were not filled in.
- Four official OWASP documents at commit `920293be317721982fa50324a6f26af3f29dc45e`, **137 chunks**, with SHA-256 verification and license preserved. Relevance was sanity-checked for SQLi, least privilege and TLS; there is no gold-labeled retrieval benchmark yet.
- Research proposal Word document generated and reopened; 243-word abstract. Rendered with LibreOffice successfully as 19 A4 pages. Title-page personal metadata remains blank for the team to complete.

## Environment-specific execution

The default execution sandbox denied network sockets (including loopback binds and the TestClient event-loop socket). Network-dependent package installation, local service startup, browser checks and the unittest run used approved elevated tool execution. No proxy or TLS verification was bypassed. A transient execution transport disconnection was retried after service recovery. These are tooling constraints, not application test failures.

Starlette emits a TestClient deprecation notice about its httpx integration; the tests completed successfully. The prototype does not depend on TestClient for serving requests.

## Not verified / not completed

- No real LLM call: no Gemini credential is configured in this workspace. The live provider branch has mocked boundary/schema/credential-error tests only. Actual account/model access, generation quality, real token usage, pricing and provider-specific authentication remain unverified.
- No live PostgreSQL/MySQL connection or scan. The application analyzes supplied security findings/evidence. The fixtures are synthetic, not acquired security test results.
- No held-out study dataset, expert gold labels, completed literature search, expert annotation, confidence intervals or research-effectiveness findings. Dataset sizes and research schedules in the proposal are plans.
- The experiment runner exports reports and blank annotation forms. Human coding, retrieval relevance judgments, statistical analysis and manuscript results are separate planned stages described in the protocol; they are not automatically inferred from structural API metrics.
- No production authentication, user-level authorization, encryption-at-rest, deployment hardening or public exposure has been tested. Bind to loopback for internal research.
- Draft setup instructions may be saved in environment settings; saving is not publication or a validation of restoration in a new task. Source code has not been pushed or published.
