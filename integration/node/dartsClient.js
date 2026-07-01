// Klient serwisu wizyjnego dartscore dla aplikacji Node.js.
//
// Serwis (Python/FastAPI) działa jako osobny proces/kontener; ten moduł opakowuje
// wywołania HTTP/WebSocket, żeby Twój backend Node miał gotowe funkcje.
//
// Wymagania:
//   * Node 18+ (globalne `fetch`),
//   * pakiet `ws` do WebSocketu:  npm install ws
//
// Konfiguracja adresu serwisu: zmienna środowiskowa DARTS_SERVICE_URL
// (domyślnie http://localhost:8000) lub argument konstruktora.
//
// Przykład na dole pliku (uruchom: node integration/node/dartsClient.js --demo-help).

import { readFile } from "node:fs/promises";
import WebSocket from "ws";

/** Błąd domenowy serwisu dartscore (z kodem HTTP i treścią z serwera). */
export class DartsServiceError extends Error {
  constructor(status, detail) {
    super(`dartscore ${status}: ${detail}`);
    this.name = "DartsServiceError";
    this.status = status;   // 409 = brak kalibracji/tarczy, 422 = niejednoznaczne, 503 = kamera offline
    this.detail = detail;
  }
}

export class DartsClient {
  /**
   * @param {object} [opts]
   * @param {string} [opts.baseUrl] - adres serwisu; domyślnie DARTS_SERVICE_URL lub http://localhost:8000
   * @param {number} [opts.timeoutMs] - timeout żądań HTTP (domyślnie 15000)
   */
  constructor(opts = {}) {
    this.baseUrl = (opts.baseUrl || process.env.DARTS_SERVICE_URL || "http://localhost:8000").replace(/\/$/, "");
    this.timeoutMs = opts.timeoutMs ?? 15000;
  }

  async _request(method, path, body) {
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
        throw new DartsServiceError(res.status, data.detail ?? res.statusText);
      }
      return data;
    } finally {
      clearTimeout(t);
    }
  }

  /** Stan kalibracji: { calibrated, sector20_offset_deg, cameras, message }. */
  async calibrationStatus() {
    return this._request("GET", "/calibration/status");
  }

  /**
   * Kalibracja z klatek pustej tarczy.
   * @param {Record<string,string>} frames - mapa camId -> obraz base64 (PNG/JPEG).
   * @returns {Promise<object>} status kalibracji + wykryty offset sektora 20.
   */
  async calibrate(frames) {
    return this._request("POST", "/calibrate", { frames });
  }

  /**
   * Punktacja rzutu z klatek przed/po trafieniu.
   * @param {Record<string,string>} before - camId -> base64 (stan sprzed rzutu).
   * @param {Record<string,string>} after  - camId -> base64 (po trafieniu).
   * @returns {Promise<object>} Hit: { sector, ring, multiplier, score, confidence, position, cameras_used }.
   */
  async scoreThrow(before, after) {
    return this._request("POST", "/score-throw", { before, after });
  }

  /**
   * Subskrypcja trafień na żywo (WebSocket /ws/hits).
   * @param {(hit: object) => void} onHit - callback wywoływany dla każdego trafienia.
   * @param {object} [opts]
   * @param {(err: Error) => void} [opts.onError]
   * @param {boolean} [opts.reconnect=true] - automatyczne wznawianie połączenia.
   * @returns {{ close: () => void }} uchwyt do zamknięcia subskrypcji.
   */
  subscribeHits(onHit, opts = {}) {
    const { onError, reconnect = true } = opts;
    const wsUrl = this.baseUrl.replace(/^http/, "ws") + "/ws/hits";
    let closedByUser = false;
    let ws;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      ws.on("message", (raw) => {
        try {
          onHit(JSON.parse(raw.toString()));
        } catch (e) {
          onError?.(e);
        }
      });
      ws.on("error", (e) => onError?.(e));
      ws.on("close", () => {
        if (!closedByUser && reconnect) setTimeout(connect, 1000);
      });
    };
    connect();

    return {
      close: () => {
        closedByUser = true;
        ws?.close();
      },
    };
  }
}

/** Zamień plik obrazu z dysku na base64 (do kalibracji / testów). */
export async function fileToBase64(path) {
  const buf = await readFile(path);
  return buf.toString("base64");
}

/** Zamień Bufor (np. klatkę z kamery) na base64. */
export function bufferToBase64(buf) {
  return Buffer.from(buf).toString("base64");
}

// --- Przykład użycia (nie wykonuje żądań; pokazuje wzorzec) -----------------
// import { DartsClient, fileToBase64 } from "./dartsClient.js";
//
// const darts = new DartsClient();                 // DARTS_SERVICE_URL lub localhost:8000
//
// // 1) Kalibracja (raz, klatki pustej tarczy):
// await darts.calibrate({
//   cam0: await fileToBase64("empty_cam0.png"),
//   cam1: await fileToBase64("empty_cam1.png"),
//   cam2: await fileToBase64("empty_cam2.png"),
// });
//
// // 2) Trafienia na żywo -> przekaż do frontu (np. Socket.IO / SSE):
// const sub = darts.subscribeHits((hit) => {
//   console.log("trafienie:", hit);            // { sector:20, ring:"triple", score:60, ... }
//   // io.emit("dart-hit", hit);
// });
//
// // 3) Pojedynczy rzut (klatki przed/po):
// const hit = await darts.scoreThrow(beforeFrames, afterFrames);
//
// // sub.close();  // gdy kończysz

if (process.argv.includes("--demo-help")) {
  console.log("dartsClient.js — importuj DartsClient i użyj calibrate / scoreThrow / subscribeHits.");
  console.log("Adres serwisu:", process.env.DARTS_SERVICE_URL || "http://localhost:8000");
}
