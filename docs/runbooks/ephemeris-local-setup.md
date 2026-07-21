# Runbook: Swiss Ephemeris Local Setup

**Symptom:** `503 ephemeris_unavailable` when calling any calculation endpoint in local development.

**Root cause:** The engine calls the Swiss Ephemeris C library which requires binary data files
to compute planetary positions. Docker downloads and verifies these files at build time. For
local development outside Docker, you must supply them manually.

---

## Required Files

| File | Contents |
|------|----------|
| `sepl_18.se1` | Main planets (Sun through Pluto) |
| `semo_18.se1` | Moon |
| `seas_18.se1` | Asteroids and minor bodies |
| `seplm06.se1` | Outer planets, pre-1800 extension |

All four files are required. Missing any one of them causes `ephemeris_unavailable` errors
on requests that need that body (Moon calculations fail with `semo_18.se1` absent, etc.).

---

## Step-by-Step Setup

### 1. Download the files

Files are available from the Swiss Ephemeris project at https://www.astro.com/swisseph/.
Download the `sweph18` package which contains all four required files.

```bash
mkdir -p ~/.swisseph
cd ~/.swisseph

# Example using curl (check astro.com for current download paths):
curl -O https://www.astro.com/ftp/swisseph/ephe/sepl_18.se1
curl -O https://www.astro.com/ftp/swisseph/ephe/semo_18.se1
curl -O https://www.astro.com/ftp/swisseph/ephe/seas_18.se1
curl -O https://www.astro.com/ftp/swisseph/ephe/seplm06.se1
```

Alternatively, extract them from the Docker image (requires the image to be built first):

```bash
# Build the image (downloads and verifies files at build time)
docker build -t fufire .

# Copy files out
docker create --name tmp_fufire fufire
docker cp tmp_fufire:/usr/local/share/swisseph ~/.swisseph
docker rm tmp_fufire
```

### 2. Set `SE_EPHE_PATH`

```bash
export SE_EPHE_PATH=~/.swisseph
```

To persist across shell sessions, add it to your shell profile (`~/.zshrc`, `~/.bashrc`):

```bash
echo 'export SE_EPHE_PATH=~/.swisseph' >> ~/.zshrc
```

Or use a `.env` file in the project root (loaded automatically by `uvicorn` when using
`python-dotenv`):

```
SE_EPHE_PATH=/path/to/your/swisseph
```

### 3. Verify

Start the server and check the health endpoint:

```bash
uvicorn bazi_engine.app:app --reload --port 8080
curl -s http://localhost:8080/v1/health | python -m json.tool
```

Expected output when files are found:

```json
{
  "status": "ok",
  "dependencies": {
    "ephemeris": { "status": "ok", "detail": "type=swisseph" },
    "rate_limiter": { "status": "ok", "detail": "type=memory" }
  }
}
```

If `ephemeris` still shows `"status": "degraded"`, double-check the path:

```bash
ls -la $SE_EPHE_PATH
# Should list sepl_18.se1, semo_18.se1, seas_18.se1, seplm06.se1
```

---

## Tests Without Ephemeris

The test suite handles missing ephemeris gracefully: tests that require real planetary
calculations are skipped automatically when `SE_EPHE_PATH` is not set or the files are absent.
You will see `pytest` output like:

```
SKIPPED [reason: ephemeris not available]
```

This is expected behaviour — the test suite is designed to be runnable in CI without
ephemeris files. Only the golden/snapshot tests and transit tests require them.

---

## Docker (Recommended for Production and CI)

The multi-stage `Dockerfile` downloads all four files and verifies their SHA256 checksums
at build time. If Astro.com changes the files, the build fails with a checksum mismatch —
this is intentional to prevent silent data corruption.

```bash
docker build -t fufire .
docker run -p 8080:8080 fufire
```

No `SE_EPHE_PATH` configuration is needed inside the Docker container; the files are
placed at `/usr/local/share/swisseph` and the engine finds them automatically.

---

## Error Reference

| Error | Meaning |
|-------|---------|
| `503 ephemeris_unavailable` | Files missing or `SE_EPHE_PATH` points to wrong directory |
| `SwissEph file not found` (log) | Same as above — check `SE_EPHE_PATH` |
| `EphemerisUnavailableError` (Python) | Raised by `ephemeris.py` when the C library cannot load files |
