# Integracja z React/Vite + backend FastAPI

Twój stack to **frontend React/Vite** + **backend Python/FastAPI**. Ponieważ
moduł wizyjny `dartscore` też jest w Pythonie, **wpinasz go wprost do swojego
backendu FastAPI** — bez osobnego mikroserwisu i bez pośrednika Node.

```
[ React/Vite ] --HTTP/WS--> [ Twój backend FastAPI + router dartscore ] --import--> dartscore
```

## 1. Backend (FastAPI) — wepnij router

W swojej aplikacji FastAPI:

```python
from fastapi import FastAPI
from service.router import create_darts_router  # z tego repo (dartscore)

app = FastAPI()
# ... Twoje endpointy ...
app.include_router(create_darts_router(prefix="/darts"))
```

Dostajesz od razu:

| Metoda | Ścieżka                    | Wejście                          | Wyjście            |
|--------|----------------------------|----------------------------------|--------------------|
| POST   | `/darts/calibrate`         | `{frames: {camId: base64}}`      | status kalibracji  |
| GET    | `/darts/calibration/status`| —                                | stan kalibracji    |
| POST   | `/darts/score-throw`       | `{before:{...}, after:{...}}`    | `Hit` JSON         |
| WS     | `/darts/ws/hits`           | (utrzymywane połączenie)         | strumień `Hit`     |

Instalacja zależności modułu w środowisku backendu:
`pip install -e .[api]` (w produkcji bez GUI użyj `opencv-python-headless`).

Ścieżkę pliku kalibracji ustawia `DARTSCORE_CALIBRATION` (domyślnie
`calibration.json`). Kalibrujesz raz — router wczytuje ją przy starcie.

> Alternatywa (jeśli wolisz osobny proces): uruchom `uvicorn service.api:app`
> i wskaż front na ten adres. Ten wariant ma już włączony CORS dla Vite
> (`http://localhost:5173`, nadpisywalny przez `DARTS_CORS_ORIGINS`).

## 2. Frontend (React/Vite) — użyj klienta

Skopiuj `dartsClient.ts` i `useDartHits.ts` do swojego projektu (np. `src/lib/`).
Adres backendu ustaw w `.env` Vite:

```
VITE_DARTS_URL=http://localhost:8000
```

Kalibracja i pojedynczy rzut:

```tsx
import { DartsClient, captureFrame } from "./lib/dartsClient";

const darts = new DartsClient(); // czyta VITE_DARTS_URL

// Klatki z podglądów kamer (elementy <video> ze strumieniem):
const grab = () => ({
  cam0: captureFrame(video0),
  cam1: captureFrame(video1),
  cam2: captureFrame(video2),
});

await darts.calibrate(grab());                 // raz, na pustej tarczy
const hit = await darts.scoreThrow(before, grab()); // { sector, ring, score, ... }
```

Trafienia na żywo (hook):

```tsx
import { useDartHits } from "./lib/useDartHits";

function Scoreboard() {
  const { lastHit, hits, connected } = useDartHits();
  return (
    <div>
      <span>{connected ? "● live" : "○ offline"}</span>
      {lastHit && <h2>{lastHit.score} pkt ({lastHit.ring} {lastHit.sector})</h2>}
      <ul>{hits.map((h, i) => <li key={i}>{h.score} — {h.ring} {h.sector}</li>)}</ul>
    </div>
  );
}
```

## 3. Błędy

Metody rzucają `DartsServiceError` z polem `.status`:
`409` (brak kalibracji/tarczy), `422` (pozycja niejednoznaczna), `503` (kamera offline).

## Pliki do podesłania Claude Code (dla apki React/FastAPI)

- Backend: `service/router.py`, `service/schemas.py`,
- Front: `integration/react/dartsClient.ts`, `integration/react/useDartHits.ts`,
- ten `README.md`.
