"use client";

import React, { useState, useRef, useCallback } from "react";

interface Agent {
  name: string;
  stress: number;
}

const AGENT_NAMES = [
  "Dr. Chen", "Marcus", "Sofia", "Amir",
  "Yuki", "Leo", "Priya", "Noah",
  "Elena", "Kai", "Ruby", "Omar",
];

const INITIAL_STRESS = 2;
const SPREAD_RATE = 0.3;
const MAX_DELTA = 2;
const CALM_FACTOR = 0.5;
const AUTO_INTERVAL_MS = 800;

function stressColor(stress: number): string {
  if (stress <= 2) return "var(--pos)";
  if (stress <= 5) return "color-mix(in srgb, var(--warn) 55%, var(--text-secondary))";
  if (stress <= 8) return "var(--warn)";
  return "var(--neg)";
}

function createInitialAgents(): Agent[] {
  return AGENT_NAMES.map((name) => ({ name, stress: INITIAL_STRESS }));
}

export default function EmotionContagionWidget() {
  const [agents, setAgents] = useState<Agent[]>(createInitialAgents);
  const [step, setStep] = useState(0);
  const [isAutoRunning, setIsAutoRunning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const propagateStep = useCallback((currentAgents: Agent[]): Agent[] => {
    const totalAgents = currentAgents.length;
    return currentAgents.map((agent) => {
      const othersStressSum = currentAgents.reduce(
        (sum, other) => (other.name === agent.name ? sum : sum + other.stress),
        0
      );
      const avgNeighborStress = othersStressSum / (totalAgents - 1);
      const stressInfluence = avgNeighborStress * SPREAD_RATE;
      const delta = Math.min(
        stressInfluence - agent.stress * CALM_FACTOR * 0.1,
        MAX_DELTA
      );
      const newStress = Math.max(0, Math.min(10, agent.stress + delta));
      return { ...agent, stress: Math.round(newStress * 100) / 100 };
    });
  }, []);

  const handlePropagate = useCallback(() => {
    setAgents((prev) => propagateStep(prev));
    setStep((prev) => prev + 1);
  }, [propagateStep]);

  const handleAutoToggle = useCallback(() => {
    if (isAutoRunning) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsAutoRunning(false);
    } else {
      setIsAutoRunning(true);
      intervalRef.current = setInterval(() => {
        setAgents((prev) => propagateStep(prev));
        setStep((prev) => prev + 1);
      }, AUTO_INTERVAL_MS);
    }
  }, [isAutoRunning, propagateStep]);

  const handleReset = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsAutoRunning(false);
    setAgents(createInitialAgents());
    setStep(0);
  }, []);

  const handleAgentClick = useCallback((index: number) => {
    setAgents((prev) =>
      prev.map((agent, i) =>
        i === index ? { ...agent, stress: 10 } : agent
      )
    );
  }, []);

  const avgStress =
    agents.reduce((sum, a) => sum + a.stress, 0) / agents.length;

  return (
    <div className="widget-container" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Emotion Contagion</div>

      {/* Controls */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px", flexWrap: "wrap" }}>
        <button className="btn-mono" onClick={handlePropagate}>
          Propagate
        </button>
        <button
          className={`btn-mono${isAutoRunning ? " active" : ""}`}
          onClick={handleAutoToggle}
        >
          {isAutoRunning ? "Stop Auto" : "Auto Propagate"}
        </button>
        <button className="btn-mono" onClick={handleReset}>
          Reset
        </button>
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-4 sm:grid-cols-6 gap-5 max-w-[600px] mx-auto mb-6">
        {agents.map((agent, i) => {
          const color = stressColor(agent.stress);
          const isHighStress = agent.stress >= 7;
          return (
            <div
              key={agent.name}
              onClick={() => handleAgentClick(i)}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                cursor: "pointer",
              }}
            >
              <div
                style={{
                  width: "64px",
                  height: "64px",
                  borderRadius: "50%",
                  background: `color-mix(in srgb, ${color} 13%, transparent)`,
                  border: `2px solid ${color}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "16px",
                  fontWeight: 700,
                  color: color,
                  transition:
                    "border-color var(--dur) var(--ease), background-color var(--dur) var(--ease), color var(--dur) var(--ease)",
                  fontVariantNumeric: "tabular-nums",
                }}
                suppressHydrationWarning
              >
                {agent.stress.toFixed(1)}
              </div>
              <span
                style={{
                  marginTop: "6px",
                  fontSize: "11px",
                  color: "var(--text-secondary)",
                  textAlign: "center",
                  lineHeight: 1.2,
                  whiteSpace: "nowrap",
                }}
              >
                {agent.name}
              </span>
            </div>
          );
        })}
      </div>

      {/* Stats */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "24px",
          marginBottom: "16px",
          fontSize: "13px",
          color: "var(--text-secondary)",
        }}
      >
        <span>
          Step:{" "}
          <span
            style={{ color: "var(--text-primary)", fontWeight: 500, fontVariantNumeric: "tabular-nums" }}
            suppressHydrationWarning
          >
            {step}
          </span>
        </span>
        <span>
          Avg Stress:{" "}
          <span
            style={{
              color: stressColor(avgStress),
              fontWeight: 700,
              fontVariantNumeric: "tabular-nums",
            }}
            suppressHydrationWarning
          >
            {avgStress.toFixed(2)}
          </span>
        </span>
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "16px",
          flexWrap: "wrap",
          fontSize: "11px",
          color: "var(--text-secondary)",
        }}
      >
        {[
          { color: "var(--pos)", label: "0-2 Calm" },
          { color: "color-mix(in srgb, var(--warn) 55%, var(--text-secondary))", label: "3-5 Tense" },
          { color: "var(--warn)", label: "6-8 Stressed" },
          { color: "var(--neg)", label: "9-10 Panic" },
        ].map((item) => (
          <div
            key={item.label}
            style={{ display: "flex", alignItems: "center", gap: "4px" }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: item.color,
              }}
            />
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      {/* Tip */}
      <p
        style={{
          textAlign: "center",
          fontSize: "11px",
          color: "var(--text-muted)",
          marginTop: "12px",
          marginBottom: 0,
        }}
      >
        Click any agent to trigger panic (stress 10), then propagate to watch contagion spread.
      </p>

    </div>
  );
}
