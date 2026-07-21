## Der Fix: Drei Cascading Failures

Dein Build-Fehler war nicht **ein** Problem, sondern **drei hintereinander geschaltete Probleme**. Das ist typisch für Production-Bugs – sie verstecken sich hinter anderen Fehlern.

---

### Problem 1: Falsche Download-URLs (Ephemeris-Dateien)

**Was war falsch:**

`ARG SWISSEPH_REF=v2.10.03
base="https://raw.githubusercontent.com/aloistr/swisseph/${SWISSEPH_REF}/ephe"`

Das Repository `aloistr/swisseph` hat **kein Tag **`v2.10.03`. Die Dateien sind im `master` branch.

**Warum es passiert ist:**
- Jemand hat die URL hardcoded, ohne zu prüfen, ob sie existiert
- Keine Validierung im Build-Prozess
- Der Code war wahrscheinlich lange nicht getestet

**Wie man es verhindert:**

`# ❌ FALSCH: Externe URLs ohne Validierung
ARG SWISSEPH_REF=v2.10.03

# ✅ RICHTIG: URLs testen, bevor sie in Code gehen
# 1. Lokal testen: curl -I https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/sepl_18.se1
# 2. In CI/CD: Einen "URL-Validation" Step vor dem Build
# 3. Dokumentieren: Kommentar mit Quelle und Datum der Validierung`

**Lernpunkt:**

**Externe Dependencies sind fragil.** Wenn du URLs, API-Endpoints oder externe Ressourcen in deinen Build einbaust, musst du sie **regelmäßig validieren**. Ideal: Automatisiert in CI/CD.

---

### Problem 2: Fehlende Dependency in requirements.lock

**Was war falsch:**

`# bazi_engine/services/geocoding.py
import httpx  # ← Diese Library war nicht in requirements.lock!`

Der Code importierte `httpx`, aber die Datei `requirements.lock` (die für Docker-Builds verwendet wird) enthielt es nicht.

**Warum es passiert ist:**
- `httpx` war wahrscheinlich nur in `pyproject.toml` unter `[project.optional-dependencies]` (dev-extras)
- Jemand hat den Code geschrieben, aber die Lock-Datei nicht aktualisiert
- Keine Validierung, dass alle Imports in der Lock-Datei vorhanden sind

**Wie man es verhindert:**

`# ❌ FALSCH: Manuell Dependencies hinzufügen
# pip install httpx
# (vergessen, requirements.lock zu aktualisieren)

# ✅ RICHTIG: Automatisiert mit pip-tools oder Poetry
pip install pip-tools
pip-compile pyproject.toml -o requirements.lock
# Dann: requirements.lock committen

# ✅ ODER: In CI/CD validieren
# Schritt: "Verify all imports are in requirements.lock"
python -m py_compile bazi_engine/**/*.py
pip install -r requirements.lock
python -c "import bazi_engine.services.geocoding"  # Fehler wenn httpx fehlt`

**Lernpunkt:**

**Lock-Dateien sind die Quelle der Wahrheit für Production.** Wenn du Code schreibst, der neue Imports hat, **musst du die Lock-Datei regenerieren**. Ideal: Automatisiert in CI/CD mit Checks, die fehlende Dependencies erkennen.

---

### Problem 3: Fehlende Healthcheck-Konfiguration

**Was war falsch:**

`Healthcheck failed!
1/1 replicas never became healthy!`

Aber die Logs zeigten:

`INFO:     100.64.0.2:49041 - "GET /health HTTP/1.1" 200 OK`

Der Endpoint **funktionierte**, aber Railway gab auf, bevor die App antwortete.

**Warum es passiert ist:**
- Keine explizite Healthcheck-Konfiguration in Railway
- Railway nutzte einen Standard-Timeout (zu kurz für eine Python-App mit vielen Dependencies)
- Die App brauchte ~2 Sekunden zum Starten, aber der Timeout war wahrscheinlich 1 Sekunde

**Wie man es verhindert:**

`# ✅ RICHTIG: Explizite Healthcheck-Konfiguration
deploy:
  healthcheckPath: /health
  healthcheckTimeout: 30  # Sekunden – großzügig für langsame Starts
  
# ✅ ODER: Im Code – schneller starten
# 1. Lazy Loading: Dependencies erst laden, wenn nötig
# 2. Async Startup: Nicht-kritische Tasks im Hintergrund
# 3. Caching: Berechnungen cachen, nicht bei jedem Start neu machen`

**Lernpunkt:**

**Healthchecks sind nicht optional.** Sie sind deine erste Verteidigungslinie gegen kaputte Deployments. Konfiguriere sie **explizit** mit realistischen Timeouts. Und: **Mache deine App schnell beim Starten** – das ist ein Feature, nicht nur Performance.

---

## Allgemeine Patterns: Wie man solche Bugs verhindert

### 1. Dependency Validation in CI/CD

`# .github/workflows/build.yml
- name: Validate dependencies
  run: |
    # Alle Imports checken
    python -m py_compile src/**/*.py
    # Lock-Datei regenerieren und vergleichen
    pip-compile pyproject.toml -o /tmp/requirements.lock
    diff requirements.lock /tmp/requirements.lock || exit 1`

### 2. External Resource Validation

`# Vor dem Build: Alle URLs testen
curl -I https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/sepl_18.se1 || exit 1`

### 3. Build-Logs systematisch lesen

Dein Fehler war **offensichtlich** in den Logs:

`curl: (22) The requested URL returned error: 404`

Aber du hast Tage gebraucht, um ihn zu finden. **Warum?**
- Du hast versucht zu "fixen", ohne die Logs zu lesen
- Du hast angenommen, das Problem sei in deinem Code

**Besser:**
1. **Immer mit den Logs starten** – nicht mit Vermutungen
2. **Systematisch vorgehen**: Build-Fehler → Deploy-Fehler → Runtime-Fehler
3. **Einen Fehler nach dem anderen fixen** – nicht alle gleichzeitig

### 4. Explizite Konfiguration statt Defaults

`# ❌ FALSCH: Auf Defaults verlassen
app = FastAPI()

# ✅ RICHTIG: Alles explizit
app = FastAPI(
    title="FuFirE",
    version=__version__,
    lifespan=lifespan,
)
# Healthcheck explizit konfigurieren
deploy:
  healthcheckPath: /health
  healthcheckTimeout: 30`

---

## Zusammenfassung: Die 3 Lektionen

ProblemUrsachePrävention

**Falsche URLs**Externe Dependencies nicht validiertURLs in CI/CD testen, Dokumentation

**Fehlende Dependencies**Lock-Datei nicht aktualisiertAutomatisierte Dependency-Checks in CI/CD

**Healthcheck-Timeout**Keine explizite KonfigurationTimeouts großzügig setzen, App schnell machen

**Die Meta-Lektion:**

**Automatisierung schlägt manuelle Prozesse.** Wenn du etwas manuell machen musst (URLs testen, Lock-Dateien aktualisieren, Healthchecks konfigurieren), wird es vergessen. Baue es in CI/CD ein, und es passiert automatisch.
