# Integracja z aplikacją Node.js

Serwis wizyjny `dartscore` (Python/FastAPI) działa jako **osobny proces**, a Twoja
aplikacja Node.js woła go po HTTP/WebSocket. W tym katalogu jest gotowy klient.

> **Pliki do podesłania Claude Code** (żeby wpiął to w Twoją apkę Node):
> `integration/node/dartsClient.js`, ten `README.md` oraz — dla dokładnego
> kontraktu JSON — `service/schemas.py` i `service/api.py` z korzenia repo.

## 1. Uruchom serwis wizyjny

Najprościej przez Docker (z korzenia repo):

```bash
docker compose up --build
# serwis nasłuchuje na http://localhost:8000
```

Bez Dockera:

```bash
pip install -e .[api]
uvicorn service.api:app --host 0.0.0.0 --port 8000
```

## 2. Podłącz klienta w Node

```bash
npm install ws          # klient używa 'ws' do WebSocketu (Node 18+ ma globalne fetch)
```

```js
import { DartsClient, fileToBase64 } from "./integration/node/dartsClient.js";

const darts = new DartsClient(); // czyta DARTS_SERVICE_URL (domyślnie http://localhost:8000)

// Kalibracja raz (klatki pustej tarczy z 3 kamer):
await darts.calibrate({
  cam0: await fileToBase64("empty_cam0.png"),
  cam1: await fileToBase64("empty_cam1.png"),
  cam2: await fileToBase64("empty_cam2.png"),
});

// Trafienia na żywo do frontu:
darts.subscribeHits((hit) => {
  console.log("trafienie:", hit); // { sector:20, ring:"triple", score:60, confidence:0.92, ... }
  // io.emit("dart-hit", hit);     // np. Socket.IO / SSE
});

// Pojedynczy rzut (klatki przed/po jako camId -> base64):
const hit = await darts.scoreThrow(beforeFrames, afterFrames);
```

## 3. API klienta

| Metoda | Opis |
|--------|------|
| `calibrationStatus()` | stan kalibracji |
| `calibrate(frames)` | kalibracja z klatek pustej tarczy (`{camId: base64}`) |
| `scoreThrow(before, after)` | punktacja rzutu → `Hit` |
| `subscribeHits(onHit, opts)` | strumień trafień (WebSocket, auto-reconnect) |
| `fileToBase64(path)` / `bufferToBase64(buf)` | pomocnicze konwersje obrazu |

Błędy serwisu rzucane są jako `DartsServiceError` z polem `.status`:
`409` (brak kalibracji/tarczy), `422` (pozycja niejednoznaczna), `503` (kamera offline).

## Konfiguracja

- `DARTS_SERVICE_URL` — adres serwisu wizyjnego (dla klienta Node).
- `DARTSCORE_CALIBRATION` — ścieżka pliku kalibracji po stronie serwisu Python.
- Obrazy przesyłane jako **base64** (PNG/JPEG), z prefiksem `data:` lub bez.
