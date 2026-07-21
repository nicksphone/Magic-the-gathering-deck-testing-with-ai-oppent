import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DeckRecord } from "../types";
import type { DiagnosticRunDetail, DiagnosticRunSummary } from "../api/client";

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
  const [diagnosticRuns, setDiagnosticRuns] = useState<DiagnosticRunSummary[]>([]);
  const [selectedDiagnostic, setSelectedDiagnostic] = useState<DiagnosticRunDetail | null>(null);
  const [selectedGameIndex, setSelectedGameIndex] = useState(0);
  const [compareLeft, setCompareLeft] = useState("");
  const [compareRight, setCompareRight] = useState("");
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [replayComparison, setReplayComparison] = useState<Record<string, unknown> | null>(null);
  const [replayLeftGame, setReplayLeftGame] = useState(0);
  const [replayRightGame, setReplayRightGame] = useState(0);
  const [diagnosticError, setDiagnosticError] = useState("");
  const firstDivergence = (resultObj?.first_divergence as Record<string, unknown> | null) ?? null;
  const firstDivergenceExcerpt = (resultObj?.first_divergence_excerpt as Record<string, unknown> | null) ?? null;
  const anomalyObj = (resultObj?.anomalies as Record<string, unknown> | null) ?? null;
  const balanceAlerts = Array.isArray(resultObj?.balance_alerts) ? resultObj.balance_alerts as Array<Record<string, unknown>> : [];
  const confidenceIntervals = (resultObj?.confidence_intervals as Record<string, Record<string, unknown>> | null) ?? null;

  async function refreshDiagnosticRuns() {
    try {
      setDiagnosticError("");
      const payload = await api.listDiagnosticRuns(20);
      setDiagnosticRuns(payload.runs);
    } catch (err) {
      setDiagnosticError(String(err));
    }
  }

  async function openDiagnosticRun(runName: string) {
    try {
      setDiagnosticError("");
      setSelectedDiagnostic(await api.getDiagnosticRun(runName));
      setSelectedGameIndex(0);
    } catch (err) {
      setDiagnosticError(String(err));
    }
  }

  async function compareDiagnosticRuns() {
    if (!compareLeft || !compareRight || compareLeft === compareRight) return;
    try {
      setDiagnosticError("");
      setComparison(await api.compareDiagnosticRuns(compareLeft, compareRight) as unknown as Record<string, unknown>);
    } catch (err) {
      setDiagnosticError(String(err));
    }
  }

  async function compareDiagnosticReplay() {
    if (!compareLeft || !compareRight || compareLeft === compareRight) return;
    try {
      setDiagnosticError("");
      setReplayComparison(await api.compareDiagnosticReplay(compareLeft, compareRight, replayLeftGame, replayRightGame) as unknown as Record<string, unknown>);
    } catch (err) {
      setDiagnosticError(String(err));
    }
  }

  useEffect(() => {
    void refreshDiagnosticRuns();
  }, []);

  function renderTraceContext(title: string, context: Record<string, unknown> | null | undefined) {
    if (!context || Object.keys(context).length === 0) {
      return <p>{title}: n/a</p>;
    }
    return (
      <div>
        <strong>{title}</strong>
        <ul className="analytics-sample-list">
          <li>pid: {String(context.pid ?? "-")}</li>
          <li>turn: {String(context.turn ?? "-")}</li>
          <li>step: {String(context.step ?? "-")}</li>
          <li>active / priority: {String(context.active_player ?? "-")} / {String(context.priority_player ?? "-")}</li>
          <li>hand: {String(context.hand_size ?? "-")} | opp hand: {String(context.opp_hand_size ?? "-")}</li>
          <li>field: {String(context.battlefield_size ?? "-")} | opp field: {String(context.opp_battlefield_size ?? "-")}</li>
          <li>life: {String(context.life_self ?? "-")} / {String(context.life_opp ?? "-")}</li>
          <li>legal: non-pass {String(context.legal_non_pass ?? "-")} | land {String(context.legal_has_land ?? "-")}</li>
          <li>action: {String(context.action_type ?? "-")}</li>
        </ul>
      </div>
    );
  }

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
      <div className="analytics-sample-block">
        <div className="sim-status-row">
          <strong>Persisted Diagnostic Runs</strong>
          <button type="button" onClick={() => void refreshDiagnosticRuns()}>Refresh</button>
        </div>
        {diagnosticError ? <p className="sim-error">Diagnostics: {diagnosticError}</p> : null}
        {diagnosticRuns.length === 0 ? (
          <p>No persisted diagnostic runs found.</p>
        ) : (
          <ul className="analytics-sample-list">
            {diagnosticRuns.map((run) => {
              const summary = run.summary;
              return (
                <li key={run.run_name}>
                  <button type="button" onClick={() => void openDiagnosticRun(run.run_name)}>{run.run_name}</button>{" "}
                  {new Date(run.modified_at * 1000).toLocaleString()} | matches {String(summary.matches ?? summary.games ?? "-")} | anomalies {String(summary.anomaly_count ?? summary.anomalies ?? "-")}
                </li>
              );
            })}
          </ul>
        )}
        {diagnosticRuns.length > 1 ? (
          <div className="row">
            <select value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)}>
              <option value="">Compare left run</option>
              {diagnosticRuns.map((run) => <option key={`left-${run.run_name}`} value={run.run_name}>{run.run_name}</option>)}
            </select>
            <select value={compareRight} onChange={(event) => setCompareRight(event.target.value)}>
              <option value="">Compare right run</option>
              {diagnosticRuns.map((run) => <option key={`right-${run.run_name}`} value={run.run_name}>{run.run_name}</option>)}
            </select>
            <button type="button" onClick={() => void compareDiagnosticRuns()} disabled={!compareLeft || !compareRight || compareLeft === compareRight}>Compare Summaries</button>
            <input aria-label="Left replay game" type="number" min="0" max="19" value={replayLeftGame} onChange={(event) => setReplayLeftGame(Math.max(0, Math.min(19, Number(event.target.value) || 0)))} />
            <input aria-label="Right replay game" type="number" min="0" max="19" value={replayRightGame} onChange={(event) => setReplayRightGame(Math.max(0, Math.min(19, Number(event.target.value) || 0)))} />
            <button type="button" onClick={() => void compareDiagnosticReplay()} disabled={!compareLeft || !compareRight || compareLeft === compareRight}>Compare Replay Lines</button>
          </div>
        ) : null}
        {comparison ? (
          <pre className="analytics-log-excerpt">{JSON.stringify(comparison, null, 2)}</pre>
        ) : null}
        {replayComparison ? (
          <pre className="analytics-log-excerpt">{JSON.stringify(replayComparison, null, 2)}</pre>
        ) : null}
        {selectedDiagnostic ? (
          <div>
            <strong>Root-Cause Snapshot: {selectedDiagnostic.run_name}</strong>
            <pre className="analytics-log-excerpt">
              {JSON.stringify({
                summary: selectedDiagnostic.summary,
                anomaly_clusters: selectedDiagnostic.anomaly_clusters,
                anomaly_samples: selectedDiagnostic.anomaly_samples.slice(0, 5),
                artifacts: selectedDiagnostic.artifacts,
              }, null, 2)}
            </pre>
            {selectedDiagnostic.games.length > 0 ? (
              <div>
                <strong>Replay Games</strong>
                <div className="row">
                  {selectedDiagnostic.games.map((game, index) => (
                    <button
                      type="button"
                      key={`${String(game.game ?? index)}-${index}`}
                      onClick={() => setSelectedGameIndex(index)}
                    >
                      Game {String(game.game ?? index + 1)}
                    </button>
                  ))}
                </div>
                <pre className="analytics-log-excerpt">
                  {JSON.stringify(selectedDiagnostic.games[selectedGameIndex] ?? {}, null, 2)}
                </pre>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
      {resultObj ? (
        <div className="analytics-summary">
          <p>
            Win Rate: A {(resultObj.win_rate_deck_a as number | undefined) ?? "-"}% | B {(resultObj.win_rate_deck_b as number | undefined) ?? "-"}% |
            Avg Turns {(resultObj.average_turns as number | undefined) ?? "-"}
          </p>
          <p>
            Fingerprint: {(resultObj.deterministic_replay_fingerprint as string | undefined) ?? "n/a"}
          </p>
          {confidenceIntervals ? (
            <p>
              95% CI: A {String(confidenceIntervals.deck_a?.low ?? "-")}%-{String(confidenceIntervals.deck_a?.high ?? "-")}% | B {String(confidenceIntervals.deck_b?.low ?? "-")}%-{String(confidenceIntervals.deck_b?.high ?? "-")}%
            </p>
          ) : null}
          {balanceAlerts.length > 0 ? (
            <div className="analytics-sample-block balance-alerts">
              <strong>Balance Alerts</strong>
              <ul className="analytics-sample-list">
                {balanceAlerts.map((alert, index) => (
                  <li key={`${String(alert.kind)}-${index}`}>
                    {String(alert.kind)}: {String(alert.deck ?? "sample")} {String(alert.rate ?? "")} ({String(alert.games ?? "")} games) [{String(alert.severity)}]
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {anomalyObj ? (
            <div className="analytics-sample-block">
              <strong>Anomaly Counters</strong>
              <ul className="analytics-sample-list">
                {Object.entries(anomalyObj).map(([key, value]) => (
                  <li key={key}>
                    {key}: {String(value)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <p>
            Anomalies: {JSON.stringify(resultObj.anomalies ?? {}, null, 0)}
          </p>
          <p>
            Top Errors: {JSON.stringify(resultObj.top_errors ?? [], null, 0)}
          </p>
          {Array.isArray(resultObj.oracle_fallback_cards) && (resultObj.oracle_fallback_cards as unknown[]).length > 0 ? (
            <div className="analytics-sample-block">
              <strong>Unsupported Oracle Effects</strong>
              <ul className="analytics-sample-list">
                {(resultObj.oracle_fallback_cards as Array<Record<string, unknown>>).map((item) => (
                  <li key={String(item.card_name)}>{String(item.card_name)}: {String(item.count)} fallback(s)</li>
                ))}
              </ul>
            </div>
          ) : null}
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
          {firstDivergence ? (
            <div className="analytics-sample-block">
              <strong>First Divergence</strong>
              <p>
                Category: {String(firstDivergence.category ?? "unknown")} | Index: {String(firstDivergence.index ?? -1)}
              </p>
              <pre className="analytics-log-excerpt">
                {JSON.stringify(firstDivergence, null, 2)}
              </pre>
            </div>
          ) : null}
          {firstDivergenceExcerpt ? (
            <div className="analytics-sample-block">
              <strong>First Divergence Trace Context</strong>
              {renderTraceContext("Trace Context A", firstDivergenceExcerpt.trace_context_a as Record<string, unknown> | null | undefined)}
              {renderTraceContext("Trace Context B", firstDivergenceExcerpt.trace_context_b as Record<string, unknown> | null | undefined)}
              <pre className="analytics-log-excerpt">
                {JSON.stringify(firstDivergenceExcerpt, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      ) : null}
      <pre>{result || "No simulation result yet."}</pre>
    </section>
  );
}
