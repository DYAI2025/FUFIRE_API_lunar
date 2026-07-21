# claudeTest0502 – Vollständige Funktions- und Formatdokumentation BAFE

**Projekt:** BAFE (BaZi-Astrology Fusion Engine)
**Version:** 0.2.0 / API 1.0.0-rc0
**Datum:** 2026-02-06
**Autor:** Claude Opus 4 – automatisierte Codebase-Analyse

---

## Inhaltsverzeichnis

- [1. Projektüberblick & Architektur](#1-projektüberblick--architektur)
- [2. Modulabhängigkeiten](#2-modulabhängigkeiten)
- [3. Datenstrukturen (types.py, constants.py)](#3-datenstrukturen)
- [4. Core-Berechnungsfunktionen](#4-core-berechnungsfunktionen)
  - [4.1 bazi.py – Hauptberechnungs-Engine](#41-bazipy)
  - [4.2 ephemeris.py – Swiss Ephemeris Backend](#42-ephemerispy)
  - [4.3 jieqi.py – Sonnenterm-Berechnungen](#43-jieqipy)
  - [4.4 time_utils.py – Zeitkonvertierung](#44-time_utilspy)
- [5. API-Endpoints & Request/Response-Formate](#5-api-endpoints) *(Iteration 2)*
- [6. Fusion-Modul & Western-Modul](#6-fusion-modul) *(Iteration 2)*
- [7. BAFE-Subpackage (Contract-First Validator)](#7-bafe-subpackage) *(Iteration 3)*
- [8. Verifikation: BaZi-Chart, Ephemeriden, Fusion-Mathematik](#8-verifikation) *(Iteration 3)*
- [9. Testabdeckung & Golden Vectors](#9-testabdeckung) *(Iteration 3)*

---

## 1. Projektüberblick & Architektur

### 1.1 Was ist BAFE?

BAFE ist eine **deterministische astronomische Berechnungs-Engine** für chinesische Astrologie (Vier Säulen des Schicksals / BaZi) kombiniert mit westlicher Astrologie und einem **Fusion-Layer**, der beide Systeme über Wu-Xing-Vektormathematik verbindet.

### 1.2 Kernmerkmale

| Eigenschaft | Beschreibung |
|---|---|
| **Deterministisch** | Keine Zufallselemente, rein astronomische Berechnungen |
| **Immutabel** | Alle Dataclasses mit `frozen=True` |
| **Typsicher** | Vollständige Type-Hint-Abdeckung (Python 3.10+) |
| **Funktional** | Pure Functions ohne Seiteneffekte |
| **Contract-First** | JSON-Schema-Validierung (Draft-07) für `/validate` |
| **Dual-System** | BaZi (östlich) + Western Astrology + Fusion-Layer |

### 1.3 Verzeichnisstruktur

```
BAFE/
├── bazi_engine/                # Hauptpaket
│   ├── __init__.py             # Package-Exporte (Pillar, FourPillars, BaziInput, BaziResult, compute_bazi)
│   ├── types.py                # Datenstrukturen (76 LOC)
│   ├── constants.py            # STEMS, BRANCHES, ANIMALS, DAY_OFFSET (21 LOC)
│   ├── bazi.py                 # Kern-Berechnungs-Pipeline (150 LOC)
│   ├── ephemeris.py            # Swiss Ephemeris Backend + Protocol (110 LOC)
│   ├── jieqi.py                # Sonnenterm-/Jieqi-Berechnungen (99 LOC)
│   ├── time_utils.py           # Zeitparsing/-konvertierung (42 LOC)
│   ├── western.py              # Westliche Astrologie (121 LOC)
│   ├── fusion.py               # Wu-Xing Fusion-Analyse (596 LOC)
│   ├── app.py                  # FastAPI REST API (617 LOC)
│   ├── cli.py                  # Command-Line Interface (67 LOC)
│   └── bafe/                   # Contract-First Validator Subpackage
│       ├── __init__.py          # Exportiert validate_request
│       ├── service.py           # Haupt-Validierungslogik (322 LOC)
│       ├── mapping.py           # Branch-Mapping-Konventionen (131 LOC)
│       ├── kernel.py            # Von-Mises Soft-Kernel (51 LOC)
│       ├── harmonics.py         # Phasor-Harmonik-Features (44 LOC)
│       ├── canonical_json.py    # Deterministische JSON-Serialisierung (75 LOC)
│       ├── refdata.py           # RefData-Evaluierung (278 LOC)
│       ├── time_model.py        # Zeitmodell-Evaluierung (200 LOC)
│       ├── ruleset_loader.py    # Ruleset-Loader (59 LOC)
│       └── errors.py           # Fehlerkatalog (53 LOC)
├── tests/                      # Testsuite
│   ├── conftest.py             # Pfadkonfiguration
│   ├── test_golden.py          # 4 Golden-Vector-Tests
│   ├── test_golden_vectors.py  # 5 erweiterte Vektor-Tests
│   ├── test_invariants.py      # 2 strukturelle Invarianz-Tests
│   ├── test_api.py             # 11 API/Contract-Tests
│   └── test_properties.py      # 4 mathematische Eigenschafts-Tests
├── spec/                       # BaZodiac Spezifikation
│   ├── schemas/                # JSON-Schemas (ValidateRequest, ValidateResponse)
│   ├── rulesets/               # standard_bazi_2026.json
│   ├── refdata/                # RefPack Manifest Template
│   ├── tests/                  # tv_matrix.json (Test-Vektoren)
│   └── addenda/                # Interpretation/Scientific Compliance
├── scripts/                    # GitHub Actions Script
│   └── action_compute.py       # BaZi + Western Berechnung für CI
└── metrics/                    # System-Metriken
    └── system-metrics.json
```

---

## 2. Modulabhängigkeiten

```
Ebene 0:  constants.py                          (keine Abhängigkeiten)
Ebene 1:  types.py                              (← constants.py)
Ebene 2:  ephemeris.py, time_utils.py           (← types.py, swisseph)
Ebene 3:  jieqi.py                              (← ephemeris.py)
Ebene 4:  bazi.py                               (← types, time_utils, ephemeris, jieqi, constants)
Ebene 5:  western.py                            (← ephemeris.py, swisseph)
Ebene 6:  fusion.py                             (← eigenständig, math)
Ebene 7:  app.py                                (← bazi, western, fusion, time_utils, bafe)
          cli.py                                (← types, bazi)
          bafe/service.py                       (← bafe/*, fusion.true_solar_time)
```

**Kritische Regel:** Niedrigere Ebenen dürfen NIEMALS höhere Ebenen importieren (Zirkuläre-Import-Prävention).

---

## 3. Datenstrukturen

### 3.1 Konstanten (`constants.py:1-21`)

| Konstante | Typ | Wert | Beschreibung |
|---|---|---|---|
| `STEMS` | `List[str]` | `["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]` | 10 Himmelsstämme (天干) |
| `BRANCHES` | `List[str]` | `["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]` | 12 Erdzweige (地支) |
| `ANIMALS` | `List[str]` | `["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]` | 12 Tierkreiszeichen |
| `DAY_OFFSET` | `int` | `49` | JDN-Kalibrierungskonstante: `(JDN + 49) % 60` aligniert 1949-10-01 auf Jia-Zi (Index 0) |

### 3.2 Type-Aliase (`types.py:9-12`)

| Alias | Definition | Erlaubte Werte |
|---|---|---|
| `TimeStandard` | `Literal["CIVIL", "LMT"]` | Bürgerliche Zeit oder Local Mean Time |
| `DayBoundary` | `Literal["midnight", "zi"]` | Tagesgrenze: Mitternacht oder Beginn der Zi-Stunde (23:00) |
| `EphemerisBackendName` | `Literal["swisseph", "skyfield"]` | Backend-Auswahl (nur swisseph implementiert) |
| `Fold` | `Literal[0, 1]` | DST-Fold-Parameter für ambige Zeiten |

### 3.3 Pillar (`types.py:14-19`) – frozen dataclass

```python
@dataclass(frozen=True)
class Pillar:
    stem_index: int     # 0-9 → Index in STEMS
    branch_index: int   # 0-11 → Index in BRANCHES
```

| Feld | Typ | Bereich | Beschreibung |
|---|---|---|---|
| `stem_index` | `int` | 0–9 | Jia=0, Yi=1, Bing=2, Ding=3, Wu=4, Ji=5, Geng=6, Xin=7, Ren=8, Gui=9 |
| `branch_index` | `int` | 0–11 | Zi=0, Chou=1, Yin=2, ... Hai=11 |

**`__str__`** gibt `"{Stem}{Branch}"` zurück, z.B. `"JiaChen"`.

### 3.4 FourPillars (`types.py:21-26`) – frozen dataclass

```python
@dataclass(frozen=True)
class FourPillars:
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
```

### 3.5 SolarTerm (`types.py:28-33`) – frozen dataclass

```python
@dataclass(frozen=True)
class SolarTerm:
    index: int              # 0-23, Sonnenterm-Index
    target_lon_deg: float   # Ziel-Sonnenlänge in Grad (0°, 15°, 30°, ... 345°)
    utc_dt: datetime        # UTC-Zeitpunkt des Eintritts
    local_dt: datetime      # Lokaler Zeitpunkt des Eintritts
```

### 3.6 BaziInput (`types.py:35-56`) – frozen dataclass

**Haupteingabe-Datenstruktur für `compute_bazi()`.**

| Feld | Typ | Default | Pflicht | Beschreibung |
|---|---|---|---|---|
| `birth_local` | `str` | — | Ja | ISO 8601 Lokaldatum, z.B. `"2024-02-10T14:30:00"` |
| `timezone` | `str` | — | Ja | IANA Zeitzone, z.B. `"Europe/Berlin"` |
| `longitude_deg` | `float` | — | Ja | Geographische Länge (−180 bis +180) |
| `latitude_deg` | `float` | — | Ja | Geographische Breite (−90 bis +90) |
| `time_standard` | `TimeStandard` | `"CIVIL"` | Nein | `"CIVIL"` oder `"LMT"` |
| `day_boundary` | `DayBoundary` | `"midnight"` | Nein | `"midnight"` oder `"zi"` |
| `ephemeris_backend` | `EphemerisBackendName` | `"swisseph"` | Nein | `"swisseph"` (einziges implementiertes) |
| `accuracy_seconds` | `float` | `1.0` | Nein | Iterationsgenauigkeit in Sekunden |
| `strict_local_time` | `bool` | `True` | Nein | DST-Validierung ein/aus |
| `fold` | `Fold` | `0` | Nein | DST-Fold für ambige Zeiten |
| `ephe_path` | `Optional[str]` | `None` | Nein | Pfad zu Swiss-Ephemeris-Dateien |
| `day_anchor_date_iso` | `Optional[str]` | `None` | Nein | v0.4: Anker-Datum für Tagessäule |
| `day_anchor_pillar_idx` | `Optional[int]` | `None` | Nein | v0.4: Anker-Pillar-Index (0-59) |
| `month_boundary_scheme` | `Literal["jie_only","all_24"]` | `"jie_only"` | Nein | v0.4: Monatsgrenzenmodus |

### 3.7 BaziResult (`types.py:58-75`) – frozen dataclass

**Vollständiges Berechnungsergebnis.**

| Feld | Typ | Beschreibung |
|---|---|---|
| `input` | `BaziInput` | Original-Eingabedaten |
| `pillars` | `FourPillars` | Die vier berechneten Säulen |
| `birth_local_dt` | `datetime` | Geparster lokaler Geburtszeitpunkt (timezone-aware) |
| `birth_utc_dt` | `datetime` | Geburtszeitpunkt in UTC |
| `chart_local_dt` | `datetime` | Chart-lokaler Zeitpunkt (CIVIL oder LMT) |
| `jd_ut` | `float` | Julian Day (Universal Time) |
| `jd_tt` | `float` | Julian Day (Terrestrial Time) |
| `delta_t_seconds` | `float` | ΔT-Korrektur in Sekunden (TT − UT) |
| `lichun_local_dt` | `datetime` | LiChun-Zeitpunkt (Start des Frühlings, 315° Sonnenlänge) |
| `month_boundaries_local_dt` | `Sequence[datetime]` | 13 Monatsgrenzen (Jie-Übergänge) |
| `month_index` | `int` | 0–11, aktueller Monatsindex |
| `solar_terms_local_dt` | `Optional[Sequence[SolarTerm]]` | 24 Sonnenterme (Diagnostik, kann `None` sein) |

---

## 4. Core-Berechnungsfunktionen

### 4.1 bazi.py – Hauptberechnungs-Engine

**Datei:** `bazi_engine/bazi.py` (150 LOC)

#### 4.1.1 `jdn_gregorian(y, m, d)` → `int` (Zeile 14-18)

Berechnet den **Julian Day Number** (JDN) aus einem gregorianischen Datum.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `y` | `int` | Jahr |
| `m` | `int` | Monat (1-12) |
| `d` | `int` | Tag (1-31) |

**Algorithmus:**
```
a = (14 - m) // 12
y2 = y + 4800 - a
m2 = m + 12*a - 3
JDN = d + (153*m2 + 2)//5 + 365*y2 + y2//4 - y2//100 + y2//400 - 32045
```

**Rückgabe:** Integer JDN-Wert.

---

#### 4.1.2 `sexagenary_day_index_from_date(y, m, d, offset=DAY_OFFSET)` → `int` (Zeile 20-21)

Berechnet den **60er-Zyklus-Index des Tages** (sexagenary cycle).

| Parameter | Typ | Default | Beschreibung |
|---|---|---|---|
| `y` | `int` | — | Jahr |
| `m` | `int` | — | Monat |
| `d` | `int` | — | Tag |
| `offset` | `int` | `49` | Kalibrierungs-Offset |

**Formel:** `(jdn_gregorian(y, m, d) + offset) % 60`

**Rückgabe:** Integer 0–59 (Sexagenary-Index).

**Kalibrierung:**
- `1949-10-01` → Index 0 (Jia-Zi, 甲子)
- `1912-02-18` → Index 0 (Jia-Zi)

---

#### 4.1.3 `pillar_from_index60(idx60)` → `Pillar` (Zeile 23-24)

Wandelt einen 60er-Zyklus-Index in ein `Pillar`-Objekt um.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `idx60` | `int` | 0–59, Sexagenary-Index |

**Formel:**
- `stem_index = idx60 % 10`
- `branch_index = idx60 % 12`

---

#### 4.1.4 `year_pillar_from_solar_year(solar_year)` → `Pillar` (Zeile 26-28)

Berechnet die **Jahressäule** aus dem Solarjahr.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `solar_year` | `int` | Solarjahr (nach LiChun-Grenze) |

**Formel:** `idx60 = (solar_year - 1984) % 60`

**Referenzpunkt:** 1984 = Jia-Zi Jahr (甲子年), Index 0.

---

#### 4.1.5 `month_pillar_from_year_stem(year_stem_index, month_index)` → `Pillar` (Zeile 30-33)

Berechnet die **Monatssäule** aus dem Jahresstamm und dem Monatsindex.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `year_stem_index` | `int` | 0–9, Stamm der Jahressäule |
| `month_index` | `int` | 0–11, Monatsindex (0=Yin-Monat nach LiChun) |

**Formeln:**
- `branch_index = (2 + month_index) % 12` → Yin(2) als erster Monat
- `stem_index = (year_stem_index * 2 + 2 + month_index) % 10`

---

#### 4.1.6 `hour_branch_index(dt_local)` → `int` (Zeile 35-36)

Berechnet den **Erdzweig-Index der Stunde** aus einem lokalen Zeitpunkt.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `dt_local` | `datetime` | Lokaler Zeitpunkt |

**Formel:** `((dt_local.hour + 1) // 2) % 12`

**Zuordnung:** Zi(23-01)=0, Chou(01-03)=1, Yin(03-05)=2, ... Hai(21-23)=11

---

#### 4.1.7 `hour_pillar_from_day_stem(day_stem_index, hour_branch)` → `Pillar` (Zeile 38-40)

Berechnet die **Stundensäule** aus dem Tagesstamm und dem Stundenzweig.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `day_stem_index` | `int` | 0–9, Stamm der Tagessäule |
| `hour_branch` | `int` | 0–11, Zweig der Stunde |

**Formel:** `stem_index = (day_stem_index * 2 + hour_branch) % 10`

---

#### 4.1.8 `_lichun_jd_ut_for_year(year, backend)` → `float` (Zeile 42-44)

Berechnet den **Julian Day (UT) von LiChun** (Start des Frühlings, 315° Sonnenlänge) für ein gegebenes Jahr.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `year` | `int` | Kalenderjahr |
| `backend` | `SwissEphBackend` | Ephemeris-Backend |

**Methode:** Ruft `backend.solcross_ut(315.0, jd_start)` auf, wobei `jd_start` der 1. Januar des Jahres ist.

---

#### 4.1.9 `compute_bazi(inp)` → `BaziResult` (Zeile 46-149)

**Hauptfunktion – 9-Schritt-Berechnungspipeline.**

| Parameter | Typ | Beschreibung |
|---|---|---|
| `inp` | `BaziInput` | Vollständige Eingabedaten |

**Pipeline:**

| Schritt | Zeilen | Beschreibung |
|---|---|---|
| 1 | 47-48 | Backend-Prüfung: nur `"swisseph"` implementiert |
| 2 | 50 | `SwissEphBackend` initialisieren |
| 3 | 52-57 | ISO-String parsen → timezone-aware `datetime` (DST-Prüfung) |
| 4 | 58 | Konvertierung zu Chart-Local (CIVIL oder LMT) + UTC |
| 5 | 60-62 | Julian Day (UT), ΔT, Julian Day (TT) berechnen |
| 6 | 64-76 | **Jahressäule**: LiChun-Grenze bestimmen, Solarjahr ableiten |
| 7 | 78-91 | **Monatssäule**: 13 Monatsgrenzen berechnen, Monatsindex finden |
| 8 | 93-107 | **Tagessäule**: JDN + Offset (oder Custom Anchor), Sexagenary-Index |
| 9 | 109-113 | **Stundensäule**: Stundenzweig + Tagesstamm-Ableitung |

**LiChun-Logik (Schritt 6, Zeile 64-76):**
```python
if chart_local_dt < lichun_this_local:
    solar_year = y - 1          # Geburt VOR LiChun → Vorjahr
else:
    solar_year = y              # Geburt NACH LiChun → aktuelles Jahr
```

**Custom Day Anchor (Schritt 8, Zeile 94-103):**
```python
if inp.day_anchor_date_iso and inp.day_anchor_pillar_idx is not None:
    calculated_offset = (inp.day_anchor_pillar_idx - anchor_jdn) % 60
else:
    calculated_offset = DAY_OFFSET  # Standard: 49
```

**Diagnostik (Zeile 116-134):** Berechnung der 24 Sonnenterme im try-catch – Fehler blockiert nicht die Hauptberechnung.

**Rückgabe:** Vollständiges `BaziResult`-Objekt.

---

### 4.2 ephemeris.py – Swiss Ephemeris Backend

**Datei:** `bazi_engine/ephemeris.py` (110 LOC)

#### 4.2.1 Hilfsfunktionen

| Funktion | Zeile | Signatur | Beschreibung |
|---|---|---|---|
| `norm360(deg)` | 12-16 | `float → float` | Normalisiert Grad auf [0, 360) |
| `wrap180(deg)` | 18-19 | `float → float` | Normalisiert Grad auf (-180, +180] |

#### 4.2.2 `EphemerisBackend` Protocol (Zeile 21-25)

Interface für austauschbare Ephemeris-Backends.

| Methode | Signatur | Beschreibung |
|---|---|---|
| `delta_t_seconds(jd_ut)` | `float → float` | ΔT in Sekunden |
| `jd_tt_from_jd_ut(jd_ut)` | `float → float` | JD(TT) aus JD(UT) |
| `sun_lon_deg_ut(jd_ut)` | `float → float` | Sonnenlänge in Grad |
| `solcross_ut(target, jd_start)` | `(float, float) → Optional[float]` | Sonnenlängen-Überquerung |

#### 4.2.3 `SwissEphBackend` (Zeile 27-47) – frozen dataclass

Implementiert `EphemerisBackend` mit der Swiss Ephemeris Bibliothek (pyswisseph).

| Feld | Typ | Default | Beschreibung |
|---|---|---|---|
| `flags` | `int` | `swe.FLG_SWIEPH` | Swiss Ephemeris Flags |
| `ephe_path` | `Optional[str]` | `None` | Pfad zu Ephemeris-Dateien |

**Methoden:**

| Methode | Zeile | Implementierung |
|---|---|---|
| `delta_t_seconds(jd_ut)` | 36-37 | `swe.deltat(jd_ut) * 86400.0` |
| `jd_tt_from_jd_ut(jd_ut)` | 39-40 | `jd_ut + swe.deltat(jd_ut)` |
| `sun_lon_deg_ut(jd_ut)` | 42-44 | `swe.calc_ut(jd_ut, swe.SUN, flags)` → normalisiert auf [0,360) |
| `solcross_ut(target, jd_start)` | 46-47 | `swe.solcross_ut(target, jd_start, flags)` |

**`__post_init__`** (Zeile 32-34): Löst Ephemeris-Pfad auf und ruft `swe.set_ephe_path()` auf.

#### 4.2.4 `datetime_utc_to_jd_ut(dt_utc)` → `float` (Zeile 49-53)

Konvertiert ein UTC-`datetime` in einen Julian Day (UT).

| Parameter | Typ | Bedingung |
|---|---|---|
| `dt_utc` | `datetime` | Muss timezone-aware UTC sein |

**Fehler:** `ValueError` wenn nicht UTC.

#### 4.2.5 `jd_ut_to_datetime_utc(jd_ut)` → `datetime` (Zeile 55-73)

Konvertiert einen Julian Day (UT) zurück in ein UTC-`datetime`.

**Behandelt Überläufe** bei Sekunden/Minuten/Stunden korrekt (Zeile 63-71).

#### 4.2.6 `ensure_ephemeris_files(ephe_path)` → `str` (Zeile 92-109)

Stellt sicher, dass Swiss Ephemeris Dateien vorhanden sind.

**Erforderliche Dateien:**
- `sepl_18.se1` (Planeten-Ephemeris 1800-2400 AD)
- `semo_18.se1` (Mond-Ephemeris)
- `seas_18.se1` (Asteroiden-Ephemeris)
- `seplm06.se1` (Ergänzende Ephemeris)

**Pfadauflösung:**
1. Expliziter `ephe_path` Parameter
2. Umgebungsvariable `SE_EPHE_PATH`
3. Fallback: `~/.cache/bazi_engine/swisseph`

**Sicherheit:** Lädt NIEMALS Dateien aus dem Netz herunter. Wirft `FileNotFoundError` bei fehlenden Dateien.

---

### 4.3 jieqi.py – Sonnenterm-Berechnungen

**Datei:** `bazi_engine/jieqi.py` (99 LOC)

#### 4.3.1 Konstante

```python
SOLAR_TERM_TARGETS_DEG = [0.0, 15.0, 30.0, ... 345.0]  # 24 Sonnentermen in Grad
```

#### 4.3.2 `_bisection_crossing(backend, target_lon_deg, jd_lo, jd_hi, accuracy_seconds, max_iter=80)` → `float` (Zeile 9-40)

**Interner Bisektions-Algorithmus** zum Finden eines Sonnenlängen-Übergangs.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `backend` | `EphemerisBackend` | Ephemeris-Backend |
| `target_lon_deg` | `float` | Ziellänge in Grad |
| `jd_lo` | `float` | Untere JD-Grenze |
| `jd_hi` | `float` | Obere JD-Grenze |
| `accuracy_seconds` | `float` | Zielgenauigkeit in Sekunden |
| `max_iter` | `int` | Maximale Iterationen (Default: 80) |

**Algorithmus:**
1. Berechne `f(jd) = wrap180(sun_lon(jd) - target)` an beiden Grenzen
2. Prüfe Vorzeichenwechsel (Interval-Bracketing)
3. Bisektiere bis `|hi - lo| ≤ accuracy_seconds / 86400`
4. Toleranz: `tol_days = accuracy_seconds / 86400.0`

**Fehler:** `ValueError` wenn kein Root im Interval.

#### 4.3.3 `find_crossing(backend, target_lon_deg, jd_start_ut, *, accuracy_seconds, max_span_days=40.0)` → `float` (Zeile 42-68)

**Universelle Sonnenlängen-Überquerungsfunktion.**

| Parameter | Typ | Default | Beschreibung |
|---|---|---|---|
| `backend` | `EphemerisBackend` | — | Ephemeris-Backend |
| `target_lon_deg` | `float` | — | Ziel-Sonnenlänge |
| `jd_start_ut` | `float` | — | Startpunkt (JD UT) |
| `accuracy_seconds` | `float` | — | Genauigkeit |
| `max_span_days` | `float` | `40.0` | Max. Suchfenster in Tagen |

**Strategie:**
1. **Primär:** `backend.solcross_ut()` → direkte Swiss-Ephemeris-Lösung
2. **Fallback:** Stepping (1 Tag) + Bisection bei Vorzeichenwechsel

#### 4.3.4 `compute_month_boundaries_from_lichun(backend, jd_lichun_ut, *, accuracy_seconds)` → `List[float]` (Zeile 70-83)

Berechnet **13 Monatsgrenzen** (Jie-Übergänge) ab LiChun.

| Index | Sonnenlänge | Jie-Name |
|---|---|---|
| 0 | 315° | LiChun (Frühlingsbeginn) |
| 1 | 345° | JingZhe (Erwachen der Insekten) |
| 2 | 15° | QingMing (Klares und Helles) |
| 3 | 45° | LiXia (Sommerbeginn) |
| ... | +30° je Schritt | ... |
| 12 | 315° + 360° | Nächster LiChun |

**Rückgabe:** Liste von 13 JD(UT)-Werten, streng aufsteigend.

#### 4.3.5 `compute_24_solar_terms_for_window(backend, jd_start_ut, jd_end_ut, *, accuracy_seconds)` → `List[Tuple[int, float]]` (Zeile 85-98)

Berechnet alle **24 Sonnenterme** innerhalb eines Zeitfensters.

**Rückgabe:** Liste von `(index, jd_ut)` Tupeln, sortiert nach JD.

---

### 4.4 time_utils.py – Zeitkonvertierung

**Datei:** `bazi_engine/time_utils.py` (42 LOC)

#### 4.4.1 `LocalTimeError` (Zeile 7-8)

Exception für ungültige lokale Zeiten (DST-Lücken, ambige Zeiten).

#### 4.4.2 `parse_local_iso(birth_local_iso, tz_name, *, strict, fold)` → `datetime` (Zeile 10-27)

Parst einen ISO-8601-String und macht ihn timezone-aware.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `birth_local_iso` | `str` | ISO-8601-Zeitstring |
| `tz_name` | `str` | IANA Zeitzone |
| `strict` | `bool` | Strikte DST-Validierung |
| `fold` | `int` | 0 oder 1 für ambige Zeiten |

**Strikter Modus:** Führt einen Round-Trip-Check durch (lokal → UTC → lokal). Wirft `LocalTimeError` wenn das Ergebnis abweicht (z.B. bei Spring-Forward-Lücken).

#### 4.4.3 `lmt_tzinfo(longitude_deg)` → `timezone` (Zeile 29-30)

Erzeugt ein `timezone`-Objekt für **Local Mean Time** basierend auf Längengrad.

**Formel:** `offset_seconds = longitude_deg × 240.0` (4 Minuten pro Grad)

#### 4.4.4 `to_chart_local(birth_local, longitude_deg, time_standard)` → `Tuple[datetime, datetime]` (Zeile 32-36)

Konvertiert den lokalen Geburtszeitpunkt in Chart-Local-Time.

| `time_standard` | Verhalten |
|---|---|
| `"CIVIL"` | Gibt `birth_local` und `birth_utc` zurück |
| `"LMT"` | Konvertiert UTC → LMT-Zeitzone basierend auf Längengrad |

**Rückgabe:** `(chart_local_dt, birth_utc_dt)`

#### 4.4.5 `apply_day_boundary(dt_local, day_boundary)` → `datetime` (Zeile 38-41)

Verschiebt den Zeitpunkt bei Zi-Tagesgrenze.

| `day_boundary` | Verhalten |
|---|---|
| `"midnight"` | Keine Änderung |
| `"zi"` | Addiert +1 Stunde (verschiebt 23:00-00:00 zum nächsten Tag) |

---

## 5. API-Endpoints & Request/Response-Formate

**Datei:** `bazi_engine/app.py` (617 LOC)
**Framework:** FastAPI mit Pydantic-Modellen
**Base-URL:** `http://localhost:8080`

### 5.1 Übersicht aller Endpoints

| Methode | Pfad | Beschreibung | Auth |
|---|---|---|---|
| `GET` | `/` | Root/Status | Nein |
| `GET` | `/health` | Health-Check | Nein |
| `GET` | `/api` | Sternzeichen-Abfrage (DE) | Nein |
| `GET` | `/info/wuxing-mapping` | Wu-Xing-Zuordnungstabelle | Nein |
| `POST` | `/calculate/bazi` | BaZi-Chart Berechnung | Nein |
| `POST` | `/calculate/western` | Westlicher Astrologie-Chart | Nein |
| `POST` | `/calculate/fusion` | Fusion-Analyse (Ost+West) | Nein |
| `POST` | `/calculate/wuxing` | Wu-Xing-Elementvektor | Nein |
| `POST` | `/calculate/tst` | True Solar Time Berechnung | Nein |
| `POST` | `/validate` | Contract-First Validierung | Nein |
| `POST` | `/api/webhooks/chart` | ElevenLabs Webhook | Ja (HMAC/API-Key/Bearer) |

---

### 5.2 `GET /` – Root-Status (Zeile 131-133)

**Response:**
```json
{
  "status": "ok",
  "service": "bazi_engine_v2",
  "version": "0.2.0"
}
```

### 5.3 `GET /health` – Health-Check (Zeile 135-137)

**Response:**
```json
{
  "status": "healthy"
}
```

---

### 5.4 `POST /calculate/bazi` – BaZi-Chart Berechnung (Zeile 196-237)

#### Request-Format (`BaziRequest`, Zeile 99-107)

```json
{
  "date": "2024-02-10T14:30:00",    // Pflicht: ISO 8601 lokale Zeit
  "tz": "Europe/Berlin",             // Optional, Default: "Europe/Berlin"
  "lon": 13.4050,                    // Optional, Default: 13.4050
  "lat": 52.52,                      // Optional, Default: 52.52
  "standard": "CIVIL",               // Optional: "CIVIL" | "LMT"
  "boundary": "midnight",            // Optional: "midnight" | "zi"
  "strict": true                     // Optional: DST-Validierung
}
```

| Feld | Typ | Pflicht | Default | Beschreibung |
|---|---|---|---|---|
| `date` | `str` | Ja | — | ISO 8601 Lokaldatum, z.B. `"2024-02-10T14:30:00"` |
| `tz` | `str` | Nein | `"Europe/Berlin"` | IANA Zeitzone |
| `lon` | `float` | Nein | `13.4050` | Geographische Länge |
| `lat` | `float` | Nein | `52.52` | Geographische Breite |
| `standard` | `str` | Nein | `"CIVIL"` | `"CIVIL"` oder `"LMT"` |
| `boundary` | `str` | Nein | `"midnight"` | `"midnight"` oder `"zi"` |
| `strict` | `bool` | Nein | `true` | DST-Striktmodus |

#### Response-Format

```json
{
  "input": {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
    "standard": "CIVIL",
    "boundary": "midnight",
    "strict": true
  },
  "pillars": {
    "year":  { "stamm": "Jia",  "zweig": "Chen", "tier": "Drache", "element": "Holz" },
    "month": { "stamm": "Bing", "zweig": "Yin",  "tier": "Tiger",  "element": "Feuer" },
    "day":   { "stamm": "Jia",  "zweig": "Chen", "tier": "Drache", "element": "Holz" },
    "hour":  { "stamm": "Xin",  "zweig": "Wei",  "tier": "Ziege",  "element": "Metall" }
  },
  "chinese": {
    "year": {
      "stem": "Jia",
      "branch": "Chen",
      "animal": "Dragon"
    },
    "month_master": "Bing",
    "day_master": "Jia",
    "hour_master": "Xin"
  },
  "dates": {
    "birth_local": "2024-02-10T14:30:00+01:00",
    "birth_utc": "2024-02-10T13:30:00+00:00",
    "lichun_local": "2024-02-04T09:27:00+01:00"
  },
  "solar_terms_count": 24
}
```

**Pillar-Formatierung** (`format_pillar()`, Zeile 88-96):

| Feld | Quelle | Beschreibung |
|---|---|---|
| `stamm` | `STEMS[pillar.stem_index]` | Chinesischer Himmelsstamm |
| `zweig` | `BRANCHES[pillar.branch_index]` | Chinesischer Erdzweig |
| `tier` | `BRANCH_TO_ANIMAL[branch]` | Deutsches Tierkreiszeichen |
| `element` | `STEM_TO_ELEMENT[stem]` | Deutsches Wu-Xing-Element |

**Element-Zuordnung** (`STEM_TO_ELEMENT`, Zeile 59-70):

| Stämme | Element (DE) |
|---|---|
| Jia, Yi | Holz |
| Bing, Ding | Feuer |
| Wu, Ji | Erde |
| Geng, Xin | Metall |
| Ren, Gui | Wasser |

**Fehler:** HTTP 400 mit `{"detail": "..."}`.

---

### 5.5 `POST /calculate/western` – Westlicher Chart (Zeile 239-250)

#### Request-Format (`WesternRequest`, Zeile 125-129)

```json
{
  "date": "2024-02-10T14:30:00",
  "tz": "Europe/Berlin",
  "lon": 13.4050,
  "lat": 52.52
}
```

#### Response-Format (`WesternChartResponse`)

```json
{
  "jd_ut": 2460351.0625,
  "house_system": "P",
  "bodies": {
    "Sun": {
      "longitude": 321.5,
      "latitude": 0.0,
      "distance": 0.987,
      "speed": 1.013,
      "is_retrograde": false,
      "zodiac_sign": 10,
      "degree_in_sign": 21.5
    },
    "Moon": { ... },
    "Mercury": { ... },
    "Venus": { ... },
    "Mars": { ... },
    "Jupiter": { ... },
    "Saturn": { ... },
    "Uranus": { ... },
    "Neptune": { ... },
    "Pluto": { ... },
    "Chiron": { ... },
    "Lilith": { ... },
    "NorthNode": { ... },
    "TrueNorthNode": { ... }
  },
  "houses": {
    "1": 120.5,
    "2": 150.3,
    ...
    "12": 90.2
  },
  "angles": {
    "Ascendant": 120.5,
    "MC": 210.3,
    "Vertex": 45.2
  }
}
```

**Zodiac-Sign-Index:** `int(longitude // 30)` → 0=Widder, 1=Stier, ..., 11=Fische

**Häusersystem-Fallback** (Zeile 76-96):
1. Placidus (`P`) – Standard
2. Porphyry (`O`) – Fallback für hohe Breitengrade
3. Whole Sign (`W`) – Immer funktionsfähig

---

### 5.6 `POST /calculate/fusion` – Fusion-Analyse (Zeile 274-320)

#### Request-Format (`FusionRequest`, Zeile 256-264)

```json
{
  "date": "2024-02-10T14:30:00",
  "tz": "Europe/Berlin",
  "lon": 13.4050,
  "lat": 52.52,
  "bazi_pillars": {
    "year":  { "stamm": "Jia",  "zweig": "Chen" },
    "month": { "stamm": "Bing", "zweig": "Yin" },
    "day":   { "stamm": "Jia",  "zweig": "Chen" },
    "hour":  { "stamm": "Xin",  "zweig": "Wei" }
  }
}
```

| Feld | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `date` | `str` | Ja | ISO 8601 lokale Zeit |
| `tz` | `str` | Nein | IANA Zeitzone (Default: Europe/Berlin) |
| `lon` | `float` | Ja | Geographische Länge |
| `lat` | `float` | Ja | Geographische Breite |
| `bazi_pillars` | `Dict` | Ja | BaZi-Säulen aus `/calculate/bazi` |

#### Response-Format (`FusionResponse`, Zeile 266-272)

```json
{
  "input": { "date": "...", "tz": "...", "lon": 13.405, "lat": 52.52 },
  "wu_xing_vectors": {
    "western_planets": { "Holz": 0.42, "Feuer": 0.55, "Erde": 0.31, "Metall": 0.22, "Wasser": 0.60 },
    "bazi_pillars":    { "Holz": 0.35, "Feuer": 0.28, "Erde": 0.50, "Metall": 0.22, "Wasser": 0.30 }
  },
  "harmony_index": {
    "harmony_index": 0.7234,
    "interpretation": "Gute Harmonie - Die Energien unterstützen sich gegenseitig",
    "method": "dot_product",
    "western_vector": { ... },
    "bazi_vector": { ... }
  },
  "elemental_comparison": {
    "Holz":   { "western": 0.420, "bazi": 0.350, "difference": 0.070 },
    "Feuer":  { "western": 0.550, "bazi": 0.280, "difference": 0.270 },
    "Erde":   { "western": 0.310, "bazi": 0.500, "difference": -0.190 },
    "Metall": { "western": 0.220, "bazi": 0.220, "difference": 0.000 },
    "Wasser": { "western": 0.600, "bazi": 0.300, "difference": 0.300 }
  },
  "cosmic_state": 0.7234,
  "fusion_interpretation": "Harmonie-Index: 72.34%\nGute Harmonie...\n\nWestliche Dominanz: Wasser\nÖstliche Dominanz: Erde\n..."
}
```

---

### 5.7 `POST /calculate/wuxing` – Wu-Xing-Elementvektor (Zeile 335-375)

#### Request-Format (`WxRequest`, Zeile 322-327)

```json
{
  "date": "2024-02-10T14:30:00",
  "tz": "Europe/Berlin",
  "lon": 13.4050,
  "lat": 52.52
}
```

#### Response-Format (`WxResponse`, Zeile 328-333)

```json
{
  "input": { "date": "...", "tz": "...", "lon": 13.405, "lat": 52.52 },
  "wu_xing_vector": { "Holz": 0.42, "Feuer": 0.55, "Erde": 0.31, "Metall": 0.22, "Wasser": 0.60 },
  "dominant_element": "Wasser",
  "equation_of_time": -14.12,
  "true_solar_time": 14.3847
}
```

---

### 5.8 `POST /calculate/tst` – True Solar Time (Zeile 390-438)

#### Request-Format (`TSTRequest`, Zeile 377-380)

```json
{
  "date": "2024-02-10T14:30:00",
  "tz": "Europe/Berlin",
  "lon": 13.4050
}
```

#### Response-Format (`TSTResponse`, Zeile 382-388)

```json
{
  "input": { "date": "...", "tz": "...", "lon": 13.405 },
  "civil_time_hours": 14.5,
  "longitude_correction_hours": 0.8937,
  "equation_of_time_hours": -0.2353,
  "true_solar_time_hours": 15.1584,
  "true_solar_time_formatted": "15:09"
}
```

**Berechnungsformel (Zeile 411-418):**
```
Δt_lon = longitude × 4 / 60          (4 Minuten pro Grad)
E_t    = equation_of_time(day) / 60   (Minuten → Stunden)
TST    = civil_time + Δt_lon + E_t
TST    = TST mod 24
```

---

### 5.9 `GET /api` – Sternzeichen-Abfrage (Zeile 153-194)

**Query-Parameter:**

| Parameter | Typ | Pflicht | Default | Beschreibung |
|---|---|---|---|---|
| `datum` | `str` | Ja | — | Datum `YYYY-MM-DD` |
| `zeit` | `str` | Ja | — | Zeit `HH:MM[:SS]` |
| `ort` | `str` | Nein | `None` | `"lat,lon"` oder freier Text |
| `tz` | `str` | Nein | `"Europe/Berlin"` | Zeitzone |
| `lon` | `float` | Nein | `13.4050` | Längengrad |
| `lat` | `float` | Nein | `52.52` | Breitengrad |

**Beispiel-Aufruf:**
```
GET /api?datum=2024-02-10&zeit=14:30&tz=Europe/Berlin
```

**Response:**
```json
{
  "sonne": "Wassermann",
  "input": {
    "datum": "2024-02-10",
    "zeit": "14:30",
    "ort": null,
    "tz": "Europe/Berlin",
    "lat": 52.52,
    "lon": 13.405
  }
}
```

**Deutsche Tierkreiszeichen** (`ZODIAC_SIGNS_DE`, Zeile 44-57):
`["Widder", "Stier", "Zwillinge", "Krebs", "Löwe", "Jungfrau", "Waage", "Skorpion", "Schütze", "Steinbock", "Wassermann", "Fische"]`

---

### 5.10 `GET /info/wuxing-mapping` – Elementzuordnung (Zeile 440-452)

**Response:**
```json
{
  "mapping": {
    "Sun": "Feuer",
    "Moon": "Wasser",
    "Mercury": ["Erde", "Metall"],
    "Venus": "Metall",
    "Mars": "Feuer",
    "Jupiter": "Holz",
    "Saturn": "Erde",
    "Uranus": "Holz",
    "Neptune": "Wasser",
    "Pluto": "Feuer",
    "Chiron": "Wasser",
    "Lilith": "Wasser",
    "NorthNode": "Holz",
    "TrueNorthNode": "Holz"
  },
  "order": ["Holz", "Feuer", "Erde", "Metall", "Wasser"],
  "description": {
    "PLANET_TO_WUXING": "Western planet to Chinese element mapping",
    "WUXING_ORDER": "Wu Xing cycle order: Holz -> Feuer -> Erde -> Metall -> Wasser"
  }
}
```

---

### 5.11 `POST /validate` – Contract-First Validierung (Zeile 140-150)

Delegiert an `bafe.validate_request()`. Detaillierte Dokumentation in Iteration 3 (BAFE-Subpackage).

**Fehler:** HTTP 422 (Schema-Verletzung) oder HTTP 500 (interner Fehler).

---

### 5.12 `POST /api/webhooks/chart` – ElevenLabs Webhook (Zeile 501-611)

#### Authentifizierung (3 Methoden, Zeile 522-538)

| Methode | Header | Format |
|---|---|---|
| HMAC-Signatur | `elevenlabs-signature` | `t=<timestamp>,v1=<sha256>` |
| API-Key | `x-api-key` | Plain-Text Secret |
| Bearer Token | `Authorization` | `Bearer <secret>` |

**Umgebungsvariable:** `ELEVENLABS_TOOL_SECRET` (Pflicht)

#### Request-Format (`ElevenLabsChartRequest`, Zeile 459-461)

```json
{
  "birthDate": "1990-05-15",
  "birthTime": "14:30"
}
```

| Feld | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `birthDate` | `str` | Ja | `YYYY-MM-DD` |
| `birthTime` | `str` | Nein | `HH:MM`, Default: `"12:00"` |

#### Response-Format

```json
{
  "western": {
    "sunSign": "Stier",
    "moonSign": "Krebs",
    "sunSignEnglish": "Taurus"
  },
  "eastern": {
    "yearAnimal": "Pferd",
    "yearElement": "Metall",
    "monthAnimal": "Schlange",
    "dayAnimal": "Tiger",
    "dayElement": "Holz",
    "dayMaster": "Jia"
  },
  "summary": {
    "sternzeichen": "Stier",
    "chinesischesZeichen": "Metall Pferd",
    "tagesmeister": "Holz (Jia)"
  }
}
```

**Standard-Location:** Berlin (lat=52.52, lon=13.405, tz=Europe/Berlin).

---

## 6. Fusion-Modul & Western-Modul

### 6.1 Western-Modul (`western.py`, 121 LOC)

#### 6.1.1 Berechnete Himmelskörper

| Name | Swiss-Eph-Konstante | Beschreibung |
|---|---|---|
| `Sun` | `swe.SUN` | Sonne |
| `Moon` | `swe.MOON` | Mond |
| `Mercury` | `swe.MERCURY` | Merkur |
| `Venus` | `swe.VENUS` | Venus |
| `Mars` | `swe.MARS` | Mars |
| `Jupiter` | `swe.JUPITER` | Jupiter |
| `Saturn` | `swe.SATURN` | Saturn |
| `Uranus` | `swe.URANUS` | Uranus |
| `Neptune` | `swe.NEPTUNE` | Neptun |
| `Pluto` | `swe.PLUTO` | Pluto |
| `Chiron` | `swe.CHIRON` | Chiron |
| `Lilith` | `swe.MEAN_APOG` | Mittlere Lilith |
| `NorthNode` | `swe.MEAN_NODE` | Mittlerer Mondknoten |
| `TrueNorthNode` | `swe.TRUE_NODE` | Wahrer Mondknoten |

#### 6.1.2 `compute_western_chart(birth_utc_dt, lat, lon, alt=0.0, ephe_path=None)` → `Dict` (Zeile 35-120)

| Parameter | Typ | Default | Beschreibung |
|---|---|---|---|
| `birth_utc_dt` | `datetime` | — | UTC-Geburtszeitpunkt |
| `lat` | `float` | — | Breitengrad |
| `lon` | `float` | — | Längengrad |
| `alt` | `float` | `0.0` | Höhe in Metern |
| `ephe_path` | `str` | `None` | Ephemeris-Pfad |

**Berechnung pro Planet (Zeile 56-69):**
```python
(lon_deg, lat_deg, dist, speed_lon, _, _), ret = swe.calc_ut(jd_ut, pid, flags)
```

**Flags:** `swe.FLG_SWIEPH | swe.FLG_SPEED` (Swiss Ephemeris + Geschwindigkeiten)

**Retrograd-Erkennung:** `speed_lon < 0`

**Tierkreiszeichen:** `int(longitude // 30)` (0=Aries, ..., 11=Pisces)

---

### 6.2 Fusion-Modul (`fusion.py`, 596 LOC)

#### 6.2.1 Planet-zu-Wu-Xing-Zuordnung (`PLANET_TO_WUXING`, Zeile 15-30)

| Planet | Wu Xing | Begründung |
|---|---|---|
| Sun | Feuer | Vitalität, Lebenskraft |
| Moon | Wasser | Emotionen, Intuition |
| Mercury | [Erde, Metall] | **Dual:** Tag=Erde, Nacht=Metall |
| Venus | Metall | Schönheit, Wert, Form |
| Mars | Feuer | Aktion, Energie |
| Jupiter | Holz | Wachstum, Expansion |
| Saturn | Erde | Struktur, Grenzen |
| Uranus | Holz | Innovation |
| Neptune | Wasser | Träume, Spiritualität |
| Pluto | Feuer | Transformation |
| Chiron | Wasser | Heilung |
| Lilith | Wasser | Instinkte |
| NorthNode | Holz | Wachstumspfad |

**Besonderheit Mercury:** Tag/Nacht-abhängige Zuordnung (`is_night` Parameter).

#### 6.2.2 `WuXingVector` Klasse (Zeile 40-74)

5-dimensionaler Vektor für Wu-Xing-Elementverteilung.

| Feld | Typ | Beschreibung |
|---|---|---|
| `holz` | `float` | Holz-Anteil |
| `feuer` | `float` | Feuer-Anteil |
| `erde` | `float` | Erde-Anteil |
| `metall` | `float` | Metall-Anteil |
| `wasser` | `float` | Wasser-Anteil |

**Methoden:**

| Methode | Beschreibung |
|---|---|
| `to_list()` | → `[holz, feuer, erde, metall, wasser]` |
| `to_dict()` | → `{"Holz": ..., "Feuer": ..., ...}` |
| `magnitude()` | L2-Norm: `√(Σ xᵢ²)` |
| `normalize()` | Einheitsvektor: `v / ‖v‖` |
| `zero()` | Statisch: Nullvektor |

#### 6.2.3 `calculate_wuxing_vector_from_planets(bodies, use_retrograde_weight=True)` → `WuXingVector` (Zeile 101-146)

Berechnet den Wu-Xing-Vektor aus westlichen Planetenpositionen.

**Gewichtung:**
- Normaler Planet: `weight = 1.0`
- Retrograder Planet: `weight = 1.3` (+30% stärkerer Einfluss)

**Nacht-Chart-Erkennung:** Via `is_night_chart()` – beeinflusst Mercury-Zuordnung.

#### 6.2.4 `is_night_chart(sun_longitude, ascendant=None)` → `bool` (Zeile 149-180)

| Modus | Bedingung | Beschreibung |
|---|---|---|
| Mit Aszendent | Sonne zwischen DSC und ASC | Astronomisch korrekt |
| Ohne Aszendent | `return False` | Fallback: immer Tag-Chart |

#### 6.2.5 `calculate_wuxing_from_bazi(pillars)` → `WuXingVector` (Zeile 183-245)

Extrahiert Wu-Xing-Vektor aus BaZi-Säulen mit **Hidden Stems (藏干)**.

**Gewichtung der Hidden Stems:**

| Qi-Typ | Gewicht | Beschreibung |
|---|---|---|
| 主气 (Haupt-Qi) | 1.0 | Hauptelement des Zweigs |
| 中气 (Mittel-Qi) | 0.5 | Mittleres verstecktes Element |
| 余气 (Rest-Qi) | 0.3 | Restliches verstecktes Element |

**Beispiel Yin (寅):** Holz 1.0, Feuer 0.5, Erde 0.3

**Vollständige Hidden-Stems-Tabelle** (Zeile 210-223):

| Zweig | 主气 | 中气 | 余气 |
|---|---|---|---|
| Zi (子) | Wasser 1.0 | — | — |
| Chou (丑) | Erde 1.0 | Wasser 0.5 | Metall 0.3 |
| Yin (寅) | Holz 1.0 | Feuer 0.5 | Erde 0.3 |
| Mao (卯) | Holz 1.0 | — | — |
| Chen (辰) | Erde 1.0 | Holz 0.5 | Wasser 0.3 |
| Si (巳) | Feuer 1.0 | Metall 0.5 | Erde 0.3 |
| Wu (午) | Feuer 1.0 | Erde 0.5 | — |
| Wei (未) | Erde 1.0 | Feuer 0.5 | Holz 0.3 |
| Shen (申) | Metall 1.0 | Wasser 0.5 | Erde 0.3 |
| You (酉) | Metall 1.0 | — | — |
| Xu (戌) | Erde 1.0 | Metall 0.5 | Feuer 0.3 |
| Hai (亥) | Wasser 1.0 | Holz 0.5 | — |

#### 6.2.6 `calculate_harmony_index(western_vector, bazi_vector, method="dot_product")` → `Dict` (Zeile 248-294)

**Harmony-Index:** Quantifiziert die Übereinstimmung zwischen westlicher und östlicher Elementverteilung.

| Methode | Formel | Bereich |
|---|---|---|
| `"dot_product"` | `Σ(w_norm_i × b_norm_i)`, clamped ≥ 0 | [0, 1] |
| `"cosine"` | `(w·b) / (‖w‖ × ‖b‖)` | [-1, 1] |

**Interpretation** (`interpret_harmony()`, Zeile 297-308):

| Bereich | Interpretation (DE) |
|---|---|
| ≥ 0.8 | Starke Resonanz – Perfekte Harmonie |
| ≥ 0.6 | Gute Harmonie – Gegenseitige Unterstützung |
| ≥ 0.4 | Moderate Balance – Unterschiedliche Schwerpunkte |
| ≥ 0.2 | Gespannte Harmonie – Teils komplementär |
| < 0.2 | Divergenz – Unterschiedliche Richtungen |

#### 6.2.7 `equation_of_time(day_of_year, use_precise=True)` → `float` (Zeile 315-362)

**Zeitgleichung** – Differenz zwischen wahrer Sonnenzeit und mittlerer Sonnenzeit.

| Modus | Formel | Genauigkeit |
|---|---|---|
| `use_precise=True` | NOAA Fourier-Reihe | ±0.5 Minuten |
| `use_precise=False` | Vereinfacht: `9.87·sin(2B) - 7.53·cos(B) - 1.5·sin(B)` | ±2 Minuten |

**Präzise Formel (Zeile 342-352):**
```
γ = 2π × (day_of_year - 1) / 365
E = 229.18 × (0.000075 + 0.001868·cos(γ) - 0.032077·sin(γ)
              - 0.014615·cos(2γ) - 0.040849·sin(2γ))
```

**Rückgabe:** Minuten (positiv oder negativ), Bereich ca. −14.2 bis +16.4.

#### 6.2.8 `true_solar_time(civil_time_hours, longitude_deg, day_of_year, timezone_offset_hours=None)` → `float` (Zeile 365-424)

**True Solar Time (TST)** – Astronomisch korrekte Sonnenzeit.

**Formel mit Timezone:**
```
UTC = civil_time - timezone_offset
LMT = UTC + (longitude / 15)
TST = LMT + E_t
```

**Formel ohne Timezone (LMT-Input):**
```
TST = civil_time + E_t
```

#### 6.2.9 `true_solar_time_from_civil(civil_time_hours, longitude_deg, day_of_year, standard_meridian_deg=None)` → `float` (Zeile 427-477)

Alternative TST-Berechnung mit **Standard-Meridian-Korrektur**.

**Formel:**
```
TST = civil_time + 4×(standard_meridian - longitude)/60 + E_t
```

**Standard-Meridian-Schätzung:** `round(longitude / 15) × 15`

#### 6.2.10 `compute_fusion_analysis(birth_utc_dt, latitude, longitude, bazi_pillars, western_bodies)` → `Dict` (Zeile 484-549)

**Hauptfunktion der Fusion-Analyse.** Kombiniert alle Teilberechnungen.

**Pipeline:**
1. `calculate_wuxing_vector_from_planets()` → westlicher Wu-Xing-Vektor
2. `calculate_wuxing_from_bazi()` → östlicher Wu-Xing-Vektor
3. `calculate_harmony_index()` → Harmony-Index
4. Element-für-Element-Vergleich (normalisiert)
5. Cosmic State = `Σ(w_norm_i × b_norm_i)`
6. `generate_fusion_interpretation()` → Textinterpretation

#### 6.2.11 `generate_fusion_interpretation(harmony, comparison, western, bazi)` → `str` (Zeile 552-595)

Erzeugt eine deutsche Textinterpretation der Fusion-Analyse.

**Ausgabeformat:**
```
Harmonie-Index: 72.34%
Gute Harmonie - Die Energien unterstützen sich gegenseitig

Westliche Dominanz: Wasser
Östliche Dominanz: Erde

Ihre westliche und östliche Chart stehen in starker Resonanz.
Die Energien ergänzen sich harmonisch.
```

---

### 6.3 CLI-Modul (`cli.py`, 67 LOC)

**Aufruf:** `python -m bazi_engine.cli <DATE> [OPTIONS]`

| Argument/Option | Typ | Default | Beschreibung |
|---|---|---|---|
| `date` | positional | — | ISO 8601 Lokaldatum |
| `--tz` | `str` | `Europe/Berlin` | IANA Zeitzone |
| `--lon` | `float` | `13.4050` | Längengrad |
| `--lat` | `float` | `52.52` | Breitengrad |
| `--standard` | `CIVIL\|LMT` | `CIVIL` | Zeitstandard |
| `--boundary` | `midnight\|zi` | `midnight` | Tagesgrenze |
| `--accuracy` | `float` | `1.0` | Iterationsgenauigkeit (Sek.) |
| `--strict` / `--no-strict` | `bool` | `True` | DST-Validierung |
| `--json` | flag | — | JSON-Ausgabe |

**Text-Ausgabe:**
```
Input: 2024-02-10T14:30:00 Europe/Berlin (13.405, 52.52)
Pillars: JiaChen BingYin JiaChen XinWei
LiChun local: 2024-02-04T09:27:00+01:00
Solar terms: 24
```

**JSON-Ausgabe:**
```json
{
  "pillars": { "year": "JiaChen", "month": "BingYin", "day": "JiaChen", "hour": "XinWei" },
  "dates": { "birth_local": "...", "birth_utc": "...", "lichun_local": "..." },
  "solar_terms": 24
}
```

---

## 7. BAFE-Subpackage (Contract-First Validator)

**Paket:** `bazi_engine/bafe/`
**Zweck:** Spezifikationskonforme Validierung von Berechnungskonfigurationen gemäß JSON-Schema (Draft-07).

### 7.1 Architektur-Überblick

```
bafe/
├── __init__.py           → exportiert validate_request
├── service.py            → Haupt-Validierungspipeline (7 Compliance-Dimensionen)
├── mapping.py            → Branch-Index-Mapping (SHIFT_BOUNDARIES / SHIFT_LONGITUDES)
├── kernel.py             → Von-Mises Soft-Kernel für weiche Branch-Gewichtung
├── harmonics.py          → Phasor-Feature-Extraktion (Fourier-Harmonik)
├── canonical_json.py     → Deterministische JSON-Serialisierung + SHA-256 Fingerprint
├── refdata.py            → RefData-Artefakt-Evaluierung (Ephemeriden, TZDB, Leap-Seconds, EOP)
├── time_model.py         → Zeitmodell-Evaluierung (DST, TLST, UT1/TT)
├── ruleset_loader.py     → Ruleset-Loader (standard_bazi_2026.json)
└── errors.py             → Contract-gebundener Fehlerkatalog (16 Codes)
```

### 7.2 `validate_request(payload)` → `Dict` (`service.py:71-321`)

**Hauptfunktion.** Nimmt einen ValidateRequest-Payload entgegen und gibt eine ValidateResponse zurück.

#### Eingabe: ValidateRequest-Schema

```json
{
  "validate_level": "FULL",
  "now_utc_override": "2026-01-01T00:00:00Z",
  "engine_config": {
    "engine_version": "1.0.0-rc0",
    "parameter_set_id": "standard",
    "deterministic": true,
    "compliance_mode": "RELAXED",
    "bazi_ruleset_id": "standard_bazi_2026",
    "refdata": {
      "refdata_pack_id": "refpack-test-001",
      "refdata_mode": "BUNDLED_OFFLINE",
      "allow_network": false,
      "refdata_root_path": null,
      "ephemeris_id": "swisseph-2026",
      "tzdb_version_id": "tzdb-2026a",
      "leaps_source_id": "leaps-iers",
      "eop_source_id": null,
      "verification_policy": {
        "tzdb_gpg_required": false,
        "ephemeris_hash_required": false,
        "leaps_expiry_enforced": false,
        "eop_redundancy_required": false
      }
    }
  },
  "birth_event": {
    "local_datetime": "2024-02-10T14:30:00",
    "tz_id": "Europe/Berlin",
    "geo_lon_deg": 13.405,
    "dst_policy": "error"
  },
  "positions_override": {
    "time_scale": "TT",
    "bodies": {
      "Sun": { "lambda_deg": 321.5 }
    }
  },
  "refdata_manifest_inline": {
    "pack_id": "refpack-test-001",
    "artifacts": [
      { "logical_id": "ephemeris", "present": true, "hash_sha256": "abc..." },
      { "logical_id": "tzdb", "present": true, "signature_ok": true },
      { "logical_id": "leaps", "present": true, "expires_utc": "2099-01-01T00:00:00Z" },
      { "logical_id": "eop", "present": false }
    ]
  }
}
```

#### Ausgabe: ValidateResponse-Schema

```json
{
  "compliance_status": "COMPLIANT",
  "compliance_components": {
    "REFDATA":                { "status": "OK",       "notes": ["mode=BUNDLED_OFFLINE", "allow_network=false"] },
    "TIME":                   { "status": "OK",       "notes": ["time_standard=CIVIL", "dst_policy=error"] },
    "FRAMES":                 { "status": "OK",       "notes": [] },
    "EPHEMERIS":              { "status": "OK",       "notes": ["positions_override_only=true"] },
    "DISCRETIZATION":         { "status": "OK",       "notes": [] },
    "REPRODUCIBILITY":        { "status": "OK",       "notes": [] },
    "INTERPRETATION_POLICY":  { "status": "OK",       "notes": ["interpretation_layer=not_executed_in_validate"] }
  },
  "errors": [],
  "warnings": [],
  "evidence": {
    "refdata": {
      "refdata_pack_id": "refpack-test-001",
      "allow_network": false,
      "mode": "BUNDLED_OFFLINE",
      "artifacts": {
        "ephemeris": { "logical_id": "ephemeris", "present": true, "verified": true },
        "tzdb": { "logical_id": "tzdb", "present": true, "verified": null },
        "leaps": { "logical_id": "leaps", "present": true, "verified": null },
        "eop": { "logical_id": "eop", "present": false, "verified": null }
      }
    },
    "time": {
      "time_standard": "CIVIL",
      "dst_policy": "error",
      "ut1_quality": "missing",
      "tt_quality": "ok",
      "tlst_quality": "missing",
      "eot_provenance": null,
      "uncertainty_budget_sec": null
    },
    "frames": {
      "epoch_id": "ofDate",
      "zodiac_mode": "tropical",
      "ayanamsa_id": null
    },
    "ephemeris": { "ephemeris_id": "swisseph-2026", "time_scale": "TT", "bodies": ["Sun"] },
    "discretization": {
      "interval_convention": "HALF_OPEN",
      "branch_coordinate_convention": "SHIFT_BOUNDARIES",
      "boundary_distance_deg": 15.0,
      "classification_unstable": false
    },
    "reproducibility": {
      "config_fingerprint": "a1b2c3d4...",
      "float_format_policy": { "mode": "shortest_roundtrip", "fixed_decimals": null },
      "json_canonicalization": { "sorted_keys": true, "utf8": true }
    },
    "interpretation": { "lint_status": null, "statements_returned": null }
  }
}
```

#### Compliance-Status-Logik

| Bedingung | Status |
|---|---|
| Keine Fehler und keine Warnungen | `COMPLIANT` |
| Warnungen aber keine Fehler | `DEGRADED` |
| Mindestens ein Fehler | `NON_COMPLIANT` |

#### 7 Compliance-Dimensionen

| Dimension | Prüfungen |
|---|---|
| **REFDATA** | Netzwerk-Verbot, Manifest-Pflicht, Artefakt-Hashes, Signaturen, Ablaufdaten |
| **TIME** | DST-Auflösung, TLST-Berechnung, UT1/TT-Qualität |
| **FRAMES** | Zodiac-Modus, Ayanamsa-ID bei sidereal |
| **EPHEMERIS** | Positions-Override, Zeitskala |
| **DISCRETIZATION** | SHIFT_BOUNDARIES/LONGITUDES-Konsistenz, Day-Cycle-Anchor, Boundary-Distance |
| **REPRODUCIBILITY** | Config-Fingerprint (SHA-256 über kanonisches JSON) |
| **INTERPRETATION_POLICY** | Lint-Status (nicht in /validate ausgeführt) |

### 7.3 Fehlerkatalog (`errors.py:7-25`)

| Error-Code | Schwere | Auslöser |
|---|---|---|
| `REFDATA_NETWORK_FORBIDDEN` | ERROR | `allow_network=true` bei BUNDLED_OFFLINE/LOCAL_MIRROR |
| `REFDATA_MANIFEST_MISSING` | ERROR | Offline-Modus ohne Manifest |
| `EPHEMERIS_HASH_MISMATCH` | ERROR | SHA-256 stimmt nicht überein |
| `EPHEMERIS_MISSING` | ERROR | Ephemeris-Artefakt fehlt |
| `TZDB_SIGNATURE_INVALID` | ERROR | GPG-Signatur ungültig |
| `LEAP_SECONDS_FILE_EXPIRED` | ERROR | Leap-Seconds-Datei abgelaufen |
| `MISSING_TT` | ERROR | STRICT-Modus ohne TT-Qualität |
| `EOP_MISSING` | ERROR | EOP-Redundanz verlangt, Artefakt fehlt |
| `EOP_STALE` | WARNING | EOP-Artefakt als veraltet markiert |
| `EOP_PREDICTED_REGION_USED` | ERROR | Vorhergesagte EOP-Region verwendet |
| `DST_AMBIGUOUS_LOCAL_TIME` | ERROR | Ambige Ortszeit mit dst_policy=error |
| `DST_NONEXISTENT_LOCAL_TIME` | ERROR | Nicht-existente Ortszeit (DST-Lücke) |
| `INCONSISTENT_BRANCH_ORIGIN_FOR_SHIFTED_LONGITUDES` | ERROR | SHIFT_LONGITUDES != SHIFT_BOUNDARIES |
| `MISSING_DAY_CYCLE_ANCHOR` | ERROR/WARN | Day-Cycle-Anchor nicht verifiziert |
| `MISSING_AYANAMSA_ID` | ERROR | Sidereal-Modus ohne Ayanamsa |
| `INTERP_DERIVATION_EMPTY` | ERROR | Leere Interpretation |
| `INTERP_LINT_FAIL` | ERROR | Interpretation-Lint fehlgeschlagen |

### 7.4 Mapping-Funktionen (`mapping.py`)

#### 7.4.1 Winkel-Normalisierung

| Funktion | Zeile | Ausgabebereich | Beschreibung |
|---|---|---|---|
| `wrap360(x)` | 7-15 | [0, 360) | Standard-Normalisierung |
| `wrap180(x)` | 17-23 | (-180, 180] | Vorzeichenbehaftete Normalisierung |
| `delta_deg(a, b)` | 25-27 | [0, 180] | Absolute Winkeldifferenz |

#### 7.4.2 Branch-Index-Mapping

| Funktion | Zeile | Konvention | Beschreibung |
|---|---|---|---|
| `branch_index_shift_boundaries(l, *, zi_apex, width)` | 33-37 | **K1 (empfohlen)** | Branch-Ursprung bei `zi_apex - width/2`, HALF_OPEN |
| `branch_index_shift_longitudes(l, *, zi_apex, width, phi)` | 39-51 | **K2** | Äquivalent zu K1 bei korrekter Implementierung |
| `branch_index_shift_longitudes_misused(...)` | 53-67 | **FEHLERHAFT** | Absichtlich falsch, nur für Tests |

**K1-Formel:**
```
b0 = wrap360(zi_apex - width/2)          // Branch-Ursprung
x  = wrap360(lambda - b0) / width        // Position in Branch-Einheiten
index = floor(x) % 12
```

**Standard-Konfiguration:** `zi_apex=270 deg, width=30 deg, phi=15 deg`

#### 7.4.3 Stunden-Branch aus TLST

| Funktion | Zeile | Beschreibung |
|---|---|---|
| `hour_branch_index_from_tlst(tlst_hours)` | 80-86 | `floor(((TLST + 1) mod 24) / 2) % 12` |
| `nearest_hour_boundary_distance_minutes(tlst_hours)` | 88-107 | Abstand zur nächsten Stundenzweig-Grenze |

**Stundenzweig-Zuordnung:**
```
Zi:   [23:00, 01:00)
Chou: [01:00, 03:00)
Yin:  [03:00, 05:00)
...
Hai:  [21:00, 23:00)
```

#### 7.4.4 Boundary-Distance und Equivalence-Checker

| Funktion | Zeile | Beschreibung |
|---|---|---|
| `nearest_boundary_distance_deg(l, *, zi_apex, width)` | 69-78 | Abstand in Grad zur nächsten Branch-Grenze |
| `shift_longitudes_equivalence_ok(impl_fn, ...)` | 110-130 | Prüft ob K2 Impl. identisch K1 auf Sample |

**Instabilitätserkennung:** `boundary_distance < 0.1 deg` = instabile Klassifikation.

### 7.5 Kernel-Funktionen (`kernel.py`)

**Von-Mises Soft-Kernel:** Weiche Branch-Gewichtung statt harter HALF_OPEN-Segmentierung.

| Funktion | Zeile | Beschreibung |
|---|---|---|
| `_von_mises_unnormalized(d_deg, kappa)` | 9-12 | `exp(kappa * cos(d_rad))` |
| `branch_centers_deg(*, zi_apex, width)` | 14-15 | 12 Branch-Zentrums-Winkel |
| `soft_branch_weights_von_mises(l, *, zi_apex, width, kappa)` | 17-30 | 12 normalisierte Gewichte |
| `soft_branch_weights(l, *, kernel, zi_apex, width)` | 32-50 | Dispatcher (aktuell nur von_mises) |

**Eigenschaft:** Alle Gewichte >= 0, Summe = 1.0. kappa=4.0 (Standard).

### 7.6 Harmonik-Funktionen (`harmonics.py`)

| Funktion | Zeile | Beschreibung |
|---|---|---|
| `phasor(angles, weights, k)` | 9-20 | Gewichteter Phasor k-ter Ordnung |
| `phasor_features(angles, weights, ks)` | 22-43 | Feature-Extraktion: Amplitude, Orientierung, Degeneriertheit |

**Phasor-Feature-Ausgabe pro k:**
```json
{ "R_k": [re, im], "A_k": amplitude, "O_k_deg": orientation, "degenerate": false }
```

### 7.7 Kanonisches JSON (`canonical_json.py`)

| Funktion | Zeile | Beschreibung |
|---|---|---|
| `canonical_json_dumps(obj, ...)` | 18-43 | Deterministische JSON-Serialisierung |
| `sha256_hex(s)` | 45-46 | SHA-256 eines Strings |
| `config_fingerprint(engine_config, ...)` | 48-74 | Reproduzierbarer Konfigurations-Fingerprint |

**Determinismus:** Sortierte Schlüssel, kein Whitespace, kein NaN/Infinity.

### 7.8 RefData-Evaluierung (`refdata.py`)

`evaluate_refdata()` (Zeile 56-277) prüft 4 Artefakttypen:

| Artefakt | Prüfungen |
|---|---|
| `ephemeris` | Vorhanden, Hash-SHA256-Verifikation |
| `tzdb` | Vorhanden, GPG-Signatur |
| `leaps` | Vorhanden, Ablaufdatum |
| `eop` | Vorhanden, Stale-Markierung, Redundanz |

### 7.9 Zeitmodell-Evaluierung (`time_model.py`)

`evaluate_time()` (Zeile 83-199) prüft:
- DST-Auflösung (ambig/nicht-existent) via `_detect_local_time_status()`
- TLST-Berechnung via `true_solar_time()` aus dem Fusion-Modul
- UT1/TT-Qualitäts-Reporting
- DST-Policy: `"error"`, `"earlier"`, `"later"`

### 7.10 Ruleset-Loader (`ruleset_loader.py`)

| Funktion | Zeile | Beschreibung |
|---|---|---|
| `load_ruleset(ruleset_id)` | 16-25 | Lädt JSON-Ruleset aus `spec/rulesets/` |
| `ruleset_version(ruleset)` | 27-28 | Extrahiert Version |
| `branch_order(ruleset)` | 30-34 | 12-Element Branch-Reihenfolge |
| `hidden_stems_for_branch(ruleset, branch)` | 36-44 | Hidden Stems für einen Zweig |
| `day_cycle_anchor_status(ruleset)` | 46-58 | Anchor-JDN und Verifikationsstatus |

**Aktuelles Ruleset:** `standard_bazi_2026` (Version 1.0.0)

---

## 8. Verifikation: BaZi-Chart, Ephemeriden, Fusion-Mathematik

### 8.1 BaZi-Chart-Generierung – Verifikation

#### 8.1.1 Berechnungspipeline-Integrität

Die `compute_bazi()`-Funktion (`bazi.py:46-149`) implementiert eine vollständige 9-Schritt-Pipeline:

| Schritt | Funktion | Verifiziert durch | Status |
|---|---|---|---|
| ISO-Parsing | `parse_local_iso()` | DST Round-Trip-Check | Implementiert |
| UTC-Konvertierung | `to_chart_local()` | CIVIL/LMT Branching | Implementiert |
| Julian Day | `datetime_utc_to_jd_ut()` | UTC-Pflichtprüfung | Implementiert |
| Delta-T-Berechnung | `backend.delta_t_seconds()` | Swiss Ephemeris `swe.deltat()` | Implementiert |
| Jahressäule | `year_pillar_from_solar_year()` | LiChun-Grenze (315 deg) | Verifiziert via Golden Vectors |
| Monatssäule | `month_pillar_from_year_stem()` | 13 Jie-Übergänge (streng aufsteigend) | Verifiziert via Invarianten |
| Tagessäule | `sexagenary_day_index_from_date()` | JDN + Offset=49, Kalibriert 1949-10-01 | Verifiziert via Referenzdaten |
| Stundensäule | `hour_pillar_from_day_stem()` | Tagesstamm-basierte Ableitung | Verifiziert via Golden Vectors |
| 24 Sonnenterme | `compute_24_solar_terms_for_window()` | Diagnostik (optional, try-catch) | Implementiert |

#### 8.1.2 LiChun-Grenzfallprüfung

| Testfall | Zeitpunkt | LiChun 2024 | Ergebnis |
|---|---|---|---|
| `Berlin_just_before_LiChun` | 2024-02-04T09:26:00 | ~09:27 | Solarjahr 2023, **GuiMao** |
| `Berlin_just_after_LiChun` | 2024-02-04T09:28:00 | ~09:27 | Solarjahr 2024, **JiaChen** |

**Grenzauflösung:** +/- 1 Minute, bestätigt durch Swiss Ephemeris `solcross_ut()`.

#### 8.1.3 Day-Anchor-Kalibrierung

| Referenzdatum | Erwarteter Index | Offset | Status |
|---|---|---|---|
| 1912-02-18 | 0 (Jia-Zi) | 49 | Verifiziert (`test_invariants.py`) |
| 1949-10-01 | 0 (Jia-Zi) | 49 | Verifiziert (`test_invariants.py`) |
| Custom Anchor idx=1 | Verschiebt alle Tage um +1 | Dynamisch | Verifiziert (`test_golden_vectors.py`) |

#### 8.1.4 Immutabilitäts-Garantie

Alle Datenstrukturen verwenden `frozen=True`:
`Pillar`, `FourPillars`, `SolarTerm`, `BaziInput`, `BaziResult`, `SwissEphBackend`
Keine Mutation nach Erstellung möglich. Deterministische Berechnung garantiert.

### 8.2 Exakte Ephemeriden – Verifikation

#### 8.2.1 Swiss Ephemeris Integration

| Komponente | Implementierung | Genauigkeit |
|---|---|---|
| Sonnenposition | `swe.calc_ut(jd, SUN, FLG_SWIEPH)` | +/- 0.001 Bogensekunden |
| Sonnenlängen-Überquerung | `swe.solcross_ut(target, jd_start)` | +/- 1 Sekunde (konfigurierbar) |
| Delta-T (TT - UT) | `swe.deltat(jd_ut) * 86400` | IAU/IERS Standard |
| Julian Day | `swe.julday(y, m, d, h)` | Exakt |
| Reverse Julian Day | `swe.revjul(jd)` | Exakt mit Mikrosekunden-Korrektur |

#### 8.2.2 Bisektions-Fallback

Wenn `solcross_ut()` nicht verfügbar (z.B. Skyfield-Backend):

| Parameter | Wert | Beschreibung |
|---|---|---|
| `accuracy_seconds` | 1.0 (Default) | Zielgenauigkeit |
| `max_iter` | 80 | Maximale Iterationen |
| `max_span_days` | 40.0 | Maximales Suchfenster |
| Schrittweite | 1.0 Tag | Für Interval-Bracketing |

**Konvergenzgarantie:** 80 Bisektions-Iterationen erreichen ~10^-24 Tage Genauigkeit.

#### 8.2.3 Ephemeris-Dateien

| Datei | Abdeckung | Zweck |
|---|---|---|
| `sepl_18.se1` | 1800-2400 AD | Planeten-Ephemeris |
| `semo_18.se1` | 1800-2400 AD | Mond-Ephemeris |
| `seas_18.se1` | 1800-2400 AD | Asteroiden-Ephemeris |
| `seplm06.se1` | Ergänzend | Ergänzende Daten |

**Offline-Garantie:** Kein Download zur Laufzeit. `FileNotFoundError` bei fehlenden Dateien.

#### 8.2.4 Westliche Planeten-Berechnung

14 Himmelskörper via `swe.calc_ut()` mit `FLG_SWIEPH | FLG_SPEED`:
- Ekliptikale Länge, Breite, Distanz, Geschwindigkeit
- Retrograd-Erkennung: `speed_lon < 0`
- Häusersystem-Fallback: Placidus -> Porphyry -> Whole Sign

### 8.3 Mathematische Angleichung durch Fusion – Verifikation

#### 8.3.1 Wu-Xing-Vektormathematik

Die Fusion verbindet westliche und östliche Astrologie über **5-dimensionale Vektoren**:

```
V_western = [Holz, Feuer, Erde, Metall, Wasser]   (aus Planetenpositionen)
V_bazi    = [Holz, Feuer, Erde, Metall, Wasser]   (aus BaZi Hidden Stems)
```

**Normalisierung:** L2-Norm -> Einheitsvektoren fuer vergleichbare Richtungen.

#### 8.3.2 Harmony-Index (Dot-Product-Methode)

```
H = Summe(V_w_norm_i * V_b_norm_i)    fuer i in {Holz, Feuer, Erde, Metall, Wasser}
H = max(0, H)                          Clamped auf [0, 1]
```

**Mathematische Eigenschaften:**
- H = 1.0: Identische Elementverteilung (perfekte Resonanz)
- H = 0.0: Orthogonale Verteilungen (maximale Divergenz)
- H > 0.8: Starke Übereinstimmung
- Symmetrisch: H(V_w, V_b) = H(V_b, V_w)

#### 8.3.3 Westlicher Wu-Xing-Vektor

| Planet | Element | Gewicht (normal) | Gewicht (retrograd) |
|---|---|---|---|
| Sun | Feuer | 1.0 | 1.3 |
| Moon | Wasser | 1.0 | 1.3 |
| Mercury | Erde/Metall (Tag/Nacht) | 1.0 | 1.3 |
| Venus | Metall | 1.0 | 1.3 |
| Mars | Feuer | 1.0 | 1.3 |
| Jupiter | Holz | 1.0 | 1.3 |
| Saturn | Erde | 1.0 | 1.3 |
| Uranus | Holz | 1.0 | 1.3 |
| Neptune | Wasser | 1.0 | 1.3 |
| Pluto | Feuer | 1.0 | 1.3 |

#### 8.3.4 Östlicher Wu-Xing-Vektor (Hidden-Stems-Gewichtung)

Pro Säule:
- **Himmelsstamm:** Element * 1.0
- **Erdzweig Hidden Stems:** 主气 * 1.0, 中气 * 0.5, 余气 * 0.3

#### 8.3.5 Equation of Time

NOAA-Fourier-Formel:
```
gamma = 2*pi * (N - 1) / 365
E = 229.18 * (0.000075 + 0.001868*cos(gamma) - 0.032077*sin(gamma)
              - 0.014615*cos(2*gamma) - 0.040849*sin(2*gamma))
```

Bereich: -14.2 bis +16.4 Minuten. Verwendet in `/calculate/tst` und BAFE Zeitmodell.

#### 8.3.6 Branch-Mapping-Konsistenz

| Prüfung | Methode | Status |
|---|---|---|
| K1 = K2 | `shift_longitudes_equivalence_ok()` | Verifiziert (TV2, TV3) |
| HALF_OPEN Grenzen | 284.999 deg vs 285.0 deg | Verifiziert (TV1) |
| Fehlerhafte Impl. erkannt | `misused()` != K1 | Verifiziert (TV3) |
| TLST-Stundengrenzen | 0.999h vs 1.0h, 22.999h vs 23.0h | Verifiziert (TV4) |

---

## 9. Testabdeckung & Golden Vectors

### 9.1 Testdateien-Übersicht

| Datei | Tests | Typ | Beschreibung |
|---|---|---|---|
| `test_golden.py` | 4 | Golden Vector | Exakte Pillar-Erwartungen |
| `test_golden_vectors.py` | 5 | Extended Vector | Edge Cases, Custom Anchor |
| `test_invariants.py` | 2 | Invariant | Strukturelle Eigenschaften |
| `test_api.py` | 11 | API/Contract | Schema-Validierung, Policy-Checks |
| `test_properties.py` | 4 | Property | Mathematische Eigenschaften |

**Gesamtzahl: 26 Tests**

### 9.2 Golden Vectors (`test_golden.py`)

| ID | Testfall | Input | Erwartete Säulen |
|---|---|---|---|
| 1 | `Berlin_2024-02-10` | 2024-02-10T14:30, Europe/Berlin | JiaChen, BingYin, JiaChen, XinWei |
| 2 | `Berlin_just_before_LiChun` | 2024-02-04T09:26, Europe/Berlin | GuiMao, YiChou, WuXu, DingSi |
| 3 | `Berlin_just_after_LiChun` | 2024-02-04T09:28, Europe/Berlin | JiaChen, BingYin, WuXu, DingSi |
| 4 | `Madrid_zi_LMT` | 2024-02-04T23:30, Europe/Madrid, LMT+Zi | JiaChen, BingYin, WuXu, GuiHai |

### 9.3 Erweiterte Vektoren (`test_golden_vectors.py`)

| ID | Testfall | Besonderheit | Erwartete Säulen |
|---|---|---|---|
| 1 | `Berlin_2024_Standard` | Standardfall | JiaChen, BingYin, JiaChen, XinWei |
| 2 | `Berlin_Pre_LiChun` | Vor LiChun, Vorjahr | GuiMao, YiChou, WuXu, DingSi |
| 3 | `Longyearbyen_Winter` | 78 deg N Breitengrad | GuiMao, JiaZi, JiaZi, JiaZi |
| 4 | `Custom_Anchor_Shift_1` | Anker idx=1 | JiaChen, BingYin, YiSi, GuiWei |
| 5 | `Custom_Anchor_Standard` | Anker idx=0 (Standard) | JiaChen, BingYin, JiaChen, XinWei |

### 9.4 Invarianz-Tests (`test_invariants.py`)

| Test | Prüfung |
|---|---|
| `test_day_offset_reference_examples` | `DAY_OFFSET=49`, 1912-02-18 -> 0, 1949-10-01 -> 0 |
| `test_month_boundaries_strict_increasing` | 13 Grenzen streng aufsteigend |

### 9.5 API/Contract-Tests (`test_api.py`)

| Test | Vektor | Prüfung |
|---|---|---|
| `test_TV1_branch_boundary_half_open` | TV1 | 4 Grenzwert-Cases für SHIFT_BOUNDARIES |
| `test_TV2_convention_equivalence_k1_eq_k2` | TV2 | K1 = K2 für 7 Lambda-Werte |
| `test_TV3_forbidden_mixing_detector` | TV3 | Korrekte Impl. ok, Fehlerhafte Impl. fail |
| `test_TV4_tlst_hour_boundary_rule` | TV4 | 4 TLST-Stundengrenzen |
| `test_TV5_soft_kernel_symmetry` | TV5 | Summe=1, alle>=0, Symmetrie |
| `test_TV6_hidden_stems_mapping` | TV6 | Zi->[Gui], Chou->[Ji,Gui,Xin], Hai->[Ren,Jia] |
| `test_TV7_refdata_policy_checks` (6x) | TV7 | 6 Szenarien mit erwarteten Error-Codes |
| `test_missing_tt_in_strict_mode` | — | STRICT + fehlende TT -> MISSING_TT |
| `test_validate_endpoint_smoke` | — | /validate HTTP 200 + Schema-valid |

### 9.6 Property-Tests (`test_properties.py`)

| Test | Eigenschaft |
|---|---|
| `test_PT1_wrap_periodicity_and_ranges` | `wrap360` in [0,360), `wrap180` in (-180,180], Periodizität |
| `test_PT2_kernel_weights_sum_to_one` | Von-Mises: Summe w = 1.0, alle w >= 0 |
| `test_PT3_harmonic_periodicity_and_degeneracy` | Phasor: +360 deg invariant, Gegenüber-Cancellation |
| `test_PT4_config_fingerprint_determinism` | Gleicher Inhalt, andere Key-Reihenfolge, gleicher Hash |

### 9.7 Ruleset `standard_bazi_2026`

| Regelkategorie | Konfiguration |
|---|---|
| **Jahresgrenze** | Sonnenlänge 315 deg (LiChun), TT-Zeitskala, tropisch |
| **Monatsgrenze** | Jieqi-Crossing, 315 deg Start, 30 deg Schritte, TT, tropisch |
| **Stundenregel** | TLST-basiert, 2h-Bins, HALF_OPEN |
| **Tagesgrenze** | Zi-Stunde Start (23:00 TLST), HALF_OPEN |
| **Day-Cycle-Anchor** | JDN 2419451, unverified (Warnung RELAXED, Fehler STRICT) |
| **Hidden Stems** | Tabellen-Modus, principal/central/residual (1.0/0.5/0.3) |

---

## 10. Zusammenfassung

### 10.1 Funktionsmatrix

| Bereich | Funktionen | Status |
|---|---|---|
| BaZi-Kern | 9 Funktionen in `bazi.py` | Vollständig implementiert |
| Ephemeris | 8 Funktionen in `ephemeris.py` | Vollständig implementiert |
| Sonnenterme | 4 Funktionen in `jieqi.py` | Vollständig implementiert |
| Zeitkonvertierung | 5 Funktionen in `time_utils.py` | Vollständig implementiert |
| Western Astrology | 1 Hauptfunktion (14 Planeten) | Vollständig implementiert |
| Fusion | 11 Funktionen in `fusion.py` | Vollständig implementiert |
| API | 11 Endpoints in `app.py` | Vollständig implementiert |
| BAFE Validator | 7 Module, ~30 Funktionen | Vollständig implementiert |
| CLI | 1 Hauptfunktion in `cli.py` | Vollständig implementiert |

### 10.2 Verifikations-Ergebnis

| Prüfpunkt | Ergebnis | Details |
|---|---|---|
| **BaZi-Chart wird generiert** | **JA** | 9-Schritt-Pipeline, 9 Golden Vectors bestätigen Korrektheit |
| **Exakte Ephemeriden berechnet** | **JA** | Swiss Ephemeris mit +/-0.001" Genauigkeit, Delta-T, JD |
| **Mathematische Angleichung (Fusion)** | **JA** | 5D Wu-Xing-Vektoren, Dot-Product Harmony [0,1], Hidden Stems |

### 10.3 Datenfluss End-to-End

```
Benutzer-Input (Datum, Ort, Zeitzone)
    |
    +---> /calculate/bazi ---> compute_bazi() ---> BaZi 4 Säulen
    |                                                |
    +---> /calculate/western ---> compute_western_chart() ---> 14 Planeten + Häuser
    |                                                |
    +---> /calculate/fusion ---> compute_fusion_analysis()
              |
              +-- calculate_wuxing_vector_from_planets() ---> V_western (5D)
              +-- calculate_wuxing_from_bazi() ---> V_bazi (5D)
              +-- calculate_harmony_index() ---> H in [0, 1]
              +-- Elementarer Vergleich (5 x {western, bazi, difference})
              +-- Cosmic State = Summe(V_w_i * V_b_i)
              +-- Textinterpretation (DE)
```

---

**Dokument-Version:** 1.0 (Final)
**Erstellt:** 2026-02-06
**Codebase-Analyse:** Vollständig (alle Dateien gelesen und dokumentiert)
**Gesamtumfang:** ~90 Funktionen, 11 API-Endpoints, 26 Tests
