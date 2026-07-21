# 06 — compute_fusion_analysis(): Die Gesamtarchitektur

**Funktion:** `compute_fusion_analysis()` in `bazi_engine/fusion.py`  
**Endpunkt:** `POST /calculate/fusion`

---

## Was die Funktion tut

```python
def compute_fusion_analysis(
    birth_utc_dt: datetime,
    latitude: float,
    longitude: float,
    bazi_pillars: Dict[str, Dict[str, str]],
    western_bodies: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]
```

Sie nimmt zwei vollständig vorberechnete astrologische Datensätze entgegen
(Planetenpositionen und Vier Pfeiler) und kombiniert sie zu einem einheitlichen
Profil. Sie führt selbst keine Ephemerisberechnungen durch.

---

## Der vollständige Berechnungsablauf

```
1. calculate_wuxing_vector_from_planets(western_bodies)
   → WuXingVector (roh, nicht normalisiert)

2. calculate_wuxing_from_bazi(bazi_pillars)
   → WuXingVector (roh, nicht normalisiert)

3. calculate_harmony_index(western_wuxing, bazi_wuxing)
   → {"harmony_index": H, "interpretation": ..., "western_vector": ..., "bazi_vector": ...}
   (normalisiert intern für H-Berechnung)

4. western_norm = western_wuxing.normalize()
   bazi_norm    = bazi_wuxing.normalize()

5. elemental_comparison: für jedes Element E:
   {
     "western":    western_norm.E,
     "bazi":       bazi_norm.E,
     "difference": western_norm.E − bazi_norm.E
   }

6. cosmic_state = Σ (western_norm.i × bazi_norm.i)
   = identisch mit harmony_index (dot product der normalisierten Vektoren)

7. fusion_interpretation = generate_fusion_interpretation(...)
```

---

## Die Ausgabestruktur

```json
{
  "wu_xing_vectors": {
    "western_planets": {
      "Holz": 0.231, "Feuer": 0.612, "Erde": 0.418,
      "Metall": 0.521, "Wasser": 0.337
    },
    "bazi_pillars": {
      "Holz": 0.730, "Feuer": 0.340, "Erde": 0.560,
      "Metall": 0.170, "Wasser": 0.102
    }
  },
  "harmony_index": {
    "harmony_index": 0.6847,
    "interpretation": "Gute Harmonie - Die Energien unterstützen sich gegenseitig",
    "method": "dot_product",
    "western_vector": {...},
    "bazi_vector": {...}
  },
  "elemental_comparison": {
    "Holz":   {"western": 0.231, "bazi": 0.730, "difference": -0.499},
    "Feuer":  {"western": 0.612, "bazi": 0.340, "difference": +0.272},
    "Erde":   {"western": 0.418, "bazi": 0.560, "difference": -0.142},
    "Metall": {"western": 0.521, "bazi": 0.170, "difference": +0.351},
    "Wasser": {"western": 0.337, "bazi": 0.102, "difference": +0.235}
  },
  "cosmic_state": 0.6847,
  "fusion_interpretation": "Harmonie-Index: 68,47%\n..."
}
```

---

## Redundanz: `cosmic_state` = `harmony_index`

**Das ist eine Redundanz im aktuellen Code.**

```python
cosmic_state = sum(w * b for w, b in zip(western_norm.to_list(), bazi_norm.to_list()))
```

Das ist mathematisch identisch mit dem `harmony_index`, weil
`harmony_index = Σ (w_normᵢ × b_normᵢ)` für die dot-product-Methode.

**Intention:** `cosmic_state` sollte ein zweites, unabhängiges Maß sein —
z.B. die Gesamtenergie `‖v_west + v_bazi‖` oder ein zeitkorrigierter Wert.
Diese Erweiterung ist noch nicht implementiert.

**Nächste Evolutionsstufe:**
```python
cosmic_state = (western_wuxing + bazi_wuxing).magnitude()
# → misst absolute Intensität, nicht relative Ähnlichkeit
```

---

## `generate_fusion_interpretation()`

```python
def generate_fusion_interpretation(
    harmony: float,
    comparison: Dict[str, Dict[str, float]],
    western: WuXingVector,
    bazi: WuXingVector,
) -> str
```

**Aktueller Algorithmus:**
1. Bestimme dominantes Element in Western und BaZi (argmax)
2. Schreibe H als Prozentsatz
3. Wähle einen von drei Textbausteinen basierend auf H-Schwellen (≥0.6, ≥0.3, sonst)

**Was das leistet:** Eine minimale, deterministische Textgenerierung.
**Was fehlt:** Elementspezifische Aussagen, Archetypen, narrative Tiefe.
Das ist der Bereich, der durch das Deutungslogik-Framework erweitert wird
(→ `docs/fusion/08_deutungslogiken.md`).

---

## Signalfluss-Diagramm

```
[compute_western_chart()]          [compute_bazi()]
       │                                  │
       ▼                                  ▼
  {planetary bodies}              {four pillars}
       │                                  │
       ▼                                  ▼
calculate_wuxing_vector_          calculate_wuxing_
from_planets()                    from_bazi()
       │                                  │
       └──────────────┬───────────────────┘
                      ▼
               WuXingVector_west  WuXingVector_bazi
                      │                  │
                      ▼                  ▼
              calculate_harmony_index()
                      │
                      ▼
               H, normalized vectors
                      │
                      ├─→ elemental_comparison (diff/element)
                      ├─→ cosmic_state (= H, todo: refine)
                      └─→ generate_fusion_interpretation()
                                        │
                                        ▼
                               fusion_interpretation (str)
```

---

## Anschlussfähigkeit zu den Traditionen

### Als synkretistisches Instrument

`compute_fusion_analysis()` ist konzeptuell ein **synkretistisches Instrument** —
es verbindet zwei vollständige Systeme, ohne eines zu reduzieren. Beide Systeme
liefern vollständige, für sich stehende Analyse. Die Fusion ist ein Metatool,
das auf die Ausgaben beider Systeme aufgesetzt wird.

Das folgt dem historischen Muster des astrologischen Synkretismus:
Die hellenistische Astrologie kombinierte babylonische Omina-Tradition
mit griechischer Philosophie; die arabische Astrologie integrierte indische
(jyotish) Konzepte; die chinesische Astrologie übernahm während der
Tang-Dynasie (618–907) westliche Kalenderkonzepte.

Fusion Astrology ist der Versuch, diese historisch analoge Bewegung
explizit und mathematisch fundiert zu vollziehen.
