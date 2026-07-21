# ElevenLabs Voice Agent + BaZi Fusion Analyse - Komplettanleitung

## Architektur-Ueberblick

```
ElevenLabs Voice Agent (Conversational AI)
    |
    |  POST /api/webhooks/chart  (JSON body, Bearer/API-Key Auth)
    v
Fly.io / Railway  (quissme-bazi-engine)
    |
    |  compute_bazi() + compute_western_chart() + compute_fusion_analysis()
    v
JSON Response -> Voice Agent liest Horoskop vor
```

---

## 1. API Keys & Secrets

### 1.1 Shared Secret generieren

```bash
# Sicheren 32-Byte-Hex-Key generieren
python3 -c "import secrets; print(secrets.token_hex(32))"
# Beispiel: a1b2c3d4e5f6...  (64 Zeichen)
```

Diesen Key an **zwei Stellen** konfigurieren:

### 1.2 Secret auf Fly.io setzen

```bash
flyctl secrets set ELEVENLABS_TOOL_SECRET="<dein-generierter-key>" -a quissme-bazi-engine
```

### 1.3 Secret auf Railway setzen (Alternative)

Railway Dashboard -> Project -> Variables:
```
ELEVENLABS_TOOL_SECRET = <dein-generierter-key>
SE_EPHE_PATH           = /app/ephe
PORT                   = 8080
```

---

## 2. ElevenLabs Agent Konfiguration

### 2.1 Agent erstellen

ElevenLabs Dashboard -> **Conversational AI** -> **Create Agent**

**Agent Settings:**
- Name: `Astro Berater` (oder frei waehlbar)
- Language: `German`
- Voice: nach Wahl (z.B. "Rachel", "Antoni")

### 2.2 System Prompt für den Agenten

Unter **Agent** -> **System Prompt** eintragen:

```
Du bist ein erfahrener Astrologe, der westliche und chinesische Astrologie verbindet.
Wenn der Nutzer sein Geburtsdatum nennt, rufe das Tool "get_horoscope" auf.
Frage auch nach der Geburtszeit (Stunde und Minute) - erklaere, dass die
Geburtszeit fuer ein praezises Horoskop wichtig ist, aber nicht zwingend noetig.
Frage optional nach dem Geburtsort fuer eine noch genauere Berechnung.

Wenn du die Daten hast, nutze das Tool und interpretiere die Ergebnisse:

1. Beginne mit dem westlichen Sternzeichen (Sonne + Mond)
2. Erklaere das chinesische Tierkreiszeichen und Element
3. Gehe auf den Tagesmeister ein (das persoenliche Element)
4. Beschreibe die Fusion-Analyse:
   - Der Harmonie-Index zeigt, wie gut westliche und oestliche Energien zusammenpassen
   - Erklaere das dominante Element aus beiden Systemen
   - Gib eine persoenliche Interpretation basierend auf der Fusion
5. Erwaehne retrograde Planeten, falls vorhanden

Sprich natuerlich und warm. Nutze die deutschen Elementnamen
(Holz, Feuer, Erde, Metall, Wasser). Vermeide technischen Jargon.
```

### 2.3 Tool definieren: "get_horoscope"

Unter **Agent** -> **Tools** -> **Add Tool** -> **Webhook**

**Tool-Name:** `get_horoscope`

**Tool-Beschreibung (fuer den Agent):**
```
Berechnet ein vollstaendiges Horoskop mit westlicher Astrologie (Sternzeichen,
Planeten), chinesischem BaZi (Vier Saeulen) und Fusion-Analyse (Wu-Xing
Harmonie) basierend auf dem Geburtsdatum. Optional kann eine Geburtszeit
und ein Geburtsort angegeben werden fuer hoehere Praezision.
```

**Webhook URL:**
```
https://quissme-bazi-engine.fly.dev/api/webhooks/chart
```

**Method:** `POST`

### 2.4 Tool-Parameter (Input Schema)

Unter dem Tool -> **Parameters** die folgenden Parameter definieren:

| Parameter   | Type     | Required | Beschreibung                                              |
|-------------|----------|----------|-----------------------------------------------------------|
| `birthDate` | `string` | Ja       | Geburtsdatum im Format YYYY-MM-DD                         |
| `birthTime` | `string` | Nein     | Geburtszeit im Format HH:MM (Standard: 12:00)             |
| `birthLat`  | `number` | Nein     | Breitengrad des Geburtsorts (Standard: 52.52 = Berlin)     |
| `birthLon`  | `number` | Nein     | Laengengrad des Geburtsorts (Standard: 13.405 = Berlin)    |
| `birthTz`   | `string` | Nein     | Zeitzone des Geburtsorts (Standard: Europe/Berlin)         |

**JSON Schema (falls ElevenLabs Raw-Schema verlangt):**

```json
{
  "type": "object",
  "properties": {
    "birthDate": {
      "type": "string",
      "description": "Geburtsdatum im Format YYYY-MM-DD",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    },
    "birthTime": {
      "type": "string",
      "description": "Geburtszeit im Format HH:MM. Falls nicht angegeben wird 12:00 verwendet.",
      "pattern": "^\\d{2}:\\d{2}$"
    },
    "birthLat": {
      "type": "number",
      "description": "Breitengrad des Geburtsorts in Grad. Standard: 52.52 (Berlin)"
    },
    "birthLon": {
      "type": "number",
      "description": "Laengengrad des Geburtsorts in Grad. Standard: 13.405 (Berlin)"
    },
    "birthTz": {
      "type": "string",
      "description": "Zeitzone z.B. Europe/Berlin, America/New_York. Standard: Europe/Berlin"
    }
  },
  "required": ["birthDate"]
}
```

### 2.5 Authentifizierung konfigurieren

Unter dem Tool -> **Authentication / Headers**:

**Option A: API Key Header (einfachste Methode)**
```
Header Name:  x-api-key
Header Value: <dein ELEVENLABS_TOOL_SECRET>
```

**Option B: Bearer Token**
```
Header Name:  Authorization
Header Value: Bearer <dein ELEVENLABS_TOOL_SECRET>
```

**Option C: ElevenLabs HMAC Signature (sicherste Methode)**

Falls ElevenLabs die eigene Signaturmethode unterstuetzt:
- Unter Tool -> **Secret** den gleichen Key eintragen
- ElevenLabs sendet dann automatisch den `elevenlabs-signature` Header
- Format: `t=<timestamp_ms>,v1=<hmac_sha256_hex>`

---

## 3. Vollstaendige API-Response Struktur

Der Webhook liefert folgende Daten an den Voice Agent:

```json
{
  "western": {
    "sunSign": "Loewe",
    "moonSign": "Skorpion",
    "sunSignEnglish": "Leo",
    "moonSignEnglish": "Scorpio",
    "ascendant": 185.42,
    "retrogradePlanets": ["Saturn", "Pluto"]
  },
  "eastern": {
    "yearAnimal": "Drache",
    "yearElement": "Holz",
    "monthAnimal": "Affe",
    "monthElement": "Metall",
    "dayAnimal": "Tiger",
    "dayElement": "Feuer",
    "dayMaster": "Bing",
    "hourAnimal": "Pferd",
    "hourElement": "Feuer"
  },
  "fusion": {
    "harmonyIndex": 0.72,
    "harmonyInterpretation": "Gute Harmonie",
    "cosmicState": 0.68,
    "westernDominantElement": "Feuer",
    "baziDominantElement": "Holz",
    "wuXingWestern": {
      "Holz": 0.25, "Feuer": 0.30, "Erde": 0.15,
      "Metall": 0.10, "Wasser": 0.20
    },
    "wuXingBazi": {
      "Holz": 0.35, "Feuer": 0.20, "Erde": 0.15,
      "Metall": 0.10, "Wasser": 0.20
    },
    "elementalComparison": {
      "Holz":   {"western": 0.25, "bazi": 0.35, "difference": -0.10},
      "Feuer":  {"western": 0.30, "bazi": 0.20, "difference":  0.10},
      "Erde":   {"western": 0.15, "bazi": 0.15, "difference":  0.00},
      "Metall": {"western": 0.10, "bazi": 0.10, "difference":  0.00},
      "Wasser": {"western": 0.20, "bazi": 0.20, "difference":  0.00}
    },
    "interpretation": "Harmonie-Index: 72%\nGute Harmonie\n..."
  },
  "summary": {
    "sternzeichen": "Loewe",
    "mondzeichen": "Skorpion",
    "chinesischesZeichen": "Holz Drache",
    "tagesmeister": "Feuer (Bing)",
    "harmonie": "72%",
    "dominantesElement": "West: Feuer, Ost: Holz"
  }
}
```

---

## 4. Umgebungsvariablen Checkliste

### Fly.io (fly.toml + Secrets)

| Variable                | Wo setzen          | Wert                          |
|-------------------------|--------------------|------------------------------ |
| `SE_EPHE_PATH`          | fly.toml `[env]`   | `/app/ephe`                   |
| `PORT`                  | fly.toml `[env]`   | `8080`                        |
| `ELEVENLABS_TOOL_SECRET`| `flyctl secrets`   | generierter 64-Hex-Zeichen Key |

### Railway

| Variable                | Wo setzen          | Wert                          |
|-------------------------|--------------------|------------------------------ |
| `SE_EPHE_PATH`          | Variables          | `/app/ephe`                   |
| `PORT`                  | Variables          | `8080`                        |
| `ELEVENLABS_TOOL_SECRET`| Variables          | generierter 64-Hex-Zeichen Key |

### ElevenLabs

| Einstellung            | Wo setzen                        | Wert                           |
|------------------------|----------------------------------|---------------------------------|
| Tool Secret / API Key  | Tool -> Headers -> `x-api-key`   | gleicher 64-Hex-Zeichen Key     |
| Webhook URL            | Tool -> URL                      | `https://quissme-bazi-engine.fly.dev/api/webhooks/chart` |

---

## 5. Haeufige Geburtsort-Koordinaten

Fuer den Voice Agent - der Nutzer sagt den Stadtnamen, der Agent mappt:

| Stadt       | Lat     | Lon     | Timezone          |
|-------------|---------|---------|-------------------|
| Berlin      | 52.52   | 13.405  | Europe/Berlin     |
| Muenchen    | 48.14   | 11.58   | Europe/Berlin     |
| Hamburg     | 53.55   | 9.99    | Europe/Berlin     |
| Koeln       | 50.94   | 6.96    | Europe/Berlin     |
| Frankfurt   | 50.11   | 8.68    | Europe/Berlin     |
| Wien        | 48.21   | 16.37   | Europe/Vienna     |
| Zuerich     | 47.38   | 8.54    | Europe/Zurich     |
| London      | 51.51   | -0.13   | Europe/London     |
| New York    | 40.71   | -74.01  | America/New_York  |
| Los Angeles | 34.05   | -118.24 | America/Los_Angeles |

---

## 6. Testen

### Lokaler Test (curl)

```bash
curl -X POST https://quissme-bazi-engine.fly.dev/api/webhooks/chart \
  -H "Content-Type: application/json" \
  -H "x-api-key: <dein-secret>" \
  -d '{
    "birthDate": "1990-05-15",
    "birthTime": "14:30",
    "birthLat": 52.52,
    "birthLon": 13.405,
    "birthTz": "Europe/Berlin"
  }'
```

### Health Check

```bash
curl https://quissme-bazi-engine.fly.dev/health
# -> {"status": "healthy"}
```
