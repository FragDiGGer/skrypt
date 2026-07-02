// Klient serwisu dartscore dla frontu React/Vite (przeglądarka).
//
// Front najczęściej rozmawia z Twoim backendem FastAPI, w którym wpięte są
// endpointy dartscore (service/router.py). `baseUrl` ustaw na swój backend,
// np. przez zmienną Vite: VITE_DARTS_URL (import.meta.env.VITE_DARTS_URL).
//
// Używa natywnych `fetch` i `WebSocket` (bez zależności).

export interface DartPosition {
  angle_deg: number;
  radius_mm: number;
  x_mm: number;
  y_mm: number;
}

export interface Hit {
  sector: number | null; // 1..20, 25 (outer bull), 50 (bull) lub null (miss)
  ring: string;          // "single" | "triple" | "double" | "outer_bull" | "bull" | "miss"
  multiplier: number;
  score: number;
  confidence: number;
  near_boundary: boolean;
  position: DartPosition;
  cameras_used: string[];
}

export interface CalibrationStatus {
  calibrated: boolean;
  sector20_offset_deg?: number;
  cameras: string[];
  message?: string;
}

export type Frames = Record<string, string>; // camId -> base64 (PNG/JPEG)

/** Punkty odniesienia jednej kamery do kalibracji perspektywicznej. */
export interface CameraPoints {
  image_size: [number, number];            // [width, height] klatki natywnej
  points: Record<string, [number, number]>; // etykieta -> [x_px, y_px]; np. "20","6","3","11"
}
export type PointsCalibration = Record<string, CameraPoints>; // camId -> punkty

/** Kolejność klikania punktów w UI: double 20, 6, 3, 11 (osie góra/prawo/dół/lewo). */
export const REFERENCE_LABELS = ["20", "6", "3", "11"] as const;

/** Błąd serwisu z kodem HTTP (409 brak kalibracji, 422 niejednoznaczne, 503 kamera offline). */
export class DartsServiceError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`dartscore ${status}: ${detail}`);
    this.name = "DartsServiceError";
    this.status = status;
    this.detail = detail;
  }
}

export interface DartsClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
}

export class DartsClient {
  readonly baseUrl: string;
  private timeoutMs: number;

  constructor(opts: DartsClientOptions = {}) {
    const envUrl =
      typeof import.meta !== "undefined" ? (import.meta as any).env?.VITE_DARTS_URL : undefined;
    this.baseUrl = (opts.baseUrl || envUrl || "http://localhost:8000").replace(/\/$/, "");
    this.timeoutMs = opts.timeoutMs ?? 15000;
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) {
        throw new DartsServiceError(res.status, (data as any).detail ?? res.statusText);
      }
      return data as T;
    } finally {
      clearTimeout(t);
    }
  }

  /** Stan kalibracji. */
  calibrationStatus(): Promise<CalibrationStatus> {
    return this.request("GET", "/calibration/status");
  }

  /** Kalibracja automatyczna z klatek pustej tarczy (widok ~czołowy / syntetyk). */
  calibrate(frames: Frames): Promise<CalibrationStatus> {
    return this.request("POST", "/calibrate", { frames });
  }

  /**
   * Kalibracja perspektywiczna z klikanych punktów (ZALECANA dla realnych kamer
   * bocznych). Domyślnie 4 punkty: zewnętrzna krawędź double dla sektorów 20/6/3/11.
   */
  calibrateFromPoints(cameras: PointsCalibration): Promise<CalibrationStatus> {
    return this.request("POST", "/calibrate-points", { cameras });
  }

  /**
   * OPCJONALNIE: korekcja dystorsji obiektywu ze zdjęć szachownicy (per kamera).
   * Wykonaj PRZED calibrateFromPoints. `cameras`: camId -> lista klatek base64.
   */
  calibrateLens(
    cameras: Record<string, string[]>,
    patternSize: [number, number] = [9, 6],
  ): Promise<{ cameras: string[]; message: string }> {
    return this.request("POST", "/calibrate-lens", { cameras, pattern_size: patternSize });
  }

  /** Punktacja rzutu z klatek przed/po (camId -> base64). */
  scoreThrow(before: Frames, after: Frames): Promise<Hit> {
    return this.request("POST", "/score-throw", { before, after });
  }

  /**
   * Podgląd kalibracji: nakłada siatkę tarczy na klatkę danej kamery.
   * Zwraca obraz base64 (PNG) — pokaż go, by naocznie zweryfikować dopasowanie.
   */
  async calibrationPreview(cameraId: string, frame: string): Promise<string> {
    const res = await this.request<{ image: string }>("POST", "/calibration/preview", {
      camera_id: cameraId,
      frame,
    });
    return res.image;
  }

  /**
   * Subskrypcja trafień na żywo (WebSocket). Zwraca funkcję zamykającą.
   * Auto-reconnect co 1 s po zerwaniu, dopóki nie wywołasz close().
   */
  subscribeHits(onHit: (hit: Hit) => void, onError?: (e: unknown) => void): () => void {
    const wsUrl = this.baseUrl.replace(/^http/, "ws") + "/ws/hits";
    let closed = false;
    let ws: WebSocket;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (ev) => {
        try {
          onHit(JSON.parse(ev.data) as Hit);
        } catch (e) {
          onError?.(e);
        }
      };
      ws.onerror = (e) => onError?.(e);
      ws.onclose = () => {
        if (!closed) setTimeout(connect, 1000);
      };
    };
    connect();

    return () => {
      closed = true;
      ws?.close();
    };
  }
}

/**
 * Przechwyć bieżącą klatkę z elementu <video> (strumień kamery) jako base64 PNG.
 * Przydatne, gdy front pokazuje podgląd kamer i wysyła klatki do backendu.
 */
export function captureFrame(video: HTMLVideoElement): string {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Brak kontekstu 2D canvas");
  ctx.drawImage(video, 0, 0);
  // Zwracamy samo base64 (bez prefiksu data:) — backend przyjmuje oba warianty.
  return canvas.toDataURL("image/png").split(",", 2)[1];
}

/**
 * Zamroź bieżącą klatkę z <video> jako dataURL + wymiary natywne.
 * Używane w ekranie kalibracji: pokazujesz zdjęcie i zbierasz kliknięcia w px
 * natywnych (te same, w których backend dostaje klatki do punktacji).
 */
export function captureFrameDataUrl(video: HTMLVideoElement): {
  dataUrl: string;
  width: number;
  height: number;
} {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Brak kontekstu 2D canvas");
  ctx.drawImage(video, 0, 0);
  return { dataUrl: canvas.toDataURL("image/png"), width: canvas.width, height: canvas.height };
}
