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

| Metoda | Ścieżka                     | Wejście                                    | Wyjście            |
|--------|-----------------------------|--------------------------------------------|--------------------|
| POST   | `/darts/calibrate-points`   | `{cameras:{camId:{image_size,points}}}`   | status kalibracji  |
| POST   | `/darts/calibrate`          | `{frames: {camId: base64}}` (auto, ~czoło) | status kalibracji  |
| GET    | `/darts/calibration/status` | —                                          | stan kalibracji    |
| POST   | `/darts/score-throw`        | `{before:{...}, after:{...}}`             | `Hit` JSON         |
| WS     | `/darts/ws/hits`            | (utrzymywane połączenie)                   | strumień `Hit`     |

**Kalibracja perspektywiczna (zalecana dla realnych kamer bocznych):**
`/darts/calibrate-points` — dla każdej kamery podajesz 4 punkty (piksele) =
zewnętrzna krawędź double sektorów **20, 6, 3, 11**. Moduł liczy homografię
perspektywiczną (kod: `dartscore/calibration/point_calibrator.py`). Auto
`/darts/calibrate` (OCR „20") działa dobrze tylko dla widoku ~czołowego/syntetyku.

Instalacja zależności modułu w środowisku backendu:
`pip install -e .[api]` (w produkcji bez GUI użyj `opencv-python-headless`).

Ścieżkę pliku kalibracji ustawia `DARTSCORE_CALIBRATION` (domyślnie
`calibration.json`). Kalibrujesz raz — router wczytuje ją przy starcie.

> Uwaga o adresie: klient używa ścieżek względem `baseUrl`. Jeśli wpinasz router
> z `prefix="/darts"`, ustaw `VITE_DARTS_URL=http://host:port/darts`.

> Alternatywa (jeśli wolisz osobny proces): uruchom `uvicorn service.api:app`
> i wskaż front na ten adres. Ten wariant ma już włączony CORS dla Vite
> (`http://localhost:5173`, nadpisywalny przez `DARTS_CORS_ORIGINS`).

## 2. Frontend (React/Vite) — użyj klienta

Skopiuj `dartsClient.ts`, `useDartHits.ts` (oraz opcjonalnie `DartsCalibrator.tsx`
i `DartsPanel.tsx`) do swojego projektu (np. `src/lib/`). Adres backendu w `.env`:

```
VITE_DARTS_URL=http://localhost:8000        # lub .../darts jeśli router ma prefix
```

Kalibracja perspektywiczna (4 punkty) i pojedynczy rzut:

```tsx
import { DartsClient, captureFrame } from "./lib/dartsClient";

const darts = new DartsClient(); // czyta VITE_DARTS_URL

// 4 punkty na kamerę: double 20/6/3/11 (piksele natywne klatki):
await darts.calibrateFromPoints({
  cam0: { image_size: [1280, 720], points: { "20": [x,y], "6": [x,y], "3": [x,y], "11": [x,y] } },
  cam1: { /* ... */ },
  cam2: { /* ... */ },
});

const hit = await darts.scoreThrow(before, {
  cam0: captureFrame(video0), cam1: captureFrame(video1), cam2: captureFrame(video2),
}); // { sector, ring, score, ... }
```

Gotowy ekran klikania: **`DartsCalibrator.tsx`** (klikasz 20/6/3/11 na każdej
kamerze, on sam woła `calibrateFromPoints`). Zintegrowany w `DartsPanel.tsx`
pod przyciskiem „Kalibruj (4 punkty)".

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

## Gotowy komponent (opcjonalnie)

`DartsPanel.tsx` to samowystarczalny przykład: podgląd 3 kamer, kalibracja
4-punktowa (przez `DartsCalibrator.tsx`), „klatka PRZED" + „Policz rzut" oraz
tablica trafień na żywo (`useDartHits`). Skopiuj i podmień style/logikę pod siebie.

```tsx
import { DartsPanel } from "./lib/DartsPanel";
export default function App() {
  return <DartsPanel />;   // albo <DartsPanel deviceIds={[id0, id1, id2]} />
}
```

## Weryfikacja i dystorsja

- **Podgląd kalibracji:** po zapisaniu punktów `DartsCalibrator` woła
  `POST /darts/calibration/preview` i pokazuje klatkę z nałożoną **siatką tarczy**
  (pierścienie + sektory + numery). Siatka powinna pokrywać się z realną tarczą —
  jeśli nie, „Popraw punkty".
- **Korekcja dystorsji (opcjonalna):** dla kamer szerokokątnych (beczka) zrób
  10–20 zdjęć szachownicy z każdej kamery i wywołaj `client.calibrateLens({cam0:[...], ...})`
  **przed** kalibracją 4-punktową. Moduł prostuje obraz przed detekcją i kalibracją
  (parametry zapisywane w `lens.json`; endpoint `POST /darts/calibrate-lens`).

## 3. Błędy

Metody rzucają `DartsServiceError` z polem `.status`:
`409` (brak kalibracji/tarczy), `422` (pozycja niejednoznaczna), `503` (kamera offline).

## Pliki do podesłania Claude Code (dla apki React/FastAPI)

- Backend: `service/router.py`, `service/schemas.py`,
  `dartscore/calibration/point_calibrator.py`,
- Front: `integration/react/dartsClient.ts`, `useDartHits.ts`,
  `DartsCalibrator.tsx`, `DartsPanel.tsx`,
- ten `README.md`.
