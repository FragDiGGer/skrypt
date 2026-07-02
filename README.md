# dartscore — detekcja i punktacja tarczy dart z 3 kamer

Niezależny, samodzielny moduł wizyjny (bez zależności od Autodarts ani innej
gotowej platformy), który:

1. **ustala orientację tarczy** przez wykrycie sektora **20** na pierścieniu
   numerycznym (OCR cyfr 1–20) — sektor 20 to punkt odniesienia, wszystkie
   pozostałe sektory wyznaczane są obliczeniowo co 18°,
2. z klatek **3 kamer bocznych** (ustawienie typu Autodarts) wyznacza pozycję
   końcówki grota lotki, uzgadnia ją między kamerami i **zlicza punkty**.

Moduł jest gotowy do wpięcia w aplikację webową: logika wizyjna (pakiet
`dartscore`) jest oddzielona od warstwy transportu (pakiet `service`, FastAPI
HTTP/WebSocket), więc backend Node/JS woła prosty serwis i dostaje wynik JSON.

## Status i zakres

- **Rdzeń w pełni działający i przetestowany:** geometria, punktacja
  (kąt, promień → sektor/mnożnik/punkty), kalibracja orientacji, fuzja z kamer,
  API. 37 testów jednostkowych (w tym przypadki brzegowe granic sektorów i
  pierścieni).
- **Detekcja lotki i OCR jako rozszerzalny szkielet** — działa end-to-end na
  klatkach syntetycznych; progi i parametry do dostrojenia po dostarczeniu
  realnych nagrań z kamer (interfejsy są wtykowe).

## Struktura projektu

```
dartscore/              # rdzeń: czysta wizja + logika (bez HTTP)
  config.py             # loader board.yaml / cameras.yaml (jedyne źródło wymiarów)
  geometry.py           # matematyka polar <-> sektor
  scoring.py            # (kąt, promień) -> Hit  [rdzeń, testowany]
  errors.py             # typowane wyjątki domenowe
  calibration/          # środek + orientacja (OCR "20") + homografia + zapis
  detection/            # różnica tła, wyznaczenie grota, stabilizacja
  fusion/               # uzgodnienie detekcji z 3 kamer + pewność
  pipeline.py           # orkiestracja: klatki(3) -> Hit
service/                # warstwa transportu (FastAPI: REST + WebSocket)
config/                 # board.yaml (geometria), cameras.example.yaml
examples/               # generator syntetyczny + demo end-to-end
tests/                  # testy jednostkowe (priorytet: mapowanie na punkty)
```

## Instalacja

```bash
pip install -e .[dev,api]
# lub minimalnie (bez serwisu): pip install -e .[dev]
```

W środowiskach bez GUI zamiast `opencv-python` można użyć
`opencv-python-headless`.

Opcjonalny backend OCR Tesseract: `pip install -e .[ocr-tesseract]` (wymaga
binarki `tesseract` w systemie). Domyślny rozpoznawacz cyfr (`TemplateMatcher`)
nie wymaga żadnych zależności systemowych i działa offline.

## Szybki start (demo bez sprzętu)

```bash
python -m examples.mock_throw
```

Generuje syntetyczne klatki tarczy dla 3 kamer, kalibruje (wykrywa „20”),
symuluje rzut w triple 20 i wypisuje wynik:

```json
{"sector": 20, "ring": "triple", "score": 60}
```

## Testy

```bash
pytest -q
```

Pokrywają m.in.: środki wszystkich 20 sektorów, granice między sektorami
(deterministyczny tie-break), granicę `double`/`miss`, granice `bull`/`25`/single,
mnożniki triple/double, fuzję (mediana, odrzucanie outlierów, occlusion) oraz
dymnie kalibrację i pełny pipeline na syntetyku.

## Kalibracja (jednorazowa/okresowa)

Tarcza i kamery są sztywno zamontowane, więc kalibrację liczymy raz i zapisujemy
do pliku (`calibration.json`), by nie przeliczać jej przy każdym rzucie.

Wejściem są klatki **pustej tarczy** z każdej kamery. Kalibracja:

1. wykrywa środek i promień pola punktowego (skala px↔mm),
2. rozpoznaje cyfrę **20** na pierścieniu numerycznym i wyznacza jej kąt
   względem środka → `sector20_offset_deg` (offset orientacji, mediana z kamer),
3. buduje homografię obraz→płaszczyzna tarczy (mm) per kamera.

Programowo:

```python
from dartscore.config import load_board_config
from dartscore.calibration.board_calibrator import BoardCalibrator
from dartscore.calibration.store import save_calibration

board = load_board_config()
frames = {"cam0": img0, "cam1": img1, "cam2": img2}   # klatki pustej tarczy (BGR)
calib = BoardCalibrator(board).calibrate(frames)
save_calibration(calib, "calibration.json")
```

> Uwaga dla kamer bocznych (perspektywa): domyślny kalibrator zakłada widok
> zbliżony do czołowego (homografia podobieństwa). Dla mocno skośnych ujęć
> podmień homografię na wyznaczoną z punktów odniesienia — patrz
> `dartscore/calibration/homography.py::find_homography_image_to_board`.

## Konfiguracja (bez „magic numbers”)

Wszystkie wymiary tarczy i tolerancje są w `config/board.yaml` (promienie
pierścieni w mm, kolejność sektorów, offset orientacji, tolerancje granic).
Konfigurację kamer opisuje `config/cameras.yaml` (skopiuj z
`cameras.example.yaml`): id/indeks, rozdzielczość, azymut, minimalna liczba
kamer dla pewnego trafienia.

## Wpięcie do aplikacji webowej (React/Vite + FastAPI)

Stack docelowy: **frontend React/Vite** + **backend Python/FastAPI**. Ponieważ
`dartscore` też jest w Pythonie, wpinasz go **wprost do swojego backendu FastAPI**
— bez osobnego mikroserwisu. Pełny przewodnik: **`integration/react/README.md`**.

**Backend (FastAPI) — wepnij router:**

```python
from service.router import create_darts_router
app.include_router(create_darts_router(prefix="/darts"))
```

Endpointy (obrazy jako base64 w JSON):

| Metoda | Ścieżka                     | Wejście                                  | Wyjście            |
|--------|-----------------------------|------------------------------------------|--------------------|
| POST   | `/darts/calibrate-points`   | `{cameras:{camId:{image_size,points}}}` | status kalibracji  |
| POST   | `/darts/calibrate`          | `{frames: {camId: base64}}` (auto)       | status kalibracji  |
| GET    | `/darts/calibration/status` | —                                        | stan kalibracji    |
| POST   | `/darts/score-throw`        | `{before: {...}, after: {...}}`         | `Hit` JSON         |
| WS     | `/darts/ws/hits`            | (utrzymywane połączenie)                 | strumień `Hit`     |

Dla realnych kamer bocznych (perspektywa) używaj **`/darts/calibrate-points`**
(4 punkty: double 20/6/3/11) — patrz `integration/react/README.md`.

**Frontend (React/Vite) — użyj klienta** `integration/react/dartsClient.ts`
(+ hook `useDartHits.ts`, + `captureFrame(video)` do pobrania klatki z `<video>`):

```tsx
import { DartsClient } from "./lib/dartsClient";
const darts = new DartsClient();               // czyta VITE_DARTS_URL
const hit = await darts.scoreThrow(before, after);   // { sector, ring, score, ... }
```

> **Pliki do podesłania Claude Code** (dla apki React/FastAPI): backend —
> `service/router.py`, `service/schemas.py`; front — `integration/react/*`.

**Alternatywa — osobny proces** (gdy nie chcesz wpinać routera): uruchom
`uvicorn service.api:app` (ma włączony CORS dla Vite) albo `docker compose up`.

Każde `POST /score-throw` rozsyła wynik również do klientów `/ws/hits`.

### Użycie jako biblioteka (bez HTTP)

Cała logika działa też bez serwisu — pipeline jest czystym API domenowym:

```python
from dartscore.config import load_board_config, load_cameras_config
from dartscore.calibration.store import load_calibration
from dartscore.pipeline import ThrowPipeline

pipeline = ThrowPipeline(load_board_config(), load_calibration("calibration.json"),
                         cameras=load_cameras_config())
result = pipeline.process_pair(before_frames, after_frames)   # dict camId -> BGR
print(result.hit.to_score_dict())      # {"sector": 20, "ring": "triple", "score": 60}
```

## Formy wyniku (`Hit`)

Zgodne ze specyfikacją:

```json
{ "sector": 20,   "ring": "triple",     "score": 60 }
{ "sector": 25,   "ring": "outer_bull", "score": 25 }
{ "sector": 50,   "ring": "bull",       "score": 50 }
{ "sector": null, "ring": "miss",       "score": 0  }
```

Pełny obiekt zawiera dodatkowo `multiplier`, `confidence`, `near_boundary`,
`position` (kąt/promień/xy w mm) oraz `cameras_used`.

## Obsługa błędów

Wyjątki domenowe (`dartscore/errors.py`) mapowane w serwisie na kody HTTP:

| Wyjątek            | Kiedy                                   | HTTP |
|--------------------|-----------------------------------------|------|
| `NotCalibrated`    | punktacja przed kalibracją              | 409  |
| `BoardNotDetected` | brak tarczy/cyfry „20” na obrazie       | 409  |
| `CameraOffline`    | brak klatki z kamery                    | 503  |
| `AmbiguousHit`     | za mało zgodnych kamer / duży rozrzut   | 422  |

## Metoda tip detection i triangulacji (skrót)

- **Izolacja nowej lotki:** różnica względem tła sprzed rzutu — wcześniej wbite
  lotki nie wpływają na detekcję.
- **Grot:** dopasowanie osi trzonka (PCA / `fitLine`, subpikselowo) i wybór
  skrajnego punktu bliższego środkowi tarczy; pewność z wydłużenia sylwetki.
- **Occlusion:** kamera bez detekcji jest pomijana; pozycję wyznaczają pozostałe.
- **Fuzja:** mediana + odrzucanie outlierów + ważenie pewnością → jedna pozycja
  (kąt, promień) i metryka pewności.

## Świadome ograniczenia (do dostrojenia na realnych danych)

- Parallax grota nad powierzchnią tarczy przy kamerach bocznych daje niewielki
  bias radialny per kamera; łagodzony przez fuzję — w kolejnej iteracji można
  dodać model wysokości grota.
- Progi detekcji (różnica tła, kontur) i szablony OCR są dostrojone do renderu
  syntetycznego; wymagają kalibracji po dostarczeniu nagrań z realnych kamer.
