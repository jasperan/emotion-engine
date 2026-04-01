"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Agent {
  name: string;
  influence: number;
  trust: number;
  bias: number;
  opinion: number;
  color: string;
}

interface HistoryEntry {
  opinions: number[];
}

/* ------------------------------------------------------------------ */
/*  Initial agent data                                                 */
/* ------------------------------------------------------------------ */

const INITIAL_AGENTS: Agent[] = [
  { name: "Dr. Chen", influence: 0.8, trust: 0.7, bias: 0.2, opinion: 0.8, color: "#60a5fa" },
  { name: "Marcus", influence: 0.5, trust: 0.6, bias: 0.4, opinion: -0.6, color: "#f97316" },
  { name: "Sofia", influence: 0.6, trust: 0.8, bias: 0.1, opinion: 0.3, color: "#34d399" },
  { name: "Amir", influence: 0.3, trust: 0.5, bias: 0.7, opinion: -0.3, color: "#facc15" },
];

const ACCENT = "#a78bfa";

/* ------------------------------------------------------------------ */
/*  Simulation logic                                                   */
/* ------------------------------------------------------------------ */

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function runInteraction(agents: Agent[]): Agent[] {
  const next = agents.map((a) => ({ ...a }));
  const BASE_RATE = 0.15;

  for (let i = 0; i < next.length; i++) {
    for (let j = 0; j < next.length; j++) {
      if (i === j) continue;
      const influencer = agents[j]; // use pre-step opinions
      const target = next[i];

      const direction = Math.sign(influencer.opinion - target.opinion);
      const distanceFactor = Math.abs(influencer.opinion - target.opinion);
      let shift =
        direction *
        BASE_RATE *
        influencer.influence *
        target.trust *
        (1 - target.bias) *
        distanceFactor;

      if (Math.abs(shift) < 0.001) continue;
      shift = clamp(shift, -0.3, 0.3);
      target.opinion = clamp(target.opinion + shift, -1.0, 1.0);
    }
  }

  return next;
}

function stdDev(values: number[]): number {
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

/* ------------------------------------------------------------------ */
/*  Mini SVG history chart                                             */
/* ------------------------------------------------------------------ */

function HistoryChart({ history, agents }: { history: HistoryEntry[]; agents: Agent[] }) {
  const W = 320;
  const H = 100;
  const PAD = 2;

  if (history.length === 0) return null;

  const maxSteps = 20;
  const visible = history.slice(-maxSteps);
  const stepW = visible.length > 1 ? (W - PAD * 2) / (visible.length - 1) : 0;

  const yForOpinion = (op: number) => PAD + ((1 - op) / 2) * (H - PAD * 2);

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${W} ${H}`}
      style={{
        display: "block",
        borderRadius: "6px",
        background: "#12131a",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {/* Center line */}
      <line
        x1={PAD}
        y1={H / 2}
        x2={W - PAD}
        y2={H / 2}
        stroke="rgba(255,255,255,0.1)"
        strokeDasharray="4 4"
      />
      {/* +1 / -1 labels */}
      <text x={4} y={12} fill="rgba(255,255,255,0.25)" fontSize="9" fontFamily="monospace">
        +1
      </text>
      <text x={4} y={H - 4} fill="rgba(255,255,255,0.25)" fontSize="9" fontFamily="monospace">
        -1
      </text>

      {/* One polyline + dots per agent */}
      {agents.map((agent, ai) => {
        const points = visible.map(
          (entry, si) => `${PAD + si * stepW},${yForOpinion(entry.opinions[ai])}`
        );
        return (
          <g key={agent.name}>
            {visible.length > 1 && (
              <polyline
                points={points.join(" ")}
                fill="none"
                stroke={agent.color}
                strokeWidth="1.5"
                strokeLinejoin="round"
                opacity={0.7}
              />
            )}
            {visible.map((entry, si) => (
              <circle
                key={si}
                cx={PAD + si * stepW}
                cy={yForOpinion(entry.opinions[ai])}
                r={si === visible.length - 1 ? 3 : 1.5}
                fill={agent.color}
                opacity={si === visible.length - 1 ? 1 : 0.5}
              />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Main widget                                                        */
/* ------------------------------------------------------------------ */

export default function OpinionDynamicsWidget() {
  const [agents, setAgents] = useState<Agent[]>(INITIAL_AGENTS.map((a) => ({ ...a })));
  const [step, setStep] = useState(0);
  const [history, setHistory] = useState<HistoryEntry[]>([
    { opinions: INITIAL_AGENTS.map((a) => a.opinion) },
  ]);
  const [running, setRunning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* Cleanup on unmount */
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const doStep = useCallback(() => {
    setAgents((prev) => {
      const next = runInteraction(prev);
      setHistory((h) => {
        const entry: HistoryEntry = { opinions: next.map((a) => a.opinion) };
        const updated = [...h, entry];
        return updated.length > 200 ? updated.slice(-200) : updated;
      });
      setStep((s) => s + 1);
      return next;
    });
  }, []);

  const handleInteract = () => doStep();

  const handleAutoRun = () => {
    if (running) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = null;
      setRunning(false);
    } else {
      setRunning(true);
      intervalRef.current = setInterval(doStep, 600);
    }
  };

  const handleReset = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = null;
    setRunning(false);
    setAgents(INITIAL_AGENTS.map((a) => ({ ...a })));
    setStep(0);
    setHistory([{ opinions: INITIAL_AGENTS.map((a) => a.opinion) }]);
  };

  const handleSlider = (index: number, value: number) => {
    setAgents((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], opinion: value };
      return next;
    });
  };

  const consensus = stdDev(agents.map((a) => a.opinion));

  /* ---- helpers for opinion bar ---- */
  const opinionBarBg =
    "linear-gradient(to right, #ef4444 0%, #71717a 50%, #22c55e 100%)";

  return (
    <div className="widget-container s-opinion" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Opinion Dynamics</div>

      {/* Topic */}
      <div
        style={{
          fontSize: "14px",
          fontWeight: 600,
          color: "#e4e4e7",
          marginBottom: "6px",
        }}
      >
        Topic: &ldquo;Should we evacuate?&rdquo;
      </div>
      <div
        style={{
          fontSize: "12px",
          color: "#71717a",
          marginBottom: "16px",
        }}
      >
        Opinions range from &minus;1.0 (strongly against) to +1.0 (strongly for)
      </div>

      {/* Buttons */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "18px", flexWrap: "wrap" }}>
        <button className="btn-mono" onClick={handleInteract} disabled={running}>
          Interact
        </button>
        <button
          className={`btn-mono${running ? " active" : ""}`}
          onClick={handleAutoRun}
        >
          {running ? "Stop" : "Auto Run"}
        </button>
        <button className="btn-mono" onClick={handleReset}>
          Reset
        </button>
      </div>

      {/* Agent opinion bars */}
      <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginBottom: "20px" }}>
        {agents.map((agent, idx) => {
          const pct = ((agent.opinion + 1) / 2) * 100;
          return (
            <div key={agent.name}>
              {/* Agent header row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: "6px",
                  flexWrap: "wrap",
                }}
              >
                <span
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: agent.color,
                    minWidth: "70px",
                  }}
                >
                  {agent.name}
                </span>
                <span
                  style={{
                    fontSize: "10px",
                    padding: "1px 6px",
                    borderRadius: "4px",
                    background: "rgba(167,139,250,0.15)",
                    color: ACCENT,
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                  }}
                >
                  inf {agent.influence}
                </span>
                <span
                  style={{
                    fontSize: "10px",
                    padding: "1px 6px",
                    borderRadius: "4px",
                    background: "rgba(255,255,255,0.06)",
                    color: "#a1a1aa",
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                  }}
                >
                  bias {agent.bias}
                </span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: "14px",
                    fontWeight: 700,
                    color: "#fff",
                    fontVariantNumeric: "tabular-nums",
                    minWidth: "48px",
                    textAlign: "right",
                  }}
                  suppressHydrationWarning
                >
                  {agent.opinion >= 0 ? "+" : ""}
                  {agent.opinion.toFixed(2)}
                </span>
              </div>

              {/* Labels row */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "10px",
                  color: "#71717a",
                  marginBottom: "2px",
                }}
              >
                <span style={{ color: "#ef4444" }}>Against</span>
                <span>Neutral</span>
                <span style={{ color: "#22c55e" }}>For</span>
              </div>

              {/* Opinion bar with dot */}
              <div
                style={{
                  position: "relative",
                  width: "100%",
                  height: "14px",
                  borderRadius: "7px",
                  background: opinionBarBg,
                  opacity: 0.35,
                }}
              >
                {/* Active fill overlay for contrast */}
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: "100%",
                    borderRadius: "7px",
                    background: opinionBarBg,
                    opacity: 0.65,
                  }}
                />
                {/* Dot marker */}
                <div
                  style={{
                    position: "absolute",
                    top: "50%",
                    left: `${pct}%`,
                    transform: "translate(-50%, -50%)",
                    width: "16px",
                    height: "16px",
                    borderRadius: "50%",
                    background: agent.color,
                    border: "2px solid #18181b",
                    boxShadow: `0 0 6px ${agent.color}88`,
                    zIndex: 2,
                    transition: "left 0.2s ease",
                  }}
                  suppressHydrationWarning
                />
              </div>

              {/* Hidden range input for dragging */}
              <input
                type="range"
                min={-100}
                max={100}
                value={Math.round(agent.opinion * 100)}
                onChange={(e) => handleSlider(idx, Number(e.target.value) / 100)}
                style={{
                  width: "100%",
                  marginTop: "-14px",
                  position: "relative",
                  zIndex: 3,
                  opacity: 0,
                  cursor: "pointer",
                  height: "14px",
                }}
                aria-label={`${agent.name} opinion slider`}
              />
            </div>
          );
        })}
      </div>

      {/* Stats row */}
      <div
        style={{
          display: "flex",
          gap: "24px",
          marginBottom: "16px",
          flexWrap: "wrap",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: ACCENT,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "2px",
            }}
          >
            Step
          </div>
          <div
            style={{
              fontSize: "20px",
              fontWeight: 700,
              color: "#fff",
              fontVariantNumeric: "tabular-nums",
            }}
            suppressHydrationWarning
          >
            {step}
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: ACCENT,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "2px",
            }}
          >
            Consensus Meter (std dev)
          </div>
          <div
            style={{
              fontSize: "20px",
              fontWeight: 700,
              color: consensus < 0.15 ? "#22c55e" : consensus < 0.4 ? "#facc15" : "#ef4444",
              fontVariantNumeric: "tabular-nums",
            }}
            suppressHydrationWarning
          >
            {consensus.toFixed(2)}
          </div>
          <div
            style={{ fontSize: "11px", color: "#71717a", marginTop: "2px" }}
          >
            {consensus < 0.15
              ? "Strong consensus"
              : consensus < 0.4
                ? "Moderate agreement"
                : "Polarized"}
          </div>
        </div>
      </div>

      {/* History chart */}
      <div>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: ACCENT,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            marginBottom: "8px",
          }}
        >
          Opinion Trajectories (last 20 steps)
        </div>
        <HistoryChart history={history} agents={agents} />
        {/* Legend */}
        <div
          style={{
            display: "flex",
            gap: "14px",
            marginTop: "8px",
            flexWrap: "wrap",
          }}
        >
          {agents.map((a) => (
            <div
              key={a.name}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "11px",
                color: "#a1a1aa",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: a.color,
                }}
              />
              {a.name}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
