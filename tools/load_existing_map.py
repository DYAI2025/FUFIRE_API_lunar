"""
Laedt die bestehende AFFINITY_MAP aus dem Astro-Noctum Repo
(TypeScript) und parst sie in ein Python-Dict.

Falls das Repo nicht lokal verfuegbar ist, enthaelt dieses Modul
eine eingebettete Kopie der handgeschriebenen Map als Ground Truth.
"""

# Eingebettete Kopie der handgeschriebenen AFFINITY_MAP
# aus Astro-Noctum src/lib/fusion-ring/affinity-map.ts
# Stand: 2026-03-07
EXISTING_AFFINITY_MAP: dict[str, list[float]] = {
    # === DOMAIN-LEVEL (Fallback) ===
    "love":       [0,  .1, 0,  .3, 0,  0,  .3, .3, 0,  0,  0,  0  ],
    "emotion":    [0,  .2, 0,  .4, .1, 0,  .1, .2, 0,  0,  0,  0  ],
    "social":     [0,  0,  .1, .1, .1, 0,  .3, 0,  0,  0,  .3, 0  ],
    "instinct":   [.3, 0,  0,  0,  0,  0,  0,  .3, .2, .1, 0,  .1 ],
    "cognition":  [0,  0,  .4, 0,  0,  .3, 0,  0,  .2, .1, 0,  0  ],
    "leadership": [.1, 0,  0,  0,  .3, 0,  0,  0,  0,  .4, .1, 0  ],
    "freedom":    [.2, 0,  0,  0,  0,  0,  0,  0,  .5, .1, .2, 0  ],
    "spiritual":  [0,  0,  0,  0,  0,  0,  0,  .2, .2, 0,  0,  .6 ],
    "sensory":    [0,  .5, 0,  0,  0,  0,  0,  .3, 0,  0,  0,  .2 ],
    "creative":   [0,  0,  .2, 0,  .4, 0,  .1, 0,  0,  0,  .2, .1 ],

    # === KEYWORD-LEVEL (Praezision) ===
    "physical_touch":      [0,  .2, 0,  0,  0,  0,  0,  .6, 0,  0,  0,  .2 ],
    "harmony":             [0,  0,  0,  .1, 0,  0,  .7, 0,  0,  0,  .2, 0  ],
    "pack_loyalty":        [0,  0,  0,  .2, 0,  0,  .1, 0,  0,  0,  .5, .2 ],
    "primal_sense":        [.5, 0,  0,  0,  0,  0,  0,  .4, 0,  0,  0,  .1 ],
    "gut_feeling":         [.1, 0,  0,  0,  0,  0,  0,  .2, 0,  0,  0,  .7 ],
    "body_awareness":      [0,  .4, 0,  0,  0,  0,  0,  .3, 0,  0,  0,  .3 ],
    "servant_leader":      [0,  0,  0,  .1, 0,  .2, 0,  0,  0,  .5, 0,  .2 ],
    "charisma":            [0,  0,  0,  0,  .6, 0,  .1, 0,  .2, .1, 0,  0  ],
    "analytical":          [0,  0,  .3, 0,  0,  .5, 0,  0,  .1, .1, 0,  0  ],
    "community":           [0,  0,  0,  .1, 0,  0,  .2, 0,  0,  0,  .6, .1 ],
    "passionate":          [.1, 0,  0,  0,  .2, 0,  0,  .5, 0,  0,  0,  .2 ],
    "togetherness":        [0,  0,  0,  .3, 0,  0,  .4, 0,  0,  0,  .2, .1 ],
    "expression":          [0,  0,  .2, 0,  .5, 0,  0,  0,  .2, .1, 0,  0  ],
    "protective":          [.2, 0,  0,  .4, 0,  0,  0,  0,  0,  .3, 0,  .1 ],
    "independence":        [.2, 0,  0,  0,  0,  0,  0,  0,  .5, .1, .2, 0  ],
    "sensory_connection":  [0,  .4, 0,  .1, 0,  0,  0,  .3, 0,  0,  0,  .2 ],
    "physical_expression": [.1, .1, 0,  0,  .2, 0,  0,  .4, 0,  0,  0,  .2 ],
}


def get_existing(keyword: str) -> list[float] | None:
    """Hole bestehende Map-Zeile. None wenn nicht vorhanden."""
    return EXISTING_AFFINITY_MAP.get(keyword)
