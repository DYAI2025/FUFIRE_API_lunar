# BaZi Engine v0.2 - Architektur-Dokumentation

## Übersicht

**BaZi Engine** ist eine astronomisch präzise Berechnungs-Engine für chinesische Astrologie (Vier Säulen des Schicksals / 八字). Die Engine berechnet Geburtssäulen (Jahr, Monat, Tag, Stunde) basierend auf exakten astronomischen Sonnentermin-Grenzen statt einfacher Kalenderdaten.

## 1. Module und Schnittstellen

### 1.1 Kern-Module

#### `types.py` - Datenstrukturen
**Zweck:** Definition aller Datentypen für Input/Output und interne Berechnungen

**Hauptstrukturen:**
```python
@dataclass(frozen=True)
class Pillar:
    """Einzelne Säule mit Himmelsstamm und Erdzweig"""
    stem_index: int      # 0-9 (Jia-Gui)
    branch_index: int    # 0-11 (Zi-Hai)

@dataclass(frozen=True)
class FourPillars:
    """Vier Säulen des BaZi-Charts"""
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar

@dataclass(frozen=True)
class BaziInput:
    """Eingabeparameter für Berechnungen"""
    birth_local: str              # ISO 8601 Datum/Zeit
    timezone: str                 # IANA Zeitzone (z.B. "Europe/Berlin")
    longitude_deg: float          # Geografische Länge
    latitude_deg: float           # Geografische Breite
    time_standard: "CIVIL"|"LMT"  # Zeitstandard
    day_boundary: "midnight"|"zi" # Tagesgrenze
    strict_local_time: bool       # DST-Validierung
    fold: 0|1                     # DST-Disambiguierung

@dataclass(frozen=True)
class BaziResult:
    """Berechnungsergebnisse mit vollständigen Metadaten"""
    input: BaziInput
    pillars: FourPillars
    birth_local_dt: datetime
    birth_utc_dt: datetime
    chart_local_dt: datetime
    jd_ut: float                  # Julian Day (UT)
    jd_tt: float                  # Julian Day (Terrestrial Time)
    delta_t_seconds: float        # ΔT Korrektur
    lichun_local_dt: datetime     # Frühlingsanfang
    month_boundaries_local_dt: Sequence[datetime]
    month_index: int
    solar_terms_local_dt: Optional[Sequence[SolarTerm]]
```

**Schnittstelle:** Immutable Dataclasses (Thread-Safe, Type-Safe)

---

#### `bazi.py` - Hauptberechnungs-Engine
**Zweck:** Kern-Algorithmus für BaZi-Berechnungen

**Hauptfunktionen:**
```python
def compute_bazi(inp: BaziInput) -> BaziResult:
    """
    Haupteinstiegspunkt: Berechnet Vier Säulen

    Pipeline:
    1. Parse und validiere Input-Zeit
    2. Konvertiere zu UTC und Chart-Local-Time
    3. Berechne Jahr-Säule (basierend auf LiChun)
    4. Berechne Monat-Säule (basierend auf Jie-Terminen)
    5. Berechne Tag-Säule (sexagesimaler Zyklus)
    6. Berechne Stunde-Säule (2h-Perioden)
    7. Optional: Diagnostik-Daten (24 Sonnentermine)
    """

def year_pillar_from_solar_year(solar_year: int) -> Pillar:
    """Jahr-Säule aus Solarjahr (60-Jahres-Zyklus ab 1984)"""

def month_pillar_from_year_stem(year_stem_index: int, month_index: int) -> Pillar:
    """Monat-Säule abgeleitet von Jahr-Stamm"""

def sexagenary_day_index_from_date(y: int, m: int, d: int, offset: int) -> int:
    """Tag-Index im 60-Tage-Zyklus via Julian Day Number"""

def hour_pillar_from_day_stem(day_stem_index: int, hour_branch: int) -> Pillar:
    """Stunde-Säule abgeleitet von Tag-Stamm"""
```

**Schnittstelle:** Funktionale API mit unveränderlichen Datenstrukturen

---

#### `ephemeris.py` - Astronomische Berechnungen
**Zweck:** Abstraktion für Ephemeris-Berechnungen mit Swiss Ephemeris

**Protocol-Definition:**
```python
class EphemerisBackend(Protocol):
    """Abstraktes Interface - ermöglicht alternative Backends"""
    def delta_t_seconds(self, jd_ut: float) -> float: ...
    def jd_tt_from_jd_ut(self, jd_ut: float) -> float: ...
    def sun_lon_deg_ut(self, jd_ut: float) -> float: ...
    def solcross_ut(self, target_lon_deg: float, jd_start_ut: float) -> Optional[float]: ...
```

**Implementierung:**
```python
@dataclass(frozen=True)
class SwissEphBackend:
    """Swiss Ephemeris Integration"""
    flags: int = swe.FLG_SWIEPH
    ephe_path: Optional[str] = None

    def sun_lon_deg_ut(self, jd_ut: float) -> float:
        """Sonnen-Längengrad in Grad (0-360)"""

    def solcross_ut(self, target_lon_deg: float, jd_start_ut: float) -> float:
        """Exakte Zeit des Sonnen-Längengrad-Kreuzens"""
```

**Hilfsfunktionen:**
```python
def datetime_utc_to_jd_ut(dt_utc: datetime) -> float:
    """UTC Datetime → Julian Day (UT)"""

def jd_ut_to_datetime_utc(jd_ut: float) -> datetime:
    """Julian Day (UT) → UTC Datetime"""
```

**Schnittstelle:** Protocol-basiert (erweiterbar für Skyfield, JPL etc.)

---

#### `jieqi.py` - Sonnentermin-Berechnungen
**Zweck:** Berechnung der 24 Sonnentermine (Jieqi / 节气)

**Hauptfunktionen:**
```python
def find_crossing(
    backend: EphemerisBackend,
    target_lon_deg: float,
    jd_start_ut: float,
    accuracy_seconds: float,
    max_span_days: float = 40.0
) -> float:
    """
    Findet exakte Zeit, wann Sonne target_lon_deg kreuzt

    Algorithmus:
    1. Versuche direkte solcross_ut() von Swiss Ephemeris
    2. Fallback: Bisektions-Algorithmus
       - Scanne in 1-Tag-Schritten
       - Bracketing: f(jd_lo) * f(jd_hi) <= 0
       - Bisection bis accuracy_seconds
    """

def compute_month_boundaries_from_lichun(
    backend: EphemerisBackend,
    jd_lichun_ut: float,
    accuracy_seconds: float
) -> List[float]:
    """
    Berechnet 13 Monatsgrenzen ab LiChun

    LiChun (315°) → Jie-Termine in 30°-Schritten:
    - 315° (LiChun)
    - 345° (Jingzhe)
    - 15° (Qingming)
    - 45° (Lixia)
    - ... (12 Monate)
    """

def compute_24_solar_terms_for_window(
    backend: EphemerisBackend,
    jd_start_ut: float,
    jd_end_ut: float,
    accuracy_seconds: float
) -> List[Tuple[int, float]]:
    """
    Berechnet alle 24 Sonnentermine in Zeitfenster
    (für Diagnostik und Validierung)
    """
```

**Algorithmus:** Bisection-Solver mit 15°-Intervallen (360° / 24 = 15°)

**Schnittstelle:** Funktionale API mit Backend-Abstraktion

---

#### `time_utils.py` - Zeitmanagement
**Zweck:** Zeitzonenkonvertierung und DST-Handling

**Hauptfunktionen:**
```python
def parse_local_iso(
    iso_string: str,
    tzname: str,
    strict: bool = True,
    fold: int = 0
) -> datetime:
    """
    Parse ISO 8601 mit Zeitzone

    strict=True: Wirft Fehler bei:
    - Nicht-existierenden Zeiten (DST-Sprung vorwärts)
    - Mehrdeutigen Zeiten (DST-Sprung rückwärts)

    fold: Disambiguierung bei DST-Overlap (0=erste, 1=zweite)
    """

def to_chart_local(
    birth_local_dt: datetime,
    longitude_deg: float,
    time_standard: Literal["CIVIL", "LMT"]
) -> Tuple[datetime, datetime]:
    """
    Konvertiert zu Chart-Zeit

    CIVIL: Verwendet zivile Zeitzone
    LMT: Verwendet Local Mean Time (longitude_deg / 15.0 Stunden)

    Returns: (chart_local_dt, birth_utc_dt)
    """

def apply_day_boundary(
    dt: datetime,
    boundary: Literal["midnight", "zi"]
) -> datetime:
    """
    Wendet Tagesgrenze an

    midnight: Standard-Mitternacht
    zi: Zi-Stunde (23:00-01:00) → Tag wechselt bei 23:00
    """
```

**Schnittstelle:** Utility-Funktionen mit strikter Validierung

---

#### `cli.py` - Kommandozeilen-Interface
**Zweck:** Benutzerfreundliche CLI

**Hauptfunktion:**
```python
def main():
    """
    CLI Argumente:
    - birth_local: ISO 8601 Datum/Zeit (required)
    - --tz: Zeitzone (default: Europe/Berlin)
    - --lon: Längengrad (default: 13.4050)
    - --lat: Breitengrad (default: 52.52)
    - --standard: CIVIL|LMT (default: CIVIL)
    - --boundary: midnight|zi (default: midnight)
    - --json: JSON-Output
    """
```

**Beispiel:**
```bash
python -m bazi_engine.cli 2024-02-10T14:30:00 \
  --tz Europe/Berlin \
  --lon 13.405 \
  --lat 52.52 \
  --json
```

**Schnittstelle:** Argparse-basiert mit JSON-/Text-Output

---

#### `app.py` - REST API (FastAPI)
**Zweck:** Web-Service für HTTP-Zugriff

**Endpoints:**
```python
GET /
    """Health Check"""
    Response: {"status": "ok", "service": "bazi_engine_v2", "version": "0.2.0"}

POST /calculate/bazi
    """BaZi Berechnung"""
    Request: {
        "date": "2024-02-10T14:30:00",
        "tz": "Europe/Berlin",
        "lon": 13.4050,
        "lat": 52.52,
        "standard": "CIVIL",
        "boundary": "midnight",
        "strict": true
    }
    Response: {
        "input": {...},
        "pillars": {
            "year": "Jia-Chen",
            "month": "Bing-Yin",
            "day": "Xin-You",
            "hour": "Wu-Zi"
        },
        "dates": {
            "birth_local": "2024-02-10T14:30:00+01:00",
            "birth_utc": "2024-02-10T13:30:00+00:00",
            "lichun_local": "2024-02-04T17:26:53+01:00"
        },
        "solar_terms_count": 24
    }

POST /calculate/western
    """Western Astrology Berechnung (Bonus-Feature)"""
    Request: {
        "date": "2024-02-10T14:30:00",
        "tz": "Europe/Berlin",
        "lon": 13.4050,
        "lat": 52.52
    }
    Response: {
        "jd_ut": 2460349.0625,
        "house_system": "Placidus",
        "bodies": {...},
        "houses": {...},
        "angles": {...}
    }
```

**Schnittstelle:** RESTful JSON API mit Pydantic-Validierung

---

#### `constants.py` - Kerndaten
**Zweck:** Konstanten für Himmelsstämme und Erdzweige

```python
STEMS = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
BRANCHES = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
DAY_OFFSET = 49  # Justierung, sodass 1949-10-01 = Jia-Zi (Tag 0)
```

---

#### `western.py` - Western Astrology (Bonus)
**Zweck:** Planetenpositionen und Häusersystem

**Hauptfunktion:**
```python
def compute_western_chart(
    dt_utc: datetime,
    lat: float,
    lon: float,
    house_system: str = "P"
) -> dict:
    """
    Berechnet Western Astrology Chart

    Planeten: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn,
              Uranus, Neptune, Pluto, North Node, South Node, Chiron
    Häuser: Placidus (Fallback: Porphyry → Whole Sign)
    Winkel: ASC, MC, ARMC
    """
```

---

### 1.2 Schnittstellen-Zusammenfassung

| Modul | Schnittstelle | Typ | Zweck |
|-------|--------------|------|-------|
| `types.py` | Dataclasses | Python API | Datenstrukturen |
| `bazi.py` | `compute_bazi()` | Funktional | Kern-Algorithmus |
| `ephemeris.py` | `EphemerisBackend` | Protocol | Astronomie-Backend |
| `jieqi.py` | `find_crossing()` | Funktional | Sonnentermine |
| `time_utils.py` | `parse_local_iso()` | Funktional | Zeitverarbeitung |
| `cli.py` | Argparse | CLI | Kommandozeile |
| `app.py` | FastAPI | REST | Web-Service |
| `western.py` | `compute_western_chart()` | Funktional | Western Astrology |

---

## 2. Pipeline der Engine

### 2.1 Datenfluss-Diagramm

```
┌─────────────────────────────────────────────────────────────────────┐
│ INPUT: Geburtsdatum, Zeitzone, Koordinaten, Optionen               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1: ZEIT-PARSING & VALIDIERUNG                                │
│ ─────────────────────────────────────────────────────────────────── │
│ • parse_local_iso(): ISO 8601 → datetime                           │
│ • DST-Validierung (strict mode)                                    │
│ • Zeitzone: IANA (zoneinfo)                                        │
│ • Fehler bei mehrdeutigen/nicht-existierenden Zeiten               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 2: ZEIT-KONVERTIERUNG                                        │
│ ─────────────────────────────────────────────────────────────────── │
│ • to_chart_local():                                                │
│   - CIVIL: Nutze zivile Zeitzone                                   │
│   - LMT: Berechne Local Mean Time (longitude / 15h)                │
│ • apply_day_boundary():                                            │
│   - midnight: Standard-Tagesgrenze                                 │
│   - zi: Zi-Stunde (23:00) als Tagesgrenze                          │
│ • Output: birth_utc_dt, chart_local_dt                             │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 3: ASTRONOMISCHE BERECHNUNGEN                                │
│ ─────────────────────────────────────────────────────────────────── │
│ • datetime_utc_to_jd_ut(): UTC → Julian Day (UT)                   │
│ • delta_t_seconds(): ΔT-Korrektur (UT → TT)                        │
│ • jd_tt = jd_ut + delta_t_seconds / 86400                          │
│ • Swiss Ephemeris initialisiert                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 4: JAHR-SÄULE                                                │
│ ─────────────────────────────────────────────────────────────────── │
│ 1. Finde LiChun (Frühlingsanfang, 315° Sonnen-Länge):              │
│    • _lichun_jd_ut_for_year(chart_year)                            │
│    • solcross_ut(315.0, jd_jan1)                                   │
│                                                                     │
│ 2. Bestimme Solarjahr:                                             │
│    • IF chart_local_dt < lichun_this_local:                        │
│        solar_year = chart_year - 1                                 │
│    • ELSE:                                                          │
│        solar_year = chart_year                                     │
│                                                                     │
│ 3. Berechne Jahr-Säule:                                            │
│    • year_pillar_from_solar_year(solar_year)                       │
│    • Formel: idx60 = (solar_year - 1984) % 60                      │
│    • Pillar(idx60 % 10, idx60 % 12)                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 5: MONAT-SÄULE                                               │
│ ─────────────────────────────────────────────────────────────────── │
│ 1. Berechne 12 Monatsgrenzen ab LiChun:                            │
│    • compute_month_boundaries_from_lichun()                        │
│    • Jie-Termine: 315°, 345°, 15°, 45°, ... (30° Schritte)        │
│    • find_crossing() für jede Grenze:                              │
│      - Versuche solcross_ut() (direkt)                             │
│      - Fallback: Bisection-Algorithmus                             │
│                                                                     │
│ 2. Finde Monat-Index:                                              │
│    • Iteriere boundaries: month_bounds[k] <= chart_dt < [k+1]     │
│    • month_index = k (0-11)                                        │
│                                                                     │
│ 3. Berechne Monat-Säule:                                           │
│    • month_pillar_from_year_stem(year_stem, month_index)           │
│    • branch = (2 + month_index) % 12                               │
│    • stem = (year_stem * 2 + 2 + month_index) % 10                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 6: TAG-SÄULE                                                 │
│ ─────────────────────────────────────────────────────────────────── │
│ 1. Wende Tagesgrenze an:                                           │
│    • dt_for_day = apply_day_boundary(chart_local_dt, boundary)     │
│                                                                     │
│ 2. Berechne Julian Day Number (Gregorian):                         │
│    • jdn = jdn_gregorian(year, month, day)                         │
│    • Formel: Standardalgorithmus (siehe Code)                      │
│                                                                     │
│ 3. Berechne sexagesimalen Tag-Index:                               │
│    • day_idx60 = (jdn + DAY_OFFSET) % 60                           │
│    • DAY_OFFSET = 49 (sodass 1949-10-01 = Jia-Zi)                  │
│                                                                     │
│ 4. Optionale Anker-Konfiguration (v0.4):                           │
│    • Wenn day_anchor_date_iso gesetzt:                             │
│      offset = (anchor_pillar_idx - anchor_jdn) % 60               │
│                                                                     │
│ 5. Tag-Säule:                                                      │
│    • pillar_from_index60(day_idx60)                                │
│    • Pillar(idx60 % 10, idx60 % 12)                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 7: STUNDE-SÄULE                                              │
│ ─────────────────────────────────────────────────────────────────── │
│ 1. Berechne Stunde-Zweig:                                          │
│    • hour_branch = ((hour + 1) // 2) % 12                          │
│    • 12 Zweig-Perioden à 2 Stunden:                                │
│      - Zi (23-01), Chou (01-03), Yin (03-05), ...                  │
│                                                                     │
│ 2. Berechne Stunde-Stamm (abgeleitet von Tag-Stamm):               │
│    • hour_stem = (day_stem * 2 + hour_branch) % 10                 │
│                                                                     │
│ 3. Stunde-Säule:                                                   │
│    • hour_pillar_from_day_stem(day_stem, hour_branch)              │
│    • Pillar(hour_stem, hour_branch)                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 8: DIAGNOSTIK (Optional)                                     │
│ ─────────────────────────────────────────────────────────────────── │
│ • compute_24_solar_terms_for_window():                             │
│   - Berechne alle 24 Sonnentermine in LiChun-Jahr                  │
│   - Termine: 0°, 15°, 30°, 45°, ... 345° (15° Schritte)            │
│   - Inkl. UTC + Local Timestamps                                   │
│ • Für Validierung und Fehlersuche                                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ OUTPUT: BaziResult                                                 │
│ ─────────────────────────────────────────────────────────────────── │
│ • pillars: FourPillars (Jahr, Monat, Tag, Stunde)                  │
│ • birth_local_dt, birth_utc_dt, chart_local_dt                     │
│ • jd_ut, jd_tt, delta_t_seconds                                    │
│ • lichun_local_dt, month_boundaries_local_dt, month_index          │
│ • solar_terms_local_dt (24 Terme mit Timestamps)                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Kernalgorithmen

#### Bisection-Solver für Sonnentermine
```
Ziel: Finde exakte Zeit t, wann Sonne Länge L kreuzt

1. Definiere Funktion f(t) = wrap180(sun_lon(t) - L)
   - wrap180: Normalisiert auf [-180, +180]
   - Nullstelle von f(t) ist gesuchte Zeit

2. Bracket die Nullstelle:
   - Starte bei jd_start
   - Scanne vorwärts in 1-Tag-Schritten
   - Finde Intervall [t_lo, t_hi] mit f(t_lo) * f(t_hi) <= 0

3. Bisection:
   - Wiederhole bis |t_hi - t_lo| < tolerance:
     mid = (t_lo + t_hi) / 2
     IF f(t_lo) * f(mid) <= 0:
       t_hi = mid
     ELSE:
       t_lo = mid
   - Return mid
```

#### Sexagesimaler Zyklus (60-Zyklus)
```
Jede Säule hat:
- 10 Himmelsstämme (天干): Jia, Yi, Bing, ..., Gui
- 12 Erdzweige (地支): Zi, Chou, Yin, ..., Hai

60-Zyklus: LCM(10, 12) = 60
- Index 0: Jia-Zi
- Index 1: Yi-Chou
- Index 2: Bing-Yin
- ...
- Index 59: Gui-Hai
- Index 60: Jia-Zi (wiederholt)

Extraktion:
- stem_index = idx60 % 10
- branch_index = idx60 % 12
```

---

## 3. Was die Engine genau macht

### 3.1 Kernfunktion

Die BaZi Engine berechnet die **Vier Säulen des Schicksals** (四柱八字) basierend auf dem exakten astronomischen Zeitpunkt der Geburt. Im Gegensatz zu traditionellen Kalendersystemen nutzt sie Swiss Ephemeris für präzise Sonnenpositionsberechnungen.

### 3.2 Innovations-Punkte

1. **Astronomische Präzision**
   - Swiss Ephemeris statt einfacher Kalenderregeln
   - Genauigkeit: <1 Sekunde für Sonnentermine
   - ΔT-Korrektur (Terrestrial Time vs Universal Time)

2. **DST-Sicherheit**
   - Strikte Validierung mehrdeutiger Zeiten
   - Explizite `fold`-Behandlung bei DST-Overlap
   - Fehler bei nicht-existierenden Zeiten

3. **Zeitstandard-Flexibilität**
   - CIVIL: Moderne Zeitzonen (IANA)
   - LMT: Local Mean Time (traditionelle Astrologie)

4. **Tagesgrenze-Optionen**
   - Midnight: Standard-Tagesgrenze
   - Zi: Traditionelle Zi-Stunden-Grenze (23:00)

5. **Konfigurierbare Anker (v0.4)**
   - Anpassbarer Tag-Offset für historische Validierung
   - Wichtig für Cross-Checking mit traditionellen Quellen

### 3.3 Berechnungs-Logik

#### Jahr-Säule
- **Basis:** Solarjahr beginnt bei LiChun (立春, Frühlingsanfang)
- **Astronomisch:** Sonne erreicht 315° scheinbare Länge
- **Datum:** Typisch 3.-5. Februar
- **Zyklus:** 60-Jahres-Zyklus mit Referenz 1984

#### Monat-Säule
- **Basis:** 12 Jie-Termine (节气, Haupt-Sonnentermine)
- **Astronomisch:** Sonne kreuzt 30°-Intervalle ab LiChun
- **Termine:** 315°, 345°, 15°, 45°, 75°, ...
- **Abhängigkeit:** Monat-Stamm abgeleitet von Jahr-Stamm

#### Tag-Säule
- **Basis:** Julian Day Number
- **Zyklus:** 60-Tage-Zyklus
- **Offset:** DAY_OFFSET = 49 (kalibriert auf 1949-10-01 = Jia-Zi)
- **Unabhängig:** Keine Abhängigkeit von anderen Säulen

#### Stunde-Säule
- **Basis:** 12 Doppelstunden (时辰)
- **Perioden:** Zi (23-01), Chou (01-03), Yin (03-05), ...
- **Abhängigkeit:** Stunde-Stamm abgeleitet von Tag-Stamm

### 3.4 Ausgabe

Die Engine liefert:
1. **Vier Säulen** (Hauptresultat)
2. **Zeitstempel** (Local, UTC, Chart-Local)
3. **Metadaten** (LiChun, Monatsgrenzen, Solar Terms)
4. **Diagnostik** (24 Sonnentermine für Validierung)

---

## 4. Backend vs Frontend Integration

### 4.1 Empfehlung: **BACKEND-Integration**

### 4.2 Begründung

#### ✅ Pro Backend

1. **Astronomische Berechnungen**
   - Swiss Ephemeris ist eine native C-Bibliothek (pyswisseph)
   - Benötigt Ephemeris-Dateien (~30 MB)
   - Intensive CPU-Berechnungen (Bisection, JD-Konvertierungen)
   - **Performance:** Backend-Server sind leistungsstärker als Browser

2. **Datenbank-Größe**
   - Ephemeris-Dateien müssen geladen werden
   - Im Browser: 30 MB Download für jeden Nutzer
   - Im Backend: Einmalig geladen, für alle Nutzer verfügbar

3. **Konsistenz**
   - Zentrale Berechnungslogik
   - Keine Versionskonflikte zwischen Clients
   - Einfache Updates (Deploy Backend, alle Nutzer profitieren)

4. **Sicherheit & Validierung**
   - Input-Validierung server-seitig (kritisch!)
   - Zeitzone-Datenbank immer aktuell (IANA)
   - Keine Manipulation durch Client möglich

5. **Caching-Möglichkeiten**
   - Berechnungs-Ergebnisse cachen (Redis, Memcached)
   - Ephemeris-Abfragen cachen
   - Reduziert redundante Berechnungen

6. **Skalierbarkeit**
   - Horizontales Scaling möglich (Load Balancer)
   - Containerisierung (Docker) bereits implementiert
   - Cloud-Deployment (Fly.io) bereits konfiguriert

7. **Fehlerbehandlung**
   - Zentrale Logging-Infrastruktur
   - Monitoring und Alerting
   - Einfachere Fehlersuche

8. **API-Stabilität**
   - REST API ist sprachunabhängig
   - Frontend kann in beliebiger Technologie sein (React, Vue, Angular)
   - Mobile Apps können dieselbe API nutzen

#### ❌ Contra Frontend

1. **Swiss Ephemeris im Browser**
   - Keine native pyswisseph-Unterstützung
   - Würde WebAssembly-Port erfordern (komplex)
   - Performance schlechter als native C

2. **Große Dateigröße**
   - 30 MB Ephemeris-Dateien
   - Langsamer initialer Load
   - Schlechte UX auf mobilen Verbindungen

3. **CPU-Last**
   - Astronomische Berechnungen blockieren UI
   - Würde Web Workers erfordern (zusätzliche Komplexität)

4. **Zeitzone-Handling**
   - Browser-Zeitzone kann unzuverlässig sein
   - IANA-Datenbank im Browser oft veraltet

5. **Offline-Fähigkeit**
   - Einziger Vorteil: Offline-Berechnungen
   - ABER: Für BaZi nicht kritisch (keine Echtzeit-Anforderung)

### 4.3 Architektur-Empfehlung

```
┌──────────────────────────────────────────────────────────────┐
│ FRONTEND (React/Vue/Angular)                                 │
│ ────────────────────────────────────────────────────────────│
│ • Benutzer-Interface für Input                              │
│ • Datum/Zeit-Picker                                         │
│ • Timezone-Selector (Dropdown)                              │
│ • Koordinaten-Eingabe (oder Map-Picker)                     │
│ • Visualisierung der Vier Säulen                            │
│ • Chart-Darstellung                                         │
│ • Diagnostik-Ansicht (24 Solar Terms)                       │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      │ HTTP/REST (JSON)
                      │
                      ▼
┌──────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI + BaZi Engine)                              │
│ ────────────────────────────────────────────────────────────│
│ • POST /calculate/bazi                                      │
│ • Input-Validierung (Pydantic)                              │
│ • compute_bazi()                                            │
│ • Swiss Ephemeris Berechnungen                              │
│ • Caching (Optional: Redis)                                 │
│ • Response mit FourPillars + Metadata                       │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      │ Ephemeris-Dateien
                      │
                      ▼
┌──────────────────────────────────────────────────────────────┐
│ DATENSCHICHT                                                 │
│ ────────────────────────────────────────────────────────────│
│ • Swiss Ephemeris Files (~30 MB)                            │
│ • Optional: Cache (Redis)                                   │
│ • Optional: Datenbank für User-Charts                       │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 Frontend-Aufgaben

Das Frontend sollte:
1. **Input-Formular** bereitstellen
   - Datetime-Picker (HTML5 oder Library wie react-datepicker)
   - Timezone-Dropdown (mit Suche)
   - Koordinaten-Eingabe oder Map-Integration (z.B. Google Maps API)

2. **API-Calls** durchführen
   ```javascript
   const response = await fetch('/calculate/bazi', {
     method: 'POST',
     headers: {'Content-Type': 'application/json'},
     body: JSON.stringify({
       date: '2024-02-10T14:30:00',
       tz: 'Europe/Berlin',
       lon: 13.4050,
       lat: 52.52,
       standard: 'CIVIL',
       boundary: 'midnight',
       strict: true
     })
   });
   const result = await response.json();
   ```

3. **Visualisierung** der Ergebnisse
   - Vier Säulen in traditionellem Format darstellen
   - Optional: Chart-Diagramm (Canvas/SVG)
   - Solar Terms Timeline

4. **Fehlerbehandlung**
   - Netzwerkfehler
   - Validierungsfehler vom Backend
   - DST-Warnungen anzeigen

### 4.5 Backend-Deployment

Die Engine ist bereits produktionsbereit:
- **Docker:** Dockerfile vorhanden
- **Fly.io:** Konfiguration in `fly.toml`
- **CI/CD:** GitHub Actions für Tests
- **Skalierung:** Auto-scaling konfiguriert

**Deployment-Befehle:**
```bash
# Lokal testen
docker build -t bazi-engine .
docker run -p 8080:8080 bazi-engine

# Deploy zu Fly.io
fly deploy

# Logs überwachen
fly logs
```

### 4.6 Performance-Optimierungen

1. **Caching-Strategie**
   ```python
   # Redis-Cache für häufige Anfragen
   cache_key = f"bazi:{date}:{tz}:{lon}:{lat}:{standard}:{boundary}"
   cached = redis.get(cache_key)
   if cached:
       return json.loads(cached)

   result = compute_bazi(inp)
   redis.setex(cache_key, 3600, json.dumps(result))  # 1h TTL
   ```

2. **Rate Limiting**
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)

   @app.post("/calculate/bazi")
   @limiter.limit("10/minute")
   def calculate_bazi_endpoint(req: BaziRequest):
       ...
   ```

3. **Async Processing (Optional)**
   ```python
   # Für sehr aufwändige Berechnungen
   @app.post("/calculate/bazi/async")
   async def calculate_bazi_async(req: BaziRequest):
       task_id = str(uuid.uuid4())
       background_tasks.add_task(compute_and_cache, task_id, req)
       return {"task_id": task_id, "status": "processing"}

   @app.get("/calculate/bazi/status/{task_id}")
   async def get_status(task_id: str):
       result = redis.get(f"task:{task_id}")
       if result:
           return {"status": "completed", "result": json.loads(result)}
       return {"status": "processing"}
   ```

---

## 5. Zusammenfassung

### Kernmerkmale der Engine
- ✅ **Astronomisch präzise** (Swiss Ephemeris)
- ✅ **DST-sicher** (strikte Validierung)
- ✅ **Flexibel** (CIVIL/LMT, midnight/zi)
- ✅ **Produktionsbereit** (Docker, CI/CD, Cloud-Deployment)
- ✅ **Gut getestet** (Golden Vectors, Invarianten)
- ✅ **Type-Safe** (Python 3.10+ Type Hints)
- ✅ **Erweiterbar** (Protocol-basierte Backends)

### Empfohlene Integration
**BACKEND** - Die Engine sollte als Backend-Service laufen:
- Bessere Performance (native C-Libraries)
- Zentrale Wartung
- Skalierbarkeit
- Caching-Möglichkeiten
- API-Stabilität

### Nächste Schritte für Integration
1. Frontend entwickeln (React/Vue/Angular)
2. API-Client implementieren
3. Visualisierungs-Komponenten erstellen
4. Optional: Caching-Layer hinzufügen
5. Optional: User-Datenbank für gespeicherte Charts
6. Produktions-Deployment konfigurieren
