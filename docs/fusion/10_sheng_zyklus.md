# 10 — Der Sheng-Zyklus: Struktur, Messung und Interpretation

Dieses Dokument klärt präzise, was der Sheng-Zyklus (相生, xiāng shēng)
**im Fusion-System ist**, was er **nicht ist**, und wie er **sauber** in
Leitfragen integriert wird, ohne neue Messsignale zu erfinden.

---

## Was der Sheng-Zyklus formal ist

### Als zyklische Ordnung (Struktur)

`WUXING_ORDER = ["Holz", "Feuer", "Erde", "Metall", "Wasser"]`

Der Sheng-Zyklus ist die **Nachbarschaftsrelation** über diesen fünf Elementen:

```
NEXT: Holz → Feuer → Erde → Metall → Wasser → Holz (Zyklus)
PREV: Feuer → Holz, Erde → Feuer, Metall → Erde, Wasser → Metall, Holz → Wasser
```

Formal: eine bijektive Abbildung `next: {e₁,...,e₅} → {e₁,...,e₅}` mit
Periode 5, d.h. `next⁵(e) = e` für alle e. Das ist eine zyklische Gruppe
der Ordnung 5: C₅.

**Im Code** (`bazi_engine/wuxing/zones.py`):

```python
_NEXT = {"Holz": "Feuer", "Feuer": "Erde", "Erde": "Metall",
         "Metall": "Wasser", "Wasser": "Holz"}
_PREV = {v: k for k, v in _NEXT.items()}  # automatisch invers
```

Der Test `test_sheng_order_matches_wuxing_order` stellt sicher, dass
`_NEXT` und `WUXING_ORDER` konsistent sind und bleiben.

### Als semantische Bedeutung (Tradition)

Im klassischen Wu-Xing-Denken ist der Sheng-Zyklus ein
**Erzeugungsprinzip** (生, shēng = erzeugen, nähren):

```
Holz  nährt  Feuer   (Brennstoff gibt Flamme)
Feuer nährt  Erde    (Asche bereichert Boden)
Erde  nährt  Metall  (Erde enthält Erze)
Metall nährt Wasser  (Metall schmilzt zu Flüssigkeit; Metall kondensiert Tau)
Wasser nährt Holz    (Wasser tränkt Wurzeln)
```

Und der **Kontrollzyklus** (克, kè — kontrollieren, begrenzen):

```
Holz  kontrolliert  Erde    (Wurzeln durchdringen Boden)
Erde  kontrolliert  Wasser  (Dämme halten Fluss)
Wasser kontrolliert Feuer   (Wasser löscht Feuer)
Feuer kontrolliert  Metall  (Feuer schmilzt Metall)
Metall kontrolliert Holz    (Axt fällt Baum)
```

---

## Was der Sheng-Zyklus im Fusion-System IST

Der Sheng-Zyklus ist im aktuellen Fusion-System:

1. **Die Reihenfolge der Vektorachsen** (`WUXING_ORDER`)  
   → Diese Reihenfolge ist kanonisch (nicht arbiträr) und semantisch
     aufgeladen: benachbarte Achsen sind im Sheng-Zyklus verwandt.

2. **Ein Leitfragen-Generator** in `zones.py`  
   → `_NEXT[elem]` und `_PREV[elem]` werden verwendet, um
     Reflexionsfragen zu strukturieren. Das ist Interpretation,
     kein neues Messsignal.

3. **Eine testbare Konstante**  
   → `test_wuxing_zones.py::TestShengCycle` stellt sicher, dass
     `_NEXT`/`_PREV` korrekt, invertierbar und mit `WUXING_ORDER`
     konsistent sind.

---

## Was der Sheng-Zyklus im Fusion-System NICHT IST

**Nicht automatisch berechnet.** Die Fusion-Mathematik (H, dᵢ, rᵢ) nutzt
den Sheng-Zyklus nicht als Berechnungskanal. Aussagen wie:

> "Weil Holz stark ist, ist Feuer automatisch gestärkt."

...sind **nicht** aus der Mathematik ableitbar. Sie sind traditionell
plausibel (und könnten als eigene Berechnungsebene eingebaut werden),
aber derzeit nicht implementiert.

**Konsequenz für Formulierungen:**

| Formulierung | Status |
|---|---|
| "Holz-Tension erklärt sich durch den Sheng-Zyklus zu Feuer" | ❌ Nicht aus H/d ableitbar |
| "Deine Holz-Stärke sucht Ausdruck — könnte der Schritt Richtung Feuer helfen?" | ✅ Frage, nicht Behauptung |
| "Dein Holz-Wert übersteigt den kosmischen Angebot um 49.9 Pkt." | ✅ Direkt aus d_Holz |

---

## Saubere Integration: Der Sheng-Zyklus als Fragen-Schablone

Das einzige Prinzip: **Fragen, keine Fakten** aus dem Zyklus.

### Leitfragen-Logik (implementiert in `zones.py`)

Für jedes **TENSION-Element E** mit Differenz `d`:

```
d > 0 (West dominiert — Außen bietet mehr als Innen trägt):
  Kernfrage (Ground = d, Vorzeichen):
    "Wo wartet ein Impuls von außen noch auf deine Annahme?"
  Sheng-Frage (Interpretation = prev/next als Struktur):
    "Würde eine stärkere Basis in prev(E) helfen, damit E tragfähig wird
     und in next(E) weiterfließen kann?"

d < 0 (BaZi dominiert — Innen stärker als Außen spiegelt):
  Kernfrage:
    "Wo sucht diese Kraft einen Ausdruck, den sie noch nicht gefunden hat?"
  Sheng-Frage:
    "Würde ein Schritt Richtung next(E) helfen, damit E sichtbarer wird,
     ohne sich zu überdehnen?"
```

Für jedes **DEVELOPMENT-Element E**:

```
Kernfrage:
  "Welche kleine, risikoarme Praxis würde diese Achse stärken?"
Sheng-Frage:
  "Würde ein Mikro-Schritt im Vorgänger prev(E) E indirekt nähren —
   ohne Druck auf sofortige Leistung?"
```

### Beispiel: E = Feuer, d = +0.27 (West dominiert)

```
prev(Feuer) = Holz
next(Feuer) = Erde

Kernfrage: "Der kosmische Moment bietet mehr Feuer-Energie, als deine 
innere Struktur aktuell trägt. Wo wartet ein Impuls von außen noch auf 
deine Annahme?"

Sheng-Frage: "Würde eine stärkere Verwurzelung in Holz helfen, damit der 
Feuer-Impuls von außen tragfähig wird und in Erde weiterfließen kann?"
```

Das ist sauber: `d` kommt aus der Mathematik, `prev`/`next` aus der
Konstante, die Frage ist explizit als `[Sheng-Frage]` markiert.

---

## Der Ke-Zyklus: Offene Erweiterung

Der **Kontrollzyklus (相克)** ist aktuell nicht implementiert.

```
Holz  → kontroliert → Erde
Erde  → kontroliert → Wasser
Wasser → kontroliert → Feuer
Feuer → kontroliert → Metall
Metall → kontroliert → Holz
```

Was eine Ke-Erweiterung leisten könnte:

```python
# Zukünftige Erweiterung (nicht implementiert)
KE = {"Holz": "Erde", "Erde": "Wasser", "Wasser": "Feuer",
      "Feuer": "Metall", "Metall": "Holz"}

def ke_tension(elem, diffs):
    """Wenn E TENSION hat: prüfe ob das kontrollierte Element (KE[E])
    ebenfalls erhöht ist → klassische Tension-Amplifikation."""
    controlled = KE[elem]
    return diffs[controlled]
```

Das wäre ein echter neuer **berechneter Signalkanal** — ableitbar aus den
d_i-Werten, nicht aus Tradition. Erst dann wäre die Ke-Beziehung ein
Ground-Signal, nicht nur eine Interpretationsschicht.

---

## Anschlussfähigkeit zu den Traditionen

### BaZi: Die fünf Elemente als dynamisches System

Im klassischen BaZi sind Sheng und Ke keine statischen Zuordnungen —
sie sind **Kräfterelationen**, die das Gleichgewicht des Charts bestimmen.
Ein starkes Holz "attackiert" Erde (Ke) und "nährt" Feuer (Sheng). Das
ist die Basis der Günstigkeitsgott-Analyse (用神, yòng shén): Welches
Element braucht das Chart zur Balance?

Die aktuelle Fusion-Implementierung arbeitet ohne diese Dynamik —
sie misst statische Vektoren, keine Kräftespiele. Das ist eine bewusste
Vereinfachung für Berechenbarkeit.

### Westliche Astrologie: Aspekte als Ke-Analogon

Der Ke-Zyklus ist dem westlichen Konzept der **Spannungsaspekte**
(Quadrat 90°, Opposition 180°) analog: Elemente, die in einer
Kontrollbeziehung stehen, erzeugen Spannung, nicht Harmonik.

Wenn die Fusion-Mathematik zwei hohe d_i-Werte in einer Ke-Beziehung
zeigt (z.B. Feuer-West stark, Metall-BaZi stark), dann ist das die
mathematische Abbildung einer klassischen Spannungskonstellation —
ohne dass die Ke-Relation explizit kodiert ist.

### Addey / Harmonik: C₅ als Schwingungsraum

John Addeys Harmonik-Theorie beschreibt Aspekte als Teilverhältnisse
eines Grundtons. Die C₅-Gruppe (Sheng-Zyklus) entspricht der
5. Harmonischen — einer der weniger erforschten, aber von Addey
als relevant eingestuften Harmonikstufen.

Die Projektion auf ℝ⁵ mit Sheng-Zyklus-Ordnung ist damit nicht nur
traditionell motiviert, sondern hat auch eine Verbindung zur
harmonischen Analyse in der westlichen Forschungsastrologie.
