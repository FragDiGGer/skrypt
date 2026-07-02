// Ekran kalibracji perspektywicznej (4 punkty na kamerę): klikasz zewnętrzną
// krawędź pierścienia double dla sektorów 20, 6, 3, 11 — w tej kolejności.
//
// Działa na ZAMROŻONYCH klatkach (dataUrl + wymiary natywne), które przekazuje
// rodzic (patrz DartsPanel) — dzięki temu nie otwieramy kamer drugi raz i mamy
// kliknięcia w px natywnych (tych samych, w których backend liczy rzuty).

import React, { useMemo, useState } from "react";
import {
  DartsClient,
  DartsServiceError,
  REFERENCE_LABELS,
  type PointsCalibration,
} from "./dartsClient";

export interface FrozenFrame {
  dataUrl: string;
  width: number;
  height: number;
}

export interface DartsCalibratorProps {
  client: DartsClient;
  frames: Record<string, FrozenFrame>; // camId -> zamrożona klatka
  onDone?: () => void;
  onCancel?: () => void;
}

type PointsByCam = Record<string, [number, number][]>;

export function DartsCalibrator({ client, frames, onDone, onCancel }: DartsCalibratorProps) {
  const camIds = useMemo(() => Object.keys(frames), [frames]);
  const [camIdx, setCamIdx] = useState(0);
  const [points, setPoints] = useState<PointsByCam>(() =>
    Object.fromEntries(camIds.map((c) => [c, []])),
  );
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const cam = camIds[camIdx];
  const frame = frames[cam];
  const camPts = points[cam] ?? [];
  const nextLabel = REFERENCE_LABELS[camPts.length];
  const allDone = camIds.every((c) => (points[c]?.length ?? 0) === REFERENCE_LABELS.length);

  const onImageClick = (e: React.MouseEvent<HTMLImageElement>) => {
    if (camPts.length >= REFERENCE_LABELS.length) return;
    const img = e.currentTarget;
    const rect = img.getBoundingClientRect();
    // Przelicz kliknięcie z px wyświetlanych na px natywne klatki.
    const nx = ((e.clientX - rect.left) / rect.width) * frame.width;
    const ny = ((e.clientY - rect.top) / rect.height) * frame.height;
    setPoints((p) => ({ ...p, [cam]: [...(p[cam] ?? []), [nx, ny]] }));
  };

  const undo = () => setPoints((p) => ({ ...p, [cam]: (p[cam] ?? []).slice(0, -1) }));

  const save = async () => {
    setBusy(true);
    try {
      const payload: PointsCalibration = {};
      for (const c of camIds) {
        const pts = points[c];
        payload[c] = {
          image_size: [frames[c].width, frames[c].height],
          points: Object.fromEntries(REFERENCE_LABELS.map((lab, i) => [lab, pts[i]])),
        };
      }
      const res = await client.calibrateFromPoints(payload);
      setStatus(`Zapisano kalibrację (offset 20 = ${res.sector20_offset_deg ?? 0}°).`);
      onDone?.();
    } catch (e) {
      setStatus(
        e instanceof DartsServiceError ? `Błąd (${e.status}): ${e.detail}` : "Błąd: " + (e as Error).message,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={S.wrap}>
      <div style={S.head}>
        <strong>Kalibracja — kamera {cam}</strong>
        <span style={S.hint}>
          {nextLabel
            ? `Kliknij ZEWNĘTRZNĄ krawędź double sektora „${nextLabel}” (${camPts.length + 1}/4)`
            : "✓ 4 punkty gotowe dla tej kamery"}
        </span>
      </div>

      <div style={S.imgBox}>
        <img src={frame.dataUrl} onClick={onImageClick} style={S.img} alt={`kamera ${cam}`} />
        {camPts.map(([x, y], i) => (
          <div
            key={i}
            style={{
              ...S.marker,
              left: `${(x / frame.width) * 100}%`,
              top: `${(y / frame.height) * 100}%`,
            }}
          >
            {REFERENCE_LABELS[i]}
          </div>
        ))}
      </div>

      <div style={S.bar}>
        <button onClick={undo} disabled={camPts.length === 0} style={S.btn}>Cofnij punkt</button>
        <button onClick={() => setCamIdx((i) => Math.max(0, i - 1))} disabled={camIdx === 0} style={S.btn}>◀ Kamera</button>
        <button onClick={() => setCamIdx((i) => Math.min(camIds.length - 1, i + 1))} disabled={camIdx >= camIds.length - 1} style={S.btn}>Kamera ▶</button>
        <button onClick={save} disabled={!allDone || busy} style={S.btnPrimary}>Zapisz kalibrację</button>
        {onCancel && <button onClick={onCancel} style={S.btn}>Anuluj</button>}
      </div>

      <p style={S.status}>{status}</p>
      <p style={S.legend}>
        Wskazówka: 20 = góra, 6 = prawo, 3 = dół, 11 = lewo (na Twojej tarczy w kadrze
        mogą być obrócone — klikaj wg rzeczywistego położenia tych cyfr).
      </p>
    </div>
  );
}

const S: Record<string, any> = {
  wrap: { fontFamily: "system-ui, sans-serif", maxWidth: 900, margin: "0 auto" },
  head: { display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 },
  hint: { color: "#2563eb" },
  imgBox: { position: "relative", lineHeight: 0, border: "1px solid #ccc", borderRadius: 8, overflow: "hidden" },
  img: { width: "100%", cursor: "crosshair", display: "block" },
  marker: {
    position: "absolute", transform: "translate(-50%, -50%)", width: 22, height: 22,
    borderRadius: "50%", background: "rgba(37,99,235,0.85)", color: "#fff",
    fontSize: 12, display: "flex", alignItems: "center", justifyContent: "center",
    border: "2px solid #fff", pointerEvents: "none",
  },
  bar: { display: "flex", gap: 8, margin: "12px 0", flexWrap: "wrap" },
  btn: { padding: "8px 12px", borderRadius: 8, border: "1px solid #ccc", cursor: "pointer" },
  btnPrimary: { padding: "8px 12px", borderRadius: 8, border: "none", background: "#16a34a", color: "#fff", cursor: "pointer" },
  status: { color: "#444", minHeight: 20 },
  legend: { color: "#777", fontSize: 13 },
};
