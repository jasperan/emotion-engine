"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";

/* ------------------------------------------------------------------ */
/*  Constants & types                                                  */
/* ------------------------------------------------------------------ */

const ACCENT = "#e879f9";
const ACCENT_DIM = "rgba(232,121,249,0.2)";

const FULL_PIPELINE = ["Think", "Plan", "Act", "Reflect"];
const LITE_PIPELINE = ["Evaluate", "Weighted Action"];

interface BehaviorWeight {
  trait: string;
  traitKey: string;
  action: string;
  formula: string;
  coefficient: number;
}

const BEHAVIOR_WEIGHTS: BehaviorWeight[] = [
  { trait: "High Extraversion", traitKey: "E", action: "speak", formula: "max(0.1, E/10)", coefficient: 0.10 },
  { trait: "High Agreeableness", traitKey: "A", action: "help", formula: "max(0.1, A/10)", coefficient: 0.10 },
  { trait: "High Openness", traitKey: "O", action: "move/explore", formula: "max(0.1, O/10)", coefficient: 0.10 },
  { trait: "High Conscientiousness", traitKey: "C", action: "gather", formula: "max(0.1, C/10)", coefficient: 0.10 },
  { trait: "High Neuroticism", traitKey: "N", action: "observe", formula: "max(0.1, N/10)", coefficient: 0.10 },
];

interface PromotionTrigger {
  id: string;
  label: string;
  description: string;
}

const PROMOTION_TRIGGERS: PromotionTrigger[] = [
  { id: "addressed", label: "Addressed directly by another agent", description: "Another agent speaks to this agent by name" },
  { id: "extraversion", label: "Extraversion \u2265 7 in active scene", description: "High-E agents self-promote when scene is active" },
  { id: "leadership", label: "Leadership \u2265 8 with stress \u2264 4", description: "Calm leaders escalate to full reasoning" },
];

/* ------------------------------------------------------------------ */
/*  Shared styles                                                      */
/* ------------------------------------------------------------------ */

const monoBlock: React.CSSProperties = {
  fontFamily: "var(--font-mono), ui-monospace, monospace",
  fontSize: "12px",
  lineHeight: 1.7,
  color: "#a1a1aa",
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.06)",
  borderRadius: "8px",
  padding: "14px 16px",
};

const sectionTitle: React.CSSProperties = {
  fontSize: "13px",
  fontWeight: 600,
  color: ACCENT,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: "16px",
};

const statLabel: React.CSSProperties = {
  fontSize: "11px",
  color: "#a1a1aa",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: "4px",
};

const statValue: React.CSSProperties = {
  fontSize: "18px",
  fontWeight: 700,
  color: "#fff",
  fontVariantNumeric: "tabular-nums",
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

function formatTime(seconds: number): string {
  if (seconds < 0.001) return "<0.001s";
  if (seconds < 1) return `${(seconds * 1000).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs.toFixed(0)}s`;
}

/* ------------------------------------------------------------------ */
/*  Simulation agent type                                              */
/* ------------------------------------------------------------------ */

interface SimAgent {
  id: number;
  type: "full" | "lightweight";
  status: "idle" | "thinking" | "done" | "promoted";
  progress: number; // 0-100
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function ScalingWidget() {
  const [agentCount, setAgentCount] = useState(50);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simAgents, setSimAgents] = useState<SimAgent[]>([]);
  const [simStep, setSimStep] = useState(0);
  const [triggers, setTriggers] = useState<Record<string, boolean>>({
    addressed: true,
    extraversion: true,
    leadership: true,
  });
  const simTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* ---------- derived values ---------- */

  const fullAgentCount = Math.min(Math.max(Math.round(agentCount * 0.1), 1), 15);
  const liteAgentCount = agentCount - fullAgentCount;

  // Processing times
  const fullTimeSequential = fullAgentCount * 3;
  const fullTimeParallel = Math.ceil(fullAgentCount / 4) * 3;
  const liteTime = liteAgentCount * 0.001;

  // Token costs per tick
  const fullTokens = fullAgentCount * 500;
  const liteTokens = 0;
  const totalTokens = fullTokens + liteTokens;

  /* ---------- simulation logic ---------- */

  const clearSimTimer = useCallback(() => {
    if (simTimerRef.current !== null) {
      clearInterval(simTimerRef.current);
      simTimerRef.current = null;
    }
  }, []);

  const startSimulation = useCallback(() => {
    // Build agents for sim: use 50 agents baseline for demo
    const simTotal = 50;
    const simFull = 5;
    const simLite = simTotal - simFull;

    const agents: SimAgent[] = [];
    for (let i = 0; i < simFull; i++) {
      agents.push({ id: i, type: "full", status: "idle", progress: 0 });
    }
    for (let i = 0; i < simLite; i++) {
      agents.push({ id: simFull + i, type: "lightweight", status: "idle", progress: 0 });
    }

    setSimAgents(agents);
    setSimStep(0);
    setIsSimulating(true);
  }, []);

  useEffect(() => {
    if (!isSimulating) {
      clearSimTimer();
      return;
    }

    simTimerRef.current = setInterval(() => {
      setSimStep((prev) => {
        const next = prev + 1;

        setSimAgents((agents) => {
          return agents.map((agent) => {
            // Lightweight agents complete instantly (step 1)
            if (agent.type === "lightweight" && agent.status !== "promoted") {
              if (next >= 1 && agent.status === "idle") {
                return { ...agent, status: "done", progress: 100 };
              }
              // Promote 2 lightweight agents at step 8
              if (next === 8 && (agent.id === 7 || agent.id === 22)) {
                return { ...agent, status: "promoted", progress: 0 };
              }
              return agent;
            }

            // Promoted agents act like full agents
            if (agent.status === "promoted") {
              if (next >= 9) {
                const promotedProgress = Math.min(((next - 8) / 6) * 100, 100);
                if (promotedProgress >= 100) {
                  return { ...agent, status: "done", progress: 100 };
                }
                return { ...agent, status: "thinking", progress: promotedProgress };
              }
              return agent;
            }

            // Full agents take multiple steps (thinking animation)
            if (agent.type === "full") {
              if (next >= 1 && agent.status === "idle") {
                return { ...agent, status: "thinking", progress: 0 };
              }
              if (agent.status === "thinking") {
                const newProgress = Math.min(agent.progress + 15 + Math.random() * 10, 100);
                if (newProgress >= 100) {
                  return { ...agent, status: "done", progress: 100 };
                }
                return { ...agent, progress: newProgress };
              }
            }
            return agent;
          });
        });

        // Stop after enough steps
        if (next >= 16) {
          setIsSimulating(false);
        }

        return next;
      });
    }, 300);

    return () => clearSimTimer();
  }, [isSimulating, clearSimTimer]);

  /* ---------- toggle trigger ---------- */

  const toggleTrigger = (id: string) => {
    setTriggers((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  /* ---------- render helpers ---------- */

  const renderPipeline = (stages: string[], color: string) => (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0",
        flexWrap: "wrap",
      }}
    >
      {stages.map((stage, i) => (
        <React.Fragment key={stage}>
          <div
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              background: "rgba(255,255,255,0.04)",
              border: `1px solid ${color}33`,
              fontSize: "12px",
              fontWeight: 600,
              color,
              fontFamily: "var(--font-mono), ui-monospace, monospace",
              letterSpacing: "0.03em",
              whiteSpace: "nowrap",
            }}
          >
            {stage}
          </div>
          {i < stages.length - 1 && (
            <span
              style={{
                padding: "0 6px",
                color: `${color}88`,
                fontSize: "14px",
                fontWeight: 700,
                userSelect: "none",
              }}
            >
              {"\u2192"}
            </span>
          )}
        </React.Fragment>
      ))}
    </div>
  );

  const renderCostBar = (
    label: string,
    value: number,
    maxValue: number,
    color: string,
  ) => {
    const pct = maxValue > 0 ? Math.max((value / maxValue) * 100, value > 0 ? 2 : 0) : 0;
    return (
      <div style={{ marginBottom: "10px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: "4px",
          }}
        >
          <span style={{ fontSize: "12px", color: "#a1a1aa" }}>{label}</span>
          <span
            style={{
              fontSize: "12px",
              fontWeight: 700,
              color: "#fff",
              fontVariantNumeric: "tabular-nums",
              fontFamily: "var(--font-mono), ui-monospace, monospace",
            }}
            suppressHydrationWarning
          >
            {formatNumber(value)} tokens
          </span>
        </div>
        <div
          style={{
            width: "100%",
            height: "8px",
            borderRadius: "4px",
            background: "rgba(255,255,255,0.08)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              borderRadius: "4px",
              background: color,
              transition: "width 0.3s ease",
            }}
            suppressHydrationWarning
          />
        </div>
      </div>
    );
  };

  /* ---------- sim agent dot ---------- */

  const renderSimDot = (agent: SimAgent) => {
    let bg = "rgba(255,255,255,0.1)";
    let border = "transparent";
    let animClass = "";

    if (agent.status === "thinking") {
      bg = ACCENT_DIM;
      border = ACCENT;
      animClass = "animate-pulse";
    } else if (agent.status === "done") {
      bg = agent.type === "full" ? ACCENT : "#4ade80";
      border = "transparent";
    } else if (agent.status === "promoted") {
      bg = "#fbbf24";
      border = "#f59e0b";
      animClass = "animate-pulse";
    }

    return (
      <div
        key={agent.id}
        className={animClass}
        title={`Agent #${agent.id} (${agent.type}${agent.status === "promoted" ? " \u2192 promoted" : ""})`}
        style={{
          width: "10px",
          height: "10px",
          borderRadius: "50%",
          background: bg,
          border: `1.5px solid ${border}`,
          transition: "background 0.3s, border 0.3s",
          flexShrink: 0,
        }}
      />
    );
  };

  /* ---------- render ---------- */

  return (
    <div className="widget-container s-scaling" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Agent Scaling</div>

      {/* ---- Agent Count Slider ---- */}
      <div style={{ marginBottom: "24px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "8px",
          }}
        >
          <label
            style={{
              fontSize: "13px",
              color: "#a1a1aa",
              fontWeight: 500,
            }}
          >
            Number of Agents
          </label>
          <span
            style={{
              fontSize: "18px",
              fontWeight: 700,
              color: "#fff",
              fontVariantNumeric: "tabular-nums",
              minWidth: "40px",
              textAlign: "right",
            }}
            suppressHydrationWarning
          >
            {agentCount}
          </span>
        </div>
        <input
          type="range"
          min={5}
          max={100}
          value={agentCount}
          onChange={(e) => setAgentCount(Number(e.target.value))}
          style={{
            width: "100%",
            accentColor: ACCENT,
          }}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "11px",
            color: "#71717a",
            marginTop: "4px",
          }}
        >
          <span>5</span>
          <span>
            {fullAgentCount} full + {liteAgentCount} lightweight
          </span>
          <span>100</span>
        </div>
      </div>

      {/* ---- Side-by-Side Comparison ---- */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* LEFT: Full Agent (LLM) */}
        <div>
          <h3 style={sectionTitle}>Full Agent (LLM)</h3>

          {/* Pipeline */}
          <div style={{ marginBottom: "16px" }}>
            {renderPipeline(FULL_PIPELINE, "#22d3ee")}
          </div>

          {/* Stats */}
          <div style={monoBlock}>
            <div style={{ marginBottom: "12px" }}>
              <div style={statLabel}>Processing Time</div>
              <div style={statValue} suppressHydrationWarning>~2&ndash;5s per tick</div>
            </div>
            <div style={{ marginBottom: "12px" }}>
              <div style={statLabel}>Features</div>
              <div style={{ fontSize: "12px", color: "#e4e4e7", lineHeight: 1.6 }}>
                Rich dialogue, nuanced decisions, memory, personality expression
              </div>
            </div>
            <div style={{ marginBottom: "12px" }}>
              <div style={statLabel}>Token Cost</div>
              <div style={statValue} suppressHydrationWarning>~500 tokens/tick</div>
            </div>
            <div>
              <div style={statLabel}>Max Scalable</div>
              <div style={statValue}>~10&ndash;15 agents</div>
              <div style={{ fontSize: "11px", color: "#71717a", marginTop: "2px" }}>
                Limited by LLM throughput
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: Lightweight Agent (Rules) */}
        <div>
          <h3 style={sectionTitle}>Lightweight Agent (Rules)</h3>

          {/* Pipeline */}
          <div style={{ marginBottom: "16px" }}>
            {renderPipeline(LITE_PIPELINE, "#4ade80")}
          </div>

          {/* Stats */}
          <div style={monoBlock}>
            <div style={{ marginBottom: "12px" }}>
              <div style={statLabel}>Processing Time</div>
              <div style={statValue}>&lt;1ms per tick</div>
            </div>
            <div style={{ marginBottom: "12px" }}>
              <div style={statLabel}>Features</div>
              <div style={{ fontSize: "12px", color: "#e4e4e7", lineHeight: 1.6 }}>
                Personality-weighted probabilities, basic actions, no dialogue
              </div>
            </div>
            <div style={{ marginBottom: "12px" }}>
              <div style={statLabel}>Token Cost</div>
              <div style={statValue}>0 tokens</div>
            </div>
            <div>
              <div style={statLabel}>Max Scalable</div>
              <div style={statValue}>100+ agents</div>
              <div style={{ fontSize: "11px", color: "#71717a", marginTop: "2px" }}>
                CPU-bound only, no LLM bottleneck
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ---- Behavior Weight Table (Lightweight) ---- */}
      <div style={{ marginTop: "28px" }}>
        <h3 style={sectionTitle}>Behavior Weights (Lightweight Agents)</h3>
        <div style={monoBlock}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto auto",
              gap: "8px 16px",
              alignItems: "center",
            }}
          >
            {/* Header */}
            <div style={{ fontSize: "11px", color: "#71717a", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Trait
            </div>
            <div style={{ fontSize: "11px", color: "#71717a", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Action
            </div>
            <div style={{ fontSize: "11px", color: "#71717a", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", textAlign: "right" }}>
              Weight
            </div>

            {/* Rows */}
            {BEHAVIOR_WEIGHTS.map((bw) => (
              <React.Fragment key={bw.traitKey}>
                <div style={{ fontSize: "12px", color: "#a1a1aa" }}>
                  <span style={{ color: ACCENT, fontWeight: 700 }}>{bw.traitKey}</span>{" "}
                  {bw.trait}
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "#e4e4e7",
                    fontFamily: "var(--font-mono), ui-monospace, monospace",
                  }}
                >
                  {bw.action}
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "#4ade80",
                    fontWeight: 600,
                    fontFamily: "var(--font-mono), ui-monospace, monospace",
                    textAlign: "right",
                  }}
                >
                  {bw.formula}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      {/* ---- Processing Time Estimates ---- */}
      <div style={{ marginTop: "28px" }}>
        <h3 style={sectionTitle}>Processing Time Estimates</h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "12px",
          }}
        >
          {/* Full Sequential */}
          <div style={monoBlock}>
            <div style={statLabel}>Full (Sequential)</div>
            <div style={statValue} suppressHydrationWarning>
              {formatTime(fullTimeSequential)}
            </div>
            <div
              style={{
                fontSize: "11px",
                color: "#71717a",
                marginTop: "4px",
                fontFamily: "var(--font-mono), ui-monospace, monospace",
              }}
              suppressHydrationWarning
            >
              {fullAgentCount} &times; 3s
            </div>
          </div>

          {/* Full Parallel (vLLM) */}
          <div style={monoBlock}>
            <div style={statLabel}>Full (Parallel / vLLM)</div>
            <div style={statValue} suppressHydrationWarning>
              {formatTime(fullTimeParallel)}
            </div>
            <div
              style={{
                fontSize: "11px",
                color: "#71717a",
                marginTop: "4px",
                fontFamily: "var(--font-mono), ui-monospace, monospace",
              }}
              suppressHydrationWarning
            >
              {"\u2308"}{fullAgentCount}/4{"\u2309"} &times; 3s
            </div>
          </div>

          {/* Lightweight */}
          <div style={monoBlock}>
            <div style={statLabel}>Lightweight</div>
            <div style={{ ...statValue, color: "#4ade80" }} suppressHydrationWarning>
              {formatTime(liteTime)}
            </div>
            <div
              style={{
                fontSize: "11px",
                color: "#71717a",
                marginTop: "4px",
                fontFamily: "var(--font-mono), ui-monospace, monospace",
              }}
              suppressHydrationWarning
            >
              {liteAgentCount} &times; 0.001s
            </div>
          </div>
        </div>
      </div>

      {/* ---- Token Cost Comparison ---- */}
      <div style={{ marginTop: "28px" }}>
        <h3 style={sectionTitle}>Token Cost per Tick</h3>
        <div style={monoBlock}>
          {renderCostBar(
            `Full Agents (${fullAgentCount})`,
            fullTokens,
            Math.max(fullTokens, 1),
            ACCENT,
          )}
          {renderCostBar(
            `Lightweight Agents (${liteAgentCount})`,
            liteTokens,
            Math.max(fullTokens, 1),
            "#4ade80",
          )}
          <div
            style={{
              marginTop: "12px",
              paddingTop: "12px",
              borderTop: "1px solid rgba(255,255,255,0.06)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
            }}
          >
            <span style={{ fontSize: "12px", color: "#a1a1aa" }}>Total</span>
            <span
              style={{
                fontSize: "14px",
                fontWeight: 700,
                color: "#fff",
                fontVariantNumeric: "tabular-nums",
                fontFamily: "var(--font-mono), ui-monospace, monospace",
              }}
              suppressHydrationWarning
            >
              {formatNumber(totalTokens)} tokens/tick
            </span>
          </div>
        </div>
      </div>

      {/* ---- Promotion Triggers ---- */}
      <div style={{ marginTop: "28px" }}>
        <h3 style={sectionTitle}>Promotion Triggers</h3>
        <p
          style={{
            fontSize: "12px",
            color: "#71717a",
            marginBottom: "12px",
            lineHeight: 1.5,
          }}
        >
          Conditions that promote a lightweight agent to full LLM reasoning:
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {PROMOTION_TRIGGERS.map((trigger) => {
            const active = triggers[trigger.id];
            return (
              <label
                key={trigger.id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  background: active
                    ? "rgba(232,121,249,0.08)"
                    : "rgba(255,255,255,0.03)",
                  border: `1px solid ${active ? `${ACCENT}44` : "rgba(255,255,255,0.06)"}`,
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggleTrigger(trigger.id)}
                  style={{
                    marginTop: "2px",
                    accentColor: ACCENT,
                    flexShrink: 0,
                  }}
                />
                <div>
                  <div
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: active ? "#e4e4e7" : "#71717a",
                      transition: "color 0.2s",
                    }}
                  >
                    {trigger.label}{" "}
                    <span
                      style={{
                        color: active ? "#4ade80" : "#71717a",
                        fontWeight: 700,
                        fontSize: "14px",
                      }}
                    >
                      {active ? "\u2713" : ""}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: "11px",
                      color: "#71717a",
                      marginTop: "2px",
                      lineHeight: 1.4,
                    }}
                  >
                    {trigger.description}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* ---- Simulate Button & Visualization ---- */}
      <div style={{ marginTop: "28px" }}>
        <h3 style={sectionTitle}>Simulation Demo</h3>

        <button
          className={`btn-mono${isSimulating ? " active" : ""}`}
          onClick={() => {
            if (isSimulating) {
              setIsSimulating(false);
            } else {
              startSimulation();
            }
          }}
          style={{ marginBottom: "16px" }}
        >
          {isSimulating ? "Stop" : "Simulate"} (50 agents: 5 full + 45 lightweight)
        </button>

        {/* Agent grid visualization */}
        {simAgents.length > 0 && (
          <div style={monoBlock}>
            {/* Legend */}
            <div
              style={{
                display: "flex",
                gap: "16px",
                marginBottom: "14px",
                flexWrap: "wrap",
              }}
            >
              {[
                { color: "rgba(255,255,255,0.1)", border: "transparent", label: "Idle" },
                { color: ACCENT_DIM, border: ACCENT, label: "Thinking (Full)" },
                { color: ACCENT, border: "transparent", label: "Done (Full)" },
                { color: "#4ade80", border: "transparent", label: "Done (Lightweight)" },
                { color: "#fbbf24", border: "#f59e0b", label: "Promoted" },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "11px",
                    color: "#71717a",
                  }}
                >
                  <div
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: item.color,
                      border: `1.5px solid ${item.border}`,
                      flexShrink: 0,
                    }}
                  />
                  {item.label}
                </div>
              ))}
            </div>

            {/* Full Agents Section */}
            <div style={{ marginBottom: "12px" }}>
              <div
                style={{
                  fontSize: "11px",
                  color: ACCENT,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: "8px",
                }}
              >
                Full Agents ({simAgents.filter((a) => a.type === "full").length})
              </div>
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                {simAgents
                  .filter((a) => a.type === "full")
                  .map((agent) => renderSimDot(agent))}
              </div>
            </div>

            {/* Lightweight Agents Section */}
            <div>
              <div
                style={{
                  fontSize: "11px",
                  color: "#4ade80",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: "8px",
                }}
              >
                Lightweight Agents ({simAgents.filter((a) => a.type === "lightweight").length})
              </div>
              <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                {simAgents
                  .filter((a) => a.type === "lightweight")
                  .map((agent) => renderSimDot(agent))}
              </div>
            </div>

            {/* Sim status */}
            {isSimulating && (
              <div
                style={{
                  marginTop: "14px",
                  paddingTop: "12px",
                  borderTop: "1px solid rgba(255,255,255,0.06)",
                  fontSize: "12px",
                  color: "#a1a1aa",
                }}
              >
                <span style={{ color: ACCENT, fontWeight: 600 }}>Step {simStep}</span>
                {" \u2014 "}
                {simStep < 1
                  ? "Initializing..."
                  : simStep < 2
                    ? "Lightweight agents completing instantly..."
                    : simStep < 8
                      ? "Full agents reasoning (Think\u2192Plan\u2192Act\u2192Reflect)..."
                      : simStep < 10
                        ? "2 lightweight agents promoted to full! (flash)"
                        : simStep < 15
                          ? "Promoted agents now reasoning with full LLM..."
                          : "Simulation complete."}
              </div>
            )}

            {!isSimulating && simAgents.length > 0 && simStep >= 16 && (
              <div
                style={{
                  marginTop: "14px",
                  paddingTop: "12px",
                  borderTop: "1px solid rgba(255,255,255,0.06)",
                  fontSize: "12px",
                  color: "#4ade80",
                  fontWeight: 600,
                }}
              >
                Simulation complete &mdash; 45 lightweight agents finished in &lt;0.05s, 5 full
                agents in ~15s. 2 agents were promoted mid-simulation.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
