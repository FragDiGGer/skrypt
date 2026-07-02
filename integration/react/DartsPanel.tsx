// Przykładowy, samowystarczalny komponent React do dart-scoringu.
//
// Pokazuje podgląd 3 kamer, kalibrację (na pustej tarczy), rejestrację klatki
// "przed" i policzenie rzutu ("po") oraz tablicę trafień na żywo (WebSocket).
//
// To materiał POGLĄDOWY — skopiuj do swojego projektu (np. src/components/) i
// dostosuj wygląd/logikę. Zależności: dartsClient.ts + useDartHits.ts (obok).
//
// Wybór kamer: domyślnie bierze pierwsze 3 urządzenia wideo. Możesz podać własne
// identyfikatory przez prop `deviceIds` (kolejność = cam0, cam1, cam2).

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  DartsClient,
  DartsServiceError,
  captureFrame,
  captureFrameDataUrl,
  type Frames,
  type Hit,
} from "./dartsClient";
import { DartsCalibrator, type FrozenFrame } from "./DartsCalibrator";
import { useDartHits } from "./useDartHits";

const CAM_IDS = ["cam0", "cam1", "cam2"] as const;

export interface DartsPanelProps {
  client?: DartsClient;
  deviceIds?: string[]; // opcjonalnie: konkretne kamery w kolejności cam0..cam2
}

export function DartsPanel({ client, deviceIds }: DartsPanelProps) {
  const darts = useRef(client ?? new DartsClient()).current;
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([null, null, null]);
  const streamsRef = useRef<MediaStream[]>([]);

  const [status, setStatus] = useState("Uruchamianie kamer…");
  const [calibrated, setCalibrated] = useState(false);
  const [before, setBefore] = useState<Frames | null>(null);
  const [busy, setBusy] = useState(false);
  const [frozen, setFrozen] = useState<Record<string, FrozenFrame> | null>(null);

  const { lastHit, hits, connected } = useDartHits(darts);

  // --- kamery -------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const all = await navigator.mediaDevices.enumerateDevices();
        const cams = all.filter((d) => d.kind === "videoinput");
        for (let i = 0; i < 3; i++) {
          const id = deviceIds?.[i] ?? cams[i]?.deviceId;
          const stream = await navigator.mediaDevices.getUserMedia({
            video: id ? { deviceId: { exact: id } } : true,
          });
          if (cancelled) {
            stream.getTracks().forEach((t) => t.stop());
            return;
          }
          streamsRef.current[i] = stream;
          const v = videoRefs.current[i];
          if (v) v.srcObject = stream;
        }
        if (!cancelled) {
          const st = await darts.calibrationStatus().catch(() => null);
          setCalibrated(!!st?.calibrated);
          setStatus(st?.calibrated ? "Skalibrowano — gotowe do gry." : "Skieruj kamery na PUSTĄ tarczę i kliknij „Kalibruj”.");
        }
      } catch (e) {
        setStatus("Nie udało się uruchomić kamer: " + (e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
      streamsRef.current.forEach((s) => s?.getTracks().forEach((t) => t.stop()));
    };
  }, [darts, deviceIds]);

  // --- pomocnicze ---------------------------------------------------------
  const captureAll = useCallback((): Frames => {
    const frames: Frames = {};
    CAM_IDS.forEach((cid, i) => {
      const v = videoRefs.current[i];
      if (v && v.videoWidth) frames[cid] = captureFrame(v);
    });
    return frames;
  }, []);

  const withBusy = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      if (e instanceof DartsServiceError) setStatus(`Błąd (${e.status}): ${e.detail}`);
      else setStatus("Błąd: " + (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // Kalibracja perspektywiczna (4 punkty): zamroź klatki z 3 kamer i otwórz ekran klikania.
  const onCalibrate = () => {
    const snap: Record<string, FrozenFrame> = {};
    CAM_IDS.forEach((cid, i) => {
      const v = videoRefs.current[i];
      if (v && v.videoWidth) snap[cid] = captureFrameDataUrl(v);
    });
    setFrozen(snap);
    setStatus("Kalibracja: kliknij double 20/6/3/11 na każdej kamerze.");
  };

  const onCaptureBefore = () =>
    withBusy(async () => {
      setBefore(captureAll());
      setStatus("Zapisano klatkę PRZED rzutem. Rzuć lotkę i kliknij „Policz rzut”.");
    });

  const onScoreThrow = () =>
    withBusy(async () => {
      const after = captureAll();
      const hit: Hit = await darts.scoreThrow(before ?? after, after);
      setStatus(`Trafienie: ${describe(hit)} (pewność ${(hit.confidence * 100).toFixed(0)}%)`);
      setBefore(after); // stan "po" staje się tłem dla kolejnego rzutu
    });

  // --- render -------------------------------------------------------------
  if (frozen) {
    return (
      <DartsCalibrator
        client={darts}
        frames={frozen}
        onDone={() => {
          setCalibrated(true);
          setFrozen(null);
          setStatus("Skalibrowano (4 punkty). Gotowe do gry.");
        }}
        onCancel={() => setFrozen(null)}
      />
    );
  }

  return (
    <div style={S.wrap}>
      <div style={S.row}>
        {CAM_IDS.map((cid, i) => (
          <div key={cid} style={S.cam}>
            <video
              ref={(el) => (videoRefs.current[i] = el)}
              autoPlay
              playsInline
              muted
              style={S.video}
            />
            <span style={S.camLabel}>{cid}</span>
          </div>
        ))}
      </div>

      <div style={S.bar}>
        <button onClick={onCalibrate} disabled={busy} style={S.btn}>Kalibruj (4 punkty)</button>
        <button onClick={onCaptureBefore} disabled={busy || !calibrated} style={S.btn}>Zapisz klatkę PRZED</button>
        <button onClick={onScoreThrow} disabled={busy || !calibrated} style={S.btnPrimary}>Policz rzut</button>
        <span style={S.dot(connected)}>{connected ? "● live" : "○ offline"}</span>
      </div>

      <p style={S.status}>{status}</p>

      {lastHit && (
        <div style={S.lastHit}>
          <div style={S.score}>{lastHit.score}</div>
          <div>{describe(lastHit)}</div>
        </div>
      )}

      <ol style={S.list}>
        {[...hits].reverse().map((h, i) => (
          <li key={hits.length - i}>{describe(h)} — {h.score} pkt</li>
        ))}
      </ol>
    </div>
  );
}

function describe(h: Hit): string {
  if (h.ring === "miss") return "PUDŁO";
  if (h.ring === "bull") return "BULL (50)";
  if (h.ring === "outer_bull") return "25";
  const pre = h.ring === "triple" ? "T" : h.ring === "double" ? "D" : "";
  return `${pre}${h.sector}`;
}

// Minimalne style inline — podmień na własne (CSS/Tailwind/itp.).
const S: Record<string, any> = {
  wrap: { fontFamily: "system-ui, sans-serif", maxWidth: 900, margin: "0 auto" },
  row: { display: "flex", gap: 8 },
  cam: { position: "relative", flex: 1, background: "#111", borderRadius: 8, overflow: "hidden" },
  video: { width: "100%", display: "block", aspectRatio: "4 / 3", objectFit: "cover" },
  camLabel: { position: "absolute", top: 6, left: 8, color: "#fff", fontSize: 12, opacity: 0.8 },
  bar: { display: "flex", gap: 8, alignItems: "center", margin: "12px 0" },
  btn: { padding: "8px 12px", borderRadius: 8, border: "1px solid #ccc", cursor: "pointer" },
  btnPrimary: { padding: "8px 12px", borderRadius: 8, border: "none", background: "#2563eb", color: "#fff", cursor: "pointer" },
  dot: (on: boolean) => ({ marginLeft: "auto", color: on ? "#16a34a" : "#999", fontSize: 13 }),
  status: { color: "#444", minHeight: 20 },
  lastHit: { display: "flex", alignItems: "center", gap: 16, padding: 16, background: "#f4f6fb", borderRadius: 12 },
  score: { fontSize: 40, fontWeight: 700 },
  list: { marginTop: 12, color: "#333" },
};
