# 05 — Der Kohärenz-Index: Cosinus-Ähnlichkeit als Deutungsmaß

**Funktion:** `calculate_harmony_index()` in `bazi_engine/wuxing/analysis.py`  
**Typ:** Mathematisches Ähnlichkeitsmaß im ℝ⁵

---

## Die Kernidee

Der Kohärenz-Index (H) ist die **Cosinus-Ähnlichkeit** zweier L2-normalisierter
Wu-Xing-Vektoren — einer aus westlichen Planetenpositionen, einer aus den
Vier Pfeilern des BaZi.

```
H = cos(θ) = v̂_west · v̂_bazi = Σᵢ (v̂_westᵢ × v̂_baziᵢ)
```

Weil alle Komponenten ≥ 0 sind, gilt stets `0 ≤ H ≤ 1`.

---

## Die Mathematik im Detail

### Zwei Methoden

**1. Dot Product (Standard):**
```python
w_norm = western_vector.normalize()   # L2-Einheitsvektor
b_norm = bazi_vector.normalize()
dot = sum(w * b for w, b in zip(w_norm.to_list(), b_norm.to_list()))
H = max(0.0, dot)
```

Da beide Vektoren bereits normalisiert sind, ist das Skalarprodukt
der normalisierten Vektoren identisch mit der Cosinus-Ähnlichkeit:
`cos(θ) = (v/‖v‖) · (u/‖u‖) = v·u / (‖v‖ × ‖u‖)`

**2. Cosine (explizit):**
```python
dot = sum(w * b for w, b in zip(western.to_list(), bazi.to_list()))
H = dot / (‖western‖ × ‖bazi‖)
```

Mathematisch äquivalent. Der Unterschied: Bei der expliziten Cosine-Methode
werden die Rohdaten ohne vorherige Normalisierung verrechnet, was numerisch
identisch ist, aber die Herkunft klarer macht.

### Geometrische Interpretation

```
H = 1.0 → θ = 0°   → identische Elementstruktur (parallele Vektoren)
H = 0.8 → θ = 37°  → sehr ähnliche Ausrichtung
H = 0.6 → θ = 53°  → merklich verschieden, aber konvergent
H = 0.4 → θ = 66°  → deutlich divergent
H = 0.2 → θ = 78°  → fast orthogonal
H = 0.0 → θ = 90°  → vollständige Orthogonalität (kein Elementüberlapp)
```

Im positiven Orthant des ℝ⁵ (alle Komponenten ≥ 0) ist 90° der
maximal erreichbare Winkel. Das bedeutet: H kann negativ werden,
wird aber auf max(0.0, dot) geclampt.

**Wann ist H theoretisch negativ?**  
Nie, wenn alle Komponenten nichtnegativ sind. Das `max(0.0, dot)` ist
ein defensiver Schutz gegen numerische Gleitkommafehler.

### Was H *nicht* misst

H ist eine Winkelähnlichkeit, keine Inhaltsnähe. Zwei Vektoren:

```
v₁ = (0.5, 0.5, 0.0, 0.0, 0.0)  → 50% Holz, 50% Feuer
v₂ = (0.4, 0.4, 0.1, 0.05, 0.05) → ähnlich, aber gestreuter
```

Haben einen H-Wert nahe 1.0 — obwohl Person 2 mehr Erde, Metall, Wasser hat.
H misst nur den **relativen Winkel**, nicht die **absolute Zusammensetzung**.

---

## Rückgabestruktur

```json
{
    "harmony_index":   0.7234,
    "interpretation":  "Gute Harmonie - Die Energien unterstützen sich gegenseitig",
    "method":          "dot_product",
    "western_vector":  {"Holz": 0.447, "Feuer": 0.894, "Erde": 0.0, "Metall": 0.0, "Wasser": 0.0},
    "bazi_vector":     {"Holz": 0.730, "Feuer": 0.340, "Erde": 0.560, "Metall": 0.170, "Wasser": 0.102}
}
```

Die zurückgegebenen Vektoren sind die **normalisierten** Vektoren — sie
sind der Grundlage des Harmony-Index und zeigen die relative Elementverteilung.

---

## Deutungsraum: Was der Kohärenz-Index bedeutet

### Die fundamentale Aussage

H misst **strukturelle Kongruenz** zwischen zwei kosmologischen Systemen
am selben Zeitpunkt.

Wenn H hoch ist: Das, was der Himmel zum Geburtszeitpunkt zeigt (Planeten),
entspricht dem, was die Zeitstruktur in sich trägt (Vier Pfeiler). Ost und
West "sagen dasselbe".

Wenn H niedrig ist: Beide Systeme beschreiben denselben Moment aus radikal
verschiedenen Blickwinkeln. Das ist keine Widersprüchlichkeit — es ist ein
Hinweis auf die Komplexität des Moments.

### Das Konzept der "systemischen Kongruenz"

In der klassischen Astrologie gibt es das Konzept der **Rezeption** und
**Dignität** — Planeten verstärken sich, wenn sie in den Zeichen des anderen
stehen. Der Kohärenz-Index generalisiert das: er fragt nicht nach einzelnen
planetaren Rezeptionen, sondern nach der Gesamtkongruenz zweier Systeme.

### Was H klinisch bedeutet (für die Nutzersprache)

| H-Bereich | Erfahrungsebene | Archetypische Situation |
|---|---|---|
| 0.8–1.0 | Tiefe Stimmigkeit | "Alles zieht an einem Strang" |
| 0.6–0.8 | Gute Ausrichtung | "Die Energie fließt meistens in dieselbe Richtung" |
| 0.4–0.6 | Produktive Spannung | "Es gibt Reibung, die aber vorwärtstreibt" |
| 0.2–0.4 | Kreative Dissonanz | "Ich lebe in zwei verschiedenen Rhythmen" |
| 0.0–0.2 | Integrationsauftrag | "Ich bin zwischen zwei Welten und muss den Übergang selbst bauen" |

### Die Frage der Kalibrierung

Die aktuellen Schwellen (0.8, 0.6, 0.4, 0.2) sind heuristisch.
Empirische Fragen, die Testdaten beantworten könnten:

1. Wie ist H in der Bevölkerung verteilt? (Erwartung: Gauß um 0.4–0.6)
2. Korreliert H mit selbst-berichteter "innerer Stimmigkeit"?
3. Gibt es Muster: Bestimmte Zeichen- oder Pfeiler-Kombinationen,
   die systematisch niedrige oder hohe H-Werte erzeugen?

---

## Anschlussfähigkeit zu den Traditionen

### Westliche Astrologie: Aspekte als Ähnlichkeitsmaß

Das klassischste Ähnlichkeitsmaß in der westlichen Astrologie ist der **Aspekt**:
- Konjunktion (0°): höchste Ähnlichkeit
- Opposition (180°): maximaler Unterschied, aber nicht bedeutungslos
- Quadrat (90°): Spannung

Der Kohärenz-Index ist konzeptuell analog — aber er misst den Winkel zwischen
zwei **Systemvektoren** (nicht zwei Planetenpunkten). Es ist eine Verallgemeinerung
des Aspektkonzepts auf den Systemebene.

### BaZi: Palast-Harmonien (合)

Im BaZi gibt es das Konzept der **He (合)** — Kombinationen, bei denen Zweige
oder Stämme sich "anziehen" und eine neue Elementarqualität erzeugen:

- Zi + Chou = Erde-Kombination
- Yin + Hai = Holz-Kombination
- Mao + Xu = Feuer-Kombination

Diese klassischen He-Kombinationen erzeugen per Definition hohe Elementkongruenz
in den betroffenen Dimensionen — sie sind de facto lokale Harmony-Index-Maxima
für spezifische Achsen. Die Harmony-Index-Berechnung "sieht" diese Kombinationen,
kodiert sie aber nicht explizit.

### Harmonik (John Addey): Systemresonanz

John Addeys **Harmonik** (1976) ist das westliche Pendant zum Fusion-Konzept:
Er beschrieb Aspekte als Teilverhältnisse einer fundamentalen Resonanzfrequenz
und versuchte, astrologische Wirkung über harmonische Überlagierung zu modellieren.

Der Kohärenz-Index ist strukturell verwandt: Er misst Resonanz zwischen
Systemen, nicht zwischen einzelnen Punkten. Das Konzept ist
akademisch anschlussfähig an Addeys Forschungstradition.
