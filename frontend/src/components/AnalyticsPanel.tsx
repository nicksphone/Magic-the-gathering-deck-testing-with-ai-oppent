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
  const [jobStatus, setJobStatus] = useState<string>("idle");
  const [progressPct, setProgressPct] = useState(0);
  const [jobError, setJobError] = useState<string>("");

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
      setJobStatus("queued");
      setResult("");
      setResultObj(null);
      setJobError("");
      setProgressPct(0);
      setProgressText("Queueing simulator job...");
      const job = await api.startSimulateBatchJob(a.mainboard, b.mainboard, matches, difficulty, maxTicks);
      setJobId(job.job_id);
    } catch (err) {
      setResult(`Testing Simulator request failed: ${String(err)}`);
      setProgressText("");
      setJobStatus("failed");
      setJobError(String(err));
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
        setJobStatus(job.status);
        setProgressPct(pct);
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
          setJobError(job.error ?? "unknown error");
          setRunning(false);
          setJobId(null);
          window.clearInterval(timer);
        }
      } catch (err) {
        if (cancelled) return;
        setResult(`Testing Simulator progress failed: ${String(err)}`);
        setJobError(String(err));
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
    setJobStatus("paused");
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
      <div className="sim-status-panel">
        <div className="sim-status-row">
          <span className={`sim-status-pill sim-status-${jobStatus}`}>{jobStatus}</span>
          <span>{progressText || "Idle."}</span>
        </div>
        <div className="sim-progress-track" aria-hidden="true">
          <div className="sim-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
      </div>
      {jobError ? <p className="sim-error">Latest simulator error: {jobError}</p> : null}
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
          {Array.isArray(resultObj.sample_turn_summaries) ? (
            <div className="analytics-sample-block">
              <strong>First Game Turn Summary</strong>
              <ul className="analytics-sample-list">
                {(resultObj.sample_turn_summaries as Array<Record<string, unknown>>).map((turn) => (
                  <li key={`${turn.turn ?? "turn"}-${turn.pid ?? "pid"}`}>
                    T{turn.turn as number | string} P{turn.pid as number | string} {turn.step as string} | {(turn.action_type as string) ?? "pass"} | hand {(turn.hand_size as number | string) ?? "-"} | field {(turn.battlefield_size as number | string) ?? "-"} / {(turn.opp_battlefield_size as number | string) ?? "-"}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {Array.isArray(resultObj.sample_log_excerpt) ? (
            <div className="analytics-sample-block">
              <strong>First Game Log Excerpt</strong>
              <pre className="analytics-log-excerpt">
                {(resultObj.sample_log_excerpt as string[]).join("\n")}
              </pre>
            </div>
          ) : null}
          {Array.isArray(resultObj.game_results) ? (
            <div className="analytics-sample-block">
              <strong>Per-Game Results</strong>
              <ul className="analytics-sample-list">
                {(resultObj.game_results as Array<Record<string, unknown>>).slice(0, 12).map((game) => (
                  <li key={`${game.game_index ?? "g"}-${game.seed ?? "s"}`}>
                    Game {game.game_index as number | string}: winner {String(game.winner ?? "timeout")} | turns {String(game.turns ?? "-")} | deck A on play: {String(game.deck_a_on_play ?? false)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      <pre>{result || "No simulation result yet."}</pre>
    </section>
  );
}
