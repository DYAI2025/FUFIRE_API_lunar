# BaZi Engine - Performance-Analyse und Skalierung

## Aktuelle Konfiguration

### Fly.io Deployment
```toml
[vm]
  memory = 1GB
  cpu_kind = 'shared'
  cpus = 1

[http_service]
  min_machines_running = 1
  auto_stop_machines = false
  auto_start_machines = true
```

### Uvicorn Server
- **Default:** Synchrones Processing (1 Worker)
- **Keine Worker-Konfiguration** im Dockerfile
- **Port:** 8080

---

## Performance-Charakteristiken

### Berechnungs-Komplexität pro Request

Eine BaZi-Berechnung umfasst:

1. **Zeit-Parsing & Validierung** (~0.5-1ms)
   - ISO 8601 Parsing
   - Timezone-Lookup (zoneinfo)
   - DST-Validierung

2. **Astronomische Berechnungen** (~10-50ms)
   - Julian Day Konvertierung (~0.1ms)
   - LiChun-Crossing (solcross_ut) (~5-10ms)
   - 12 Monatsgrenzen-Crossings (~15-30ms)
   - Optional: 24 Solar Terms (~30-60ms zusätzlich)

3. **Säulen-Berechnungen** (~0.1ms)
   - Jahr-Säule (trivial)
   - Monat-Säule (trivial)
   - Tag-Säule (JDN-Berechnung)
   - Stunde-Säule (trivial)

4. **Response-Serialisierung** (~0.5-1ms)
   - JSON-Encoding
   - Pydantic-Validierung

**Geschätzte Gesamtdauer:**
- **Minimal (ohne Solar Terms):** ~15-25ms
- **Maximal (mit Solar Terms):** ~50-100ms
- **Durchschnitt:** ~30ms

### Memory-Nutzung

- **Base Image (Python 3.11-slim):** ~50 MB
- **Swiss Ephemeris Libraries:** ~20 MB
- **Ephemeris Data Files:** ~3 MB (geladen)
- **FastAPI + Uvicorn:** ~30 MB
- **Pro Request (Stack):** ~1-2 MB

**Gesamt Base:** ~100 MB
**Verfügbar für Requests:** ~900 MB

**Max. parallele Requests (Memory-Limit):**
```
900 MB / 2 MB pro Request = ~450 parallele Requests
```

### CPU-Nutzung

- **1 Shared CPU** (ca. 0.5-1.0 vCPU auf Fly.io)
- **Pro Request:** ~30ms CPU-Zeit
- **CPU-Bound:** Ja (astronomische Berechnungen)

**Throughput (ohne Concurrency):**
```
1000ms / 30ms = ~33 Requests/Sekunde (single-threaded)
```

---

## Maximale Nutzer-Kapazität

### Szenario 1: Aktuelle Konfiguration (1 Worker)

**Specs:**
- 1 Shared CPU
- 1 GB RAM
- 1 Uvicorn Worker (synchron)

**Bottleneck:** CPU (single-threaded)

**Kapazität:**
- **Sequentiell:** ~33 Requests/Sekunde
- **Parallele Nutzer:** ~1-3 gleichzeitig
  - Bei 30ms Antwortzeit: 1 Request zur Zeit
  - Mit Connection Queuing: 2-3 Requests in Warteschlange

**User Experience:**
- Bei <10 Nutzern/Minute: Ausgezeichnet (<50ms)
- Bei 10-30 Nutzern/Minute: Gut (50-200ms)
- Bei >50 Nutzern/Minute: Langsam (>500ms Warteschlange)

**Maximale Nutzerlast:**
```
~30 Nutzer pro Minute (bei 1 Request pro Nutzer)
~500 Nutzer pro Stunde
```

---

### Szenario 2: Optimiert mit Uvicorn Workers

**Konfiguration:**
```dockerfile
CMD ["uvicorn", "bazi_engine.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "4"]
```

**Kapazität:**
- **4 Worker × 33 Req/s** = ~132 Requests/Sekunde
- **Parallele Nutzer:** ~10-15 gleichzeitig

**User Experience:**
- Bei <50 Nutzern/Minute: Ausgezeichnet
- Bei 50-120 Nutzern/Minute: Gut
- Bei >200 Nutzern/Minute: Degradation

**Maximale Nutzerlast:**
```
~120 Nutzer pro Minute
~7.000 Nutzer pro Stunde
```

**Limitation:** RAM (4 Worker × ~100 MB = 400 MB + Base)

---

### Szenario 3: Horizontale Skalierung (Fly.io)

**Konfiguration:**
```toml
[[vm]]
  memory = '1gb'
  cpus = 1

[http_service]
  min_machines_running = 2  # Immer 2 Instanzen
```

Mit **4 Maschinen à 4 Worker:**
- **16 Worker total**
- **~530 Requests/Sekunde**
- **~30.000 Nutzer/Stunde**

**Kosten (Fly.io Pricing 2026):**
- 1 GB Shared CPU: ~$2/Monat pro Maschine
- 4 Maschinen: ~$8/Monat

---

### Szenario 4: Optimiert mit Caching

**Redis-Cache** für identische Anfragen:

```python
# Cache-Hit-Rate: ~30% (typisch für Astrology-Apps)
# Cache TTL: 1 Stunde

Cached Request: ~1-2ms (statt 30ms)
```

**Effektive Kapazität:**
- **70% uncached:** 132 Req/s × 0.7 = 92 Req/s
- **30% cached:** 500 Req/s × 0.3 = 150 Req/s
- **Total:** ~242 Requests/Sekunde

**Maximale Nutzerlast (4 Worker + Cache):**
```
~240 Nutzer pro Minute
~14.000 Nutzer pro Stunde
```

---

## Performance-Bottlenecks

### 1. Swiss Ephemeris `solcross_ut()`
- **CPU-intensiv:** Iterative Berechnung
- **Nicht parallelisierbar** (pro Request)
- **Lösungen:**
  - Caching (gleiche Daten → gleiche LiChun/Jie-Zeiten)
  - Pre-Computation (Solar Terms für Jahre vorberechnen)

### 2. Uvicorn Single-Worker
- **Synchrones Processing**
- **Lösung:** Multi-Worker (siehe Szenario 2)

### 3. Python GIL (Global Interpreter Lock)
- **Limitation:** Multi-Threading ineffektiv
- **Lösung:** Multi-Processing (Uvicorn Workers)

### 4. Ephemeris File I/O
- **Swiss Ephemeris liest Dateien**
- **Lösung:** Memory-Mapped Files (bereits von pyswisseph genutzt)

---

## Optimierungs-Empfehlungen

### Kurzfristig (Quick Wins)

#### 1. Uvicorn Multi-Worker aktivieren
```dockerfile
# Dockerfile Zeile 36 ändern:
CMD ["uvicorn", "bazi_engine.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker"]
```

**Impact:** 4x Throughput (~132 Req/s)

---

#### 2. Fly.io Auto-Scaling konfigurieren
```toml
[http_service]
  min_machines_running = 1
  auto_stop_machines = 'suspend'  # statt 'stop'
  auto_start_machines = true

[[services.concurrency]]
  type = "requests"
  hard_limit = 50
  soft_limit = 25
```

**Impact:** Automatisches Scaling bei Last

---

#### 3. Response-Kompression aktivieren
```python
# app.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**Impact:** 60-80% kleinere Responses (bei Solar Terms)

---

### Mittelfristig (Moderat)

#### 4. Redis-Caching implementieren
```python
# app.py
import redis
import hashlib
import json

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

@app.post("/calculate/bazi")
async def calculate_bazi_endpoint(req: BaziRequest):
    # Cache-Key generieren
    cache_key = hashlib.sha256(
        f"{req.date}:{req.tz}:{req.lon}:{req.lat}:{req.standard}:{req.boundary}".encode()
    ).hexdigest()

    # Cache-Lookup
    cached = redis_client.get(f"bazi:{cache_key}")
    if cached:
        return json.loads(cached)

    # Berechnung
    inp = BaziInput(...)
    res = compute_bazi(inp)
    result = {...}

    # Cache speichern (1h TTL)
    redis_client.setex(f"bazi:{cache_key}", 3600, json.dumps(result))

    return result
```

**Impact:** 15x schnellere Antworten für gecachte Requests

---

#### 5. Rate Limiting implementieren
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/calculate/bazi")
@limiter.limit("10/minute")  # Max 10 Requests pro Minute pro IP
async def calculate_bazi_endpoint(request: Request, req: BaziRequest):
    ...
```

**Impact:** Schutz vor Missbrauch

---

### Langfristig (Advanced)

#### 6. Async Processing mit Background Tasks
```python
from fastapi import BackgroundTasks
import uuid

tasks_db = {}  # In Produktion: Redis

@app.post("/calculate/bazi/async")
async def calculate_bazi_async(req: BaziRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    background_tasks.add_task(compute_and_store, task_id, req)
    return {"task_id": task_id, "status": "processing"}

@app.get("/calculate/bazi/status/{task_id}")
async def get_task_status(task_id: str):
    result = tasks_db.get(task_id)
    if result:
        return {"status": "completed", "result": result}
    return {"status": "processing"}

def compute_and_store(task_id: str, req: BaziRequest):
    inp = BaziInput(...)
    res = compute_bazi(inp)
    tasks_db[task_id] = {...}
```

**Impact:** Nicht-blockierende API für langsame Clients

---

#### 7. Solar Terms Pre-Computation
```python
# Pre-compute Solar Terms für Jahre 1900-2100
# Speichere in SQLite/PostgreSQL
# Lookup statt Berechnung bei Requests

# Reduziert Berechnungszeit von ~50ms auf ~5ms
```

**Impact:** 10x schnellere Berechnungen

---

#### 8. CDN für statische Responses
```python
# Für häufig angefragte Daten (z.B. berühmte Personen)
# CloudFlare Cache mit lange TTL

@app.post("/calculate/bazi")
async def calculate_bazi_endpoint(req: BaziRequest, response: Response):
    ...
    response.headers["Cache-Control"] = "public, max-age=3600"
    return result
```

**Impact:** Entlastung des Backends

---

## Empfohlene Konfiguration für Produktion

### Für kleine Apps (<1.000 Nutzer/Tag)

```toml
# fly.toml
[[vm]]
  memory = '1gb'
  cpus = 1

[http_service]
  min_machines_running = 1
```

```dockerfile
# Dockerfile
CMD ["uvicorn", "bazi_engine.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "4"]
```

**Kapazität:** ~120 Nutzer/Minute, ~7.000 Nutzer/Stunde
**Kosten:** ~$2/Monat

---

### Für mittlere Apps (1.000-10.000 Nutzer/Tag)

```toml
# fly.toml
[[vm]]
  memory = '2gb'
  cpus = 2

[http_service]
  min_machines_running = 2

[[services.concurrency]]
  type = "requests"
  hard_limit = 100
  soft_limit = 50
```

```dockerfile
CMD ["uvicorn", "bazi_engine.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "8"]
```

**+ Redis-Caching**

**Kapazität:** ~500 Nutzer/Minute, ~30.000 Nutzer/Stunde
**Kosten:** ~$15-20/Monat (Fly.io + Redis)

---

### Für große Apps (>10.000 Nutzer/Tag)

- **Multi-Region Deployment** (fra, iad, syd)
- **Load Balancer** (Fly.io Anycast)
- **PostgreSQL** für Pre-Computed Solar Terms
- **Redis Cluster** für Caching
- **CDN** (CloudFlare)
- **Monitoring** (Prometheus + Grafana)

**Kapazität:** ~10.000+ Nutzer/Minute
**Kosten:** ~$100-500/Monat

---

## Monitoring-Metriken

### Key Performance Indicators (KPIs)

1. **Response Time (P50, P95, P99)**
   - Target P95: <100ms
   - Target P99: <200ms

2. **Throughput**
   - Requests/Sekunde
   - Target: >50 Req/s

3. **Error Rate**
   - Target: <0.1%

4. **Cache Hit Rate**
   - Target: >30%

5. **CPU Utilization**
   - Target: 50-70% (nicht >80%)

6. **Memory Usage**
   - Target: <80% von verfügbar

---

## Zusammenfassung

### Maximale Nutzer-Kapazität (nach Konfiguration)

| Konfiguration | Req/s | Nutzer/Minute | Nutzer/Stunde | Kosten/Monat |
|---------------|-------|---------------|---------------|--------------|
| **Aktuell (1 Worker)** | 33 | 30 | 2.000 | $2 |
| **+ Multi-Worker (4)** | 132 | 120 | 7.000 | $2 |
| **+ Redis Cache** | 242 | 240 | 14.000 | $7 |
| **+ Horizontal Scaling (2 VMs)** | 484 | 480 | 28.000 | $12 |
| **+ Horizontal Scaling (4 VMs)** | 968 | 960 | 56.000 | $20 |

### Empfehlung

**Start:** Szenario 2 (Multi-Worker)
- Einfach zu implementieren
- 4x bessere Performance
- Keine zusätzlichen Kosten

**Growth:** Szenario 4 (+ Redis Cache)
- Bei >1.000 Nutzern/Tag
- Deutliche Performance-Verbesserung
- Moderate Kosten

**Scale:** Horizontal Scaling
- Bei >10.000 Nutzern/Tag
- Multi-Region für globale Nutzer
- Enterprise-Grade Performance
