import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DeckRecord } from "../types";

type Props = {
  decks: DeckRecord[];
};

export function AnalyticsPanel({ decks }: Props) {
  const [deckA, setDeckA] = useState<number | null>(null);
  const [deckB, setDeckB] = useState<number | null>(null);
  const [matches, setMatches] = useState(20);
  const [difficulty, setDifficulty] = useState("master");
  const [maxTicks, setMaxTicks] = useState(2000);
  const [result, setResult] = useState<string>("");
  const [resultObj, setResultObj] = useState<Record<string, unknown> | null>(null);
  const [running, setRunning] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progressText, setProgressText] = useState<string>("");

  async function runBatch() {
    const a = decks.find((d) => d.id === deckA);
    const b = decks.find((d) => d.id === deckB);
      if (!a || !b) {
      setResult("Select both decks before running Testing Simulator.");
      setResultObj(null);
      return;
    }
    try {
      setRunning(true);
      setResult("");
      setResultObj(null);
      setProgressText("Queueing simulator job...");
      const job = await api.startSimulateBatchJob(a.mainboard, b.mainboard, matches, difficulty, maxTicks);
      setJobId(job.job_id);
    } catch (err) {
      setResult(`Testing Simulator request failed: ${String(err)}`);
      setProgressText("");
      setJobId(null);
      setRunning(false);
    }
  }

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.getSimulateBatchJob(jobId);
        if (cancelled) return;
        const pct = job.total_matches > 0
          ? Math.floor((job.completed_matches / job.total_matches) * 100)
          : 0;
        const elapsedSec = Math.max(0, Math.floor(Date.now() / 1000 - job.started_at));
        setProgressText(
          `Status: ${job.status} | ${job.completed_matches}/${job.total_matches} matches (${pct}%) | ${elapsedSec}s elapsed`,
        );
        if (job.status === "completed") {
          setResultObj((job.result ?? null) as Record<string, unknown> | null);
          setResult(JSON.stringify(job.result ?? {}, null, 2));
          setRunning(false);
          setJobId(null);
          window.clearInterval(timer);
        } else if (job.status === "failed") {
          setResult(`Testing Simulator failed: ${job.error ?? "unknown error"}`);
          setRunning(false);
          setJobId(null);
          window.clearInterval(timer);
        }
      } catch (err) {
        if (cancelled) return;
        setResult(`Testing Simulator progress failed: ${String(err)}`);
        setRunning(false);
        setJobId(null);
        window.clearInterval(timer);
      }
    }, 800);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobId]);

  function cancelDisplay() {
    setRunning(false);
    setJobId(null);
    setProgressText("Polling stopped. Job may still be running on backend.");
  }

  return (
    <section className="panel analytics">
      <h2>Testing Simulator</h2>
      <div className="row">
        <select value={deckA ?? ""} onChange={(e) => setDeckA(Number(e.target.value))}>
          <option value="">Deck A</option>
          {decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select value={deckB ?? ""} onChange={(e) => setDeckB(Number(e.target.value))}>
          <option value="">Deck B</option>
          {decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <input type="number" min={5} max={500} value={matches} onChange={(e) => setMatches(Number(e.target.value))} />
        <input type="number" min={500} max={50000} value={maxTicks} onChange={(e) => setMaxTicks(Number(e.target.value))} title="Max actions per game" />
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="casual">Casual</option>
          <option value="strong">Strong</option>
          <option value="master">Master</option>
          <option value="master_plus">Master+</option>
        </select>
        <button onClick={runBatch} disabled={running}>{running ? "Running..." : `Run ${matches} Matches`}</button>
        {running ? <button onClick={cancelDisplay}>Stop Polling</button> : null}
      </div>
      <pre>{progressText || "Idle."}</pre>
      {resultObj ? (
        <div className="analytics-summary">
          <p>
            Win Rate: A {(resultObj.win_rate_deck_a as number | undefined) ?? "-"}% | B {(resultObj.win_rate_deck_b as number | undefined) ?? "-"}% |
            Avg Turns {(resultObj.average_turns as number | undefined) ?? "-"}
          </p>
          <p>
            Fingerprint: {(resultObj.deterministic_replay_fingerprint as string | undefined) ?? "n/a"}
          </p>
          <p>
            Anomalies: {JSON.stringify(resultObj.anomalies ?? {}, null, 0)}
          </p>
          <p>
            Top Errors: {JSON.stringify(resultObj.top_errors ?? [], null, 0)}
          </p>
        </div>
      ) : null}
      <pre>{result || "No simulation result yet."}</pre>
    </section>
  );
}
