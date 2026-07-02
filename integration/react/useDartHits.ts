// Hook React: subskrypcja trafień na żywo z serwisu dartscore.
//
// Użycie:
//   const { lastHit, hits, connected } = useDartHits();
//   // lastHit -> ostatnie trafienie, hits -> historia, connected -> stan WS

import { useEffect, useRef, useState } from "react";
import { DartsClient, type Hit } from "./dartsClient";

export interface UseDartHitsResult {
  lastHit: Hit | null;
  hits: Hit[];
  connected: boolean;
}

export function useDartHits(client?: DartsClient): UseDartHitsResult {
  const [lastHit, setLastHit] = useState<Hit | null>(null);
  const [hits, setHits] = useState<Hit[]>([]);
  const [connected, setConnected] = useState(false);
  // Stały klient między renderami (chyba że przekazano własny).
  const clientRef = useRef<DartsClient | null>(client ?? null);
  if (clientRef.current === null) clientRef.current = new DartsClient();

  useEffect(() => {
    const darts = clientRef.current!;
    setConnected(true);
    const close = darts.subscribeHits(
      (hit) => {
        setLastHit(hit);
        setHits((prev) => [...prev, hit]);
      },
      () => setConnected(false),
    );
    return () => {
      setConnected(false);
      close();
    };
  }, []);

  return { lastHit, hits, connected };
}
