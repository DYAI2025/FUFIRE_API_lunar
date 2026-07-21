# 02 — WuXingVector: Die Geometrie des Elementarfeldes

**Modul:** `bazi_engine/wuxing/vector.py`  
**Level:** 4 (reine Mathematik, keine Domain-Importe)

---

## Was das Modul enthält

```python
@dataclass
class WuXingVector:
    holz:   float
    feuer:  float
    erde:   float
    metall: float
    wasser: float

    def magnitude() → float          # L2-Norm: ‖v‖ = √(Σ xᵢ²)
    def normalize() → WuXingVector   # Einheitsvektor: v̂ = v / ‖v‖
    def to_list()   → List[float]    # [holz, feuer, erde, metall, wasser]
    def to_dict()   → Dict[str, float]
    @staticmethod zero() → WuXingVector  # Nullvektor
```

---

## Die Mathematik

### Der Vektor als Elementarprofil

Ein `WuXingVector` ist ein Punkt im ℝ⁵ (oder auf der 4-Sphäre S⁴ nach Normalisierung).
Er repräsentiert die **Gewichtung aller fünf Elemente** für ein gegebenes Horoskop.

**Rohvektor (nicht normalisiert):**
Jeder Planet/Stamm/Zweig addiert seinen Elementwert. Die Einheit ist
"Planetengewichte" — kein natürliches Maximum.

```
Beispiel: Sonne (Feuer=1.0) + Mars (Feuer=1.0) + Jupiter (Holz=1.0)
→ v = (1.0, 2.0, 0.0, 0.0, 0.0)
```

**Normalisierter Vektor (Einheitsvektor):**
```
‖v‖ = √(1² + 2² + 0 + 0 + 0) = √5 ≈ 2.236
v̂ = (0.447, 0.894, 0.0, 0.0, 0.0)
‖v̂‖ = 1.0   (exakt)
```

Die Normalisierung macht den Vektor **vergleichbar**: Ein Chart mit 14 Planeten
und eines mit 3 Planeten werden auf dieselbe Sphäre projiziert. Es zählt nur
die relative Verteilung der Elemente, nicht die absolute Stärke.

### L2-Norm (Betrag)

```python
def magnitude(self) -> float:
    return sqrt(sum(x ** 2 for x in self.to_list()))
```

Geometrisch: die Länge des Vektors im euklidischen Raum.

**Bedeutung vor Normalisierung:**  
Ein hoher Betrag bedeutet, dass das Elementarprofil stark ausgeprägt ist
(viele Planeten, starke Qi-Gewichte). Ein niedriger Betrag bedeutet spärliche
Planetendichte oder wenige aktive Pfeiler.

**Nach Normalisierung:** immer = 1.0.

### Normalisierung und die 4-Sphäre

```python
def normalize(self) -> WuXingVector:
    mag = self.magnitude()
    if mag == 0:
        return self          # Nullvektor bleibt Nullvektor
    return WuXingVector(*[x / mag for x in self.to_list()])
```

Alle normalisierten Vektoren liegen auf einer **4-dimensionalen Einheitssphäre S⁴**
(eine Hypersphäre in ℝ⁵). Der Winkel zwischen zwei Punkten auf dieser Sphäre
ist das Ähnlichkeitsmaß — das ist die Grundlage des Harmony Index.

```
Winkel θ zwischen v₁ und v₂:
cos(θ) = v̂₁ · v̂₂ = Σ (v̂₁ᵢ × v̂₂ᵢ)

θ = 0°  → identische Elementstruktur
θ = 90° → vollständige Orthogonalität (kein Elementüberlapp)
θ > 90° → wird nicht vorkommen, da alle Komponenten ≥ 0
           (alle Vektoren liegen im ersten Orthanten von ℝ⁵)
```

### Warum nur der erste Orthant?

Elementargewichte können nicht negativ sein: ein Planet "hat" ein Element,
oder er hat es nicht. Es gibt keine negative Feuerenergie.

Das bedeutet: Alle WuXingVektoren liegen im **positiven Orthanten**
`{v ∈ ℝ⁵ : vᵢ ≥ 0}`, und der maximale Winkel zwischen zwei solchen
Vektoren ist 90°. Der Harmony Index liegt daher immer in [0, 1].

---

## Deutungsraum: Geometrie als Symbolsprache

### Was der Betrag vor Normalisierung aussagt

Der Rohbetrag `‖v‖` ist ein Maß für die **Intensität des Elementarfeldes**.

Zwei Personen können dieselbe normalisierte Richtung haben (identische
Elementverteilung) aber völlig verschiedene Intensitäten:

```
Person A:  v = (3.0, 4.0, 0, 0, 0)  → ‖v‖ = 5.0   → starkes Feld
Person B:  v = (0.3, 0.4, 0, 0, 0)  → ‖v‖ = 0.5   → schwaches Feld
Beide:     v̂ = (0.6, 0.8, 0, 0, 0)  → gleiche Richtung
```

Intensitätsinterpretation (noch nicht im aktuellen System kodiert):
- Hohes ‖v‖: starke elementare Ausprägung, konsolidiertes Profil
- Niedriges ‖v‖: diffuses Profil, viele Elemente mittelstark verteilt

### Die Sphäre als Deutungsraum

Die 4-Sphäre ist kein abstraktes mathematisches Objekt — sie ist
ein Raum möglicher Charakterprofile. Jeder Punkt auf ihr ist ein
einzigartiges Elementarmuster.

**Antipoden auf der Sphäre:**  
Der maximal mögliche Gegenpol zu "reines Feuer" = `(0, 1, 0, 0, 0)`
ist "alles außer Feuer". In der Praxis erzeugen BaZi und westliche
Astrologie nie perfekte Antipoden — echte Horoskope haben immer
alle Elemente in gewissem Maß vertreten.

**Cluster auf der Sphäre:**  
Statistisch werden bestimmte Bereiche der Sphäre häufiger besetzt sein
als andere (Geburtshäufung in Jahreszeiten, saisonale BaZi-Muster).
Das wäre ein interessantes Forschungsfeld: Welche Elementarprofile
kommen empirisch häufig vor?

### Anschlussfähigkeit zu den Traditionen

**Westliche Astrologie:**  
Die Idee der Elementargewichtung ist klassisch. Marc Edmund Jones'
"Planetary Patterns" und John Addeys Harmonik arbeiten implizit mit
Vektorraumkonzepten. Die explizite Normalisierung und die geometrische
Interpretation des Winkels als Ähnlichkeitsmaß sind neu — aber die
Grundidee, Elemente zu gewichten und zu vergleichen, ist kanonisch.

**BaZi-Tradition:**  
Das Konzept des **Wu Xing Sheng Ke** (五行生克 — Erzeugung und Kontrolle)
ist explizit relationaler Natur: Elemente stehen in Beziehung zueinander.
Die Vektorraumdarstellung formalisiert diese Relationalität: ein Vektor
mit hohem Feuer-Anteil "dominiert" Metall und "unterwirft sich" Wasser —
diese klassischen Beziehungen sind in der Geometrie codiert, auch wenn
sie nicht explizit berechnet werden.

Das Fehlen des **Ke-Zyklus (相克, Kontrollzyklus)** in der aktuellen
Implementierung ist die wichtigste offene Erweiterung:
```
Holz  kontrolliert Erde
Feuer kontrolliert Metall
Erde  kontrolliert Wasser
Metall kontrolliert Holz
Wasser kontrolliert Feuer
```
Ein Vektor mit hohem Feuer neben hohem Metall würde im Ke-Zyklus
eine Spannungsbeziehung signalisieren — derzeit wird das nur durch
die Differenz im `elemental_comparison`-Feld sichtbar, nicht als
eigenständige Berechnung.
