# CheckMate — Project State Summary for New Chat

## What this project is
CheckMate: AI-powered handwritten academic answer-sheet grading system. Native Android client (Kotlin/Jetpack Compose) + FastAPI backend, built at `D:\Desktop\MLT Project\checkmate-android\`. A separate old web prototype exists at `D:\Desktop\MLT Project\checkmate\` — **do not touch that one**, it's kept only as reference. Team: Kartik Mishra, Ridhi Sharma (user, ridhisharma2521@gmail.com), Fiza Khan, Priyanshu Jaiswal (students); Puneet Kumar Goyal (KIET faculty, likely project guide — unconfirmed). KIET Group of Institutions, Ghaziabad.

## Architecture (built, real, verified working end-to-end)
- **Backend**: FastAPI + SQLAlchemy(async) + SQLite, in-process asyncio job queue (no Celery/Redis), PyMuPDF for PDF/image rendering.
- **Pipeline** (~3 LLM calls/submission, not per-page): OCR extraction (Gemini vision, schema-constrained) → hybrid answer mapping (deterministic label-normalize first, LLM content-match fallback only for unresolved entries) → dual-layer scoring (35% sentence-transformer similarity + 65% LLM rubric, +5% bonus each for matched diagram/table/code) → aggregation (resolves "attempt any N of M" as best-N-of-M *after* grading, not before).
- **Model router**: provider-agnostic, ordered candidate chain per capability (vision/text), credential-pooling within a provider + cross-provider failover, exponential-backoff cooldown (60s quota-related / 15s other, doubling per failure, capped 600s). Cloud-only for OCR; Ollama local model allowed only as last-resort text-only grading fallback. Currently only one Gemini free-tier key configured in practice (15 RPM/1500 RPD limit → ~5 submissions/min ceiling).
- **Android client**: Upload → Progress (real 5-stage backend-driven checklist, no fake timer) → Results (Overview/Questions/Notes tabs, single-tap teacher override) screens, shared ViewModel, Retrofit/OkHttp/Gson.
- **Verified real**: full pipeline tested end-to-end via emulator + adb automation, including a genuinely real graded run (9.16/14.0, coherent per-question feedback, 95% handwriting confidence). Router failover confirmed working against a real Gemini 503 in the wild (fell through to Ollama, which then failed since Ollama isn't actually installed).
- **Not yet built**: camera capture, batch upload (backend supports 1 file/student only, no multi-student results UI), auth/multi-tenant data model (phase 3), Postgres migration, formal accuracy evaluation (CER/mapping-accuracy/QWK) — no such evaluation has ever been run at scale.

## Two academic papers (both cleaned up, both IEEE format, `D:\Downloads\`)
1. **Review paper** (`review_paper_revised.tex`) — literature survey, 3 identified gaps (content-grounded mapping / pipeline call-architecture / content-type scoring outside math) that motivate CheckMate's design. Had a self-incriminating "earlier draft had fabricated data" disclosure sentence — **removed**. Had 4 unverified/placeholder citations — **replaced with real, verified sources** via web research.
2. **Research paper** (`checkmate_research_paper.tex`) — was originally a **fabricated draft** with invented CER/QWK/accuracy numbers and wrong architecture (React frontend, cloud deployment — neither real). **Completely rewritten** as an honest systems paper: real architecture, 2 algorithms (hybrid mapper, router failover) matching actual code, 2 TikZ diagrams, a labeled-illustrative worked example (no fake numbers), honest "preliminary functional evaluation" section stating plainly that no accuracy benchmark exists, specific real limitations. 8 pages, validated.

## BTech final-year presentation
`CheckMate_BTech_Presentation_v2.pptx` — filled from a department template with real content: real architecture diagram, real Android screenshots (including the real 9.16/14.0 graded example), bolded sub-headings, a proper student-project-scale cost estimate (~₹0 actual spend, ~₹1,500–3,300 estimated if a public demo were deployed). A few fields deliberately left blank/flagged: Project ID, guide-name confirmation, SDG evidence, paper submission status — genuinely unknown, not guessed.

## Critical standing rules for this project
- **Never fabricate evaluation data/numbers.** This project got burned once already (caught in an earlier draft). Always state "not yet measured" / "future work" instead of inventing figures.
- **Never paste/print API keys or secrets in chat**, and never read/cat a file known to contain secrets myself — even to "verify" it. Have the user edit `.env` directly and confirm verbally. (Learned the hard way — did this wrong twice.)
- Old `checkmate` project is off-limits for edits.
- No LaTeX compiler or LibreOffice installed on this machine — can't visually verify `.tex`/`.pptx` output directly; always ask the user to recompile/open and report back.
- This machine's Bash tool is often missing core utilities (curl, cat, tail, nohup, grep sometimes) inconsistently — prefer PowerShell or Python (`C:\Users\Acer\anaconda3\python.exe`) for anything that needs to actually work.
- C: drive runs low on space; large caches (Gradle, ML models, AVDs) were redirected to D: via env vars (`GRADLE_USER_HOME=D:\gradle-home`, `ANDROID_AVD_HOME=D:\android-avd-home`).

## Where things stand (user's own words, most recent)
"Review done, research done, frontend basic, backend mid level done." Next open threads if resumed: real accuracy evaluation, camera/batch upload, auth/multi-tenant phase, or further presentation/paper polish.
