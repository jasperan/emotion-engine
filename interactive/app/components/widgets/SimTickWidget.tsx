"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";

/* ── Phase Definitions ─────────────────────────────────────────────── */

interface Phase {
  name: string;
  icon: string;
  badgeColor: string;
  description: string;
  detail: Record<string, unknown>;
}

const PHASES: Phase[] = [
  {
    name: "ENVIRONMENT",
    icon: "\u{1F30D}",
    badgeColor: "#34d399",
    description:
      "Environment agents generate world events and update hazard levels",
    detail: {
      hazard_level: "RISING \u2192 CRITICAL",
      new_event: "Bridge partially collapsed",
      locations_affected: ["Bridge", "River Bank"],
    },
  },
  {
    name: "AGENTS",
    icon: "\u{1F9D1}\u200D\u{1F91D}\u200D\u{1F9D1}",
    badgeColor: "#22d3ee",
    description: "Human agents process in parallel scenes by location",
    detail: {
      "Scene 1 (Rooftop)": "Dr. Chen speaks, Marcus moves",
      "Scene 2 (Bridge)": "Amir plans evacuation",
      "Scene 3 (Town Hall)": "Leo helps Priya",
    },
  },
  {
    name: "REACTIONS",
    icon: "\u{1F4AC}",
    badgeColor: "#f472b6",
    description: "Reaction round for intra-step responses",
    detail: {
      reactions: [
        "Marcus responds to Dr. Chen\u2019s call",
        "Priya thanks Leo for help",
      ],
      conversations_updated: 2,
    },
  },
  {
    name: "PERSIST",
    icon: "\u{1F4BE}",
    badgeColor: "#facc15",
    description:
      "State snapshot saved, WebSocket events emitted, consensus check",
    detail: {
      step: 7,
      agents_alive: 10,
      consensus: false,
      events_emitted: 14,
      token_budget_used: "12,450 / 50,000",
    },
  },
];

const PHASE_DURATION_MS = 1000;
const AUTO_PAUSE_BETWEEN_TICKS_MS = 600;

/* ── Helpers ───────────────────────────────────────────────────────── */

function borderStyle(
  phaseIndex: number,
  currentPhase: number,
  completedUpTo: number
): React.CSSProperties {
  if (phaseIndex === currentPhase) {
    return {
      border: "2px solid #22d3ee",
      boxShadow: "0 0 12px rgba(34,211,238,0.45)",
    };
  }
  if (phaseIndex < completedUpTo) {
    return { border: "2px solid #34d399" };
  }
  return { border: "2px solid rgba(255,255,255,0.12)" };
}

function renderDetailValue(value: unknown): React.ReactNode {
  if (Array.isArray(value)) {
    return (
      <span>
        [
        {value.map((v, i) => (
          <span key={i}>
            {i > 0 && ", "}
            <span style={{ color: "#34d399" }}>
              &quot;{String(v)}&quot;
            </span>
          </span>
        ))}
        ]
      </span>
    );
  }
  if (typeof value === "boolean") {
    return <span style={{ color: value ? "#34d399" : "#f472b6" }}>{String(value)}</span>;
  }
  if (typeof value === "number") {
    return <span style={{ color: "#22d3ee" }}>{value}</span>;
  }
  return <span style={{ color: "#e2e8f0" }}>&quot;{String(value)}&quot;</span>;
}

/* ── Component ─────────────────────────────────────────────────────── */

export default function SimTickWidget() {
  const [currentPhase, setCurrentPhase] = useState(-1); // -1 = idle
  const [completedUpTo, setCompletedUpTo] = useState(0);
  const [stepNumber, setStepNumber] = useState(7);
  const [isRunningFullTick, setIsRunningFullTick] = useState(false);
  const [isAutoRunning, setIsAutoRunning] = useState(false);
  const [tickComplete, setTickComplete] = useState(false);
  const [expandedPhase, setExpandedPhase] = useState<number | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (autoRef.current) clearTimeout(autoRef.current);
    };
  }, []);

  /* ── Step Through (one phase at a time) ──────────────────── */

  const stepThrough = useCallback(() => {
    if (isRunningFullTick || isAutoRunning) return;

    setTickComplete(false);

    setCurrentPhase((prev) => {
      const next = prev + 1;
      if (next >= PHASES.length) {
        // Completed full tick
        setCompletedUpTo(PHASES.length);
        setStepNumber((s) => s + 1);
        setTickComplete(true);
        // Reset for next tick after brief pause
        setTimeout(() => {
          if (!isMountedRef.current) return;
          setCurrentPhase(-1);
          setCompletedUpTo(0);
          setTickComplete(false);
        }, 1500);
        return prev; // stay on last phase visually
      }
      setCompletedUpTo(next);
      setExpandedPhase(next);
      return next;
    });
  }, [isRunningFullTick, isAutoRunning]);

  /* ── Run Full Tick (all 4 phases, animated) ──────────────── */

  const runFullTick = useCallback(() => {
    if (isRunningFullTick) return;
    setIsRunningFullTick(true);
    setTickComplete(false);
    setCurrentPhase(0);
    setCompletedUpTo(0);
    setExpandedPhase(0);

    let phase = 0;
    const advance = () => {
      if (!isMountedRef.current) return;
      phase++;
      if (phase < PHASES.length) {
        setCurrentPhase(phase);
        setCompletedUpTo(phase);
        setExpandedPhase(phase);
        timerRef.current = setTimeout(advance, PHASE_DURATION_MS);
      } else {
        // All phases done
        setCompletedUpTo(PHASES.length);
        setStepNumber((s) => s + 1);
        setTickComplete(true);
        setIsRunningFullTick(false);
        timerRef.current = setTimeout(() => {
          if (!isMountedRef.current) return;
          setCurrentPhase(-1);
          setCompletedUpTo(0);
          setTickComplete(false);
        }, 1500);
      }
    };
    timerRef.current = setTimeout(advance, PHASE_DURATION_MS);
  }, [isRunningFullTick]);

  /* ── Auto Run ────────────────────────────────────────────── */

  const runAutoTick = useCallback(() => {
    // Run a single full tick and schedule the next one
    setTickComplete(false);
    setCurrentPhase(0);
    setCompletedUpTo(0);
    setExpandedPhase(0);

    let phase = 0;
    const advance = () => {
      if (!isMountedRef.current) return;
      phase++;
      if (phase < PHASES.length) {
        setCurrentPhase(phase);
        setCompletedUpTo(phase);
        setExpandedPhase(phase);
        timerRef.current = setTimeout(advance, PHASE_DURATION_MS);
      } else {
        setCompletedUpTo(PHASES.length);
        setStepNumber((s) => s + 1);
        setTickComplete(true);
        // Brief pause then start next tick
        autoRef.current = setTimeout(() => {
          if (!isMountedRef.current) return;
          setCurrentPhase(-1);
          setCompletedUpTo(0);
          setTickComplete(false);
          // Schedule next tick
          autoRef.current = setTimeout(() => {
            if (!isMountedRef.current) return;
            runAutoTick();
          }, AUTO_PAUSE_BETWEEN_TICKS_MS);
        }, 800);
      }
    };
    timerRef.current = setTimeout(advance, PHASE_DURATION_MS);
  }, []);

  const toggleAutoRun = useCallback(() => {
    if (isAutoRunning) {
      // Stop
      if (timerRef.current) clearTimeout(timerRef.current);
      if (autoRef.current) clearTimeout(autoRef.current);
      timerRef.current = null;
      autoRef.current = null;
      setIsAutoRunning(false);
      setIsRunningFullTick(false);
      setCurrentPhase(-1);
      setCompletedUpTo(0);
      setTickComplete(false);
    } else {
      // Start
      setIsAutoRunning(true);
      runAutoTick();
    }
  }, [isAutoRunning, runAutoTick]);

  /* ── Reset ───────────────────────────────────────────────── */

  const handleReset = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (autoRef.current) clearTimeout(autoRef.current);
    timerRef.current = null;
    autoRef.current = null;
    setCurrentPhase(-1);
    setCompletedUpTo(0);
    setStepNumber(7);
    setIsRunningFullTick(false);
    setIsAutoRunning(false);
    setTickComplete(false);
    setExpandedPhase(null);
  }, []);

  /* ── Progress ────────────────────────────────────────────── */

  const progressPercent =
    currentPhase === -1
      ? tickComplete
        ? 100
        : 0
      : ((currentPhase + 1) / PHASES.length) * 100;

  /* ── Render ──────────────────────────────────────────────── */

  return (
    <div className="widget-container s-tick" suppressHydrationWarning>
      <div className="widget-label">
        Interactive &middot; Simulation Tick Loop
      </div>

      {/* Step Counter */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "14px",
            color: "#94a3b8",
          }}
        >
          Step:{" "}
          <span style={{ color: "#34d399", fontWeight: 700 }}>
            {stepNumber}
          </span>{" "}
          of &infin;
        </span>
        {tickComplete && (
          <span
            style={{
              fontFamily: "var(--font-mono, monospace)",
              fontSize: "13px",
              color: "#34d399",
              fontWeight: 700,
              animation: "fadeIn 0.3s ease",
            }}
          >
            Tick Complete
          </span>
        )}
      </div>

      {/* Phase Boxes Row */}
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          gap: "0",
          marginBottom: "20px",
          overflowX: "auto",
        }}
      >
        {PHASES.map((phase, idx) => (
          <React.Fragment key={phase.name}>
            {/* Phase Box */}
            <div
              onClick={() =>
                setExpandedPhase(expandedPhase === idx ? null : idx)
              }
              style={{
                flex: "1 1 0",
                minWidth: "110px",
                padding: "12px 10px",
                borderRadius: "8px",
                background:
                  currentPhase === idx
                    ? "rgba(34,211,238,0.08)"
                    : completedUpTo > idx
                      ? "rgba(52,211,153,0.06)"
                      : "rgba(255,255,255,0.03)",
                cursor: "pointer",
                transition: "all 0.3s ease",
                ...borderStyle(idx, currentPhase, completedUpTo),
              }}
            >
              {/* Icon */}
              <div
                style={{
                  fontSize: "20px",
                  textAlign: "center",
                  marginBottom: "6px",
                }}
              >
                {phase.icon}
              </div>
              {/* Badge */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  marginBottom: "4px",
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    borderRadius: "9999px",
                    fontSize: "11px",
                    fontWeight: 700,
                    fontFamily: "var(--font-mono, monospace)",
                    letterSpacing: "0.05em",
                    color: "#0f172a",
                    background: phase.badgeColor,
                  }}
                >
                  {phase.name}
                </span>
              </div>
              {/* Phase number */}
              <div
                style={{
                  textAlign: "center",
                  fontSize: "10px",
                  color: "#64748b",
                  fontFamily: "var(--font-mono, monospace)",
                }}
              >
                Phase {idx + 1}
              </div>
            </div>

            {/* Arrow between boxes */}
            {idx < PHASES.length - 1 && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "0 4px",
                  color:
                    completedUpTo > idx ? "#34d399" : "rgba(255,255,255,0.2)",
                  fontSize: "18px",
                  fontWeight: 700,
                  transition: "color 0.3s ease",
                  flexShrink: 0,
                }}
              >
                &rarr;
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Expanded Detail Panel */}
      {expandedPhase !== null && (
        <div
          style={{
            marginBottom: "20px",
            padding: "14px 16px",
            borderRadius: "8px",
            border: `1px solid ${PHASES[expandedPhase].badgeColor}44`,
            background: "rgba(0,0,0,0.25)",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "12px",
            lineHeight: 1.7,
            animation: "fadeIn 0.25s ease",
          }}
        >
          {/* Description */}
          <div
            style={{
              color: PHASES[expandedPhase].badgeColor,
              fontWeight: 600,
              marginBottom: "10px",
              fontSize: "13px",
            }}
          >
            {PHASES[expandedPhase].description}
          </div>

          {/* Key-value pairs */}
          {Object.entries(PHASES[expandedPhase].detail).map(([key, value]) => (
            <div
              key={key}
              style={{
                display: "flex",
                gap: "8px",
                padding: "3px 0",
                borderBottom: "1px solid rgba(255,255,255,0.05)",
              }}
            >
              <span style={{ color: "#64748b", minWidth: "160px", flexShrink: 0 }}>
                {key}:
              </span>
              <span>{renderDetailValue(value)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Progress Bar */}
      <div
        style={{
          marginBottom: "16px",
          background: "rgba(255,255,255,0.06)",
          borderRadius: "4px",
          height: "6px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${progressPercent}%`,
            background:
              tickComplete
                ? "#34d399"
                : "linear-gradient(90deg, #34d399, #22d3ee)",
            borderRadius: "4px",
            transition: "width 0.4s ease",
          }}
        />
      </div>

      {/* Controls */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        <button
          className="btn-mono"
          onClick={stepThrough}
          disabled={isRunningFullTick || isAutoRunning}
          style={{
            opacity: isRunningFullTick || isAutoRunning ? 0.4 : 1,
            cursor:
              isRunningFullTick || isAutoRunning ? "not-allowed" : "pointer",
          }}
        >
          Step Through
        </button>
        <button
          className="btn-mono"
          onClick={runFullTick}
          disabled={isRunningFullTick || isAutoRunning}
          style={{
            opacity: isRunningFullTick || isAutoRunning ? 0.4 : 1,
            cursor:
              isRunningFullTick || isAutoRunning ? "not-allowed" : "pointer",
          }}
        >
          Run Full Tick
        </button>
        <button
          className={`btn-mono${isAutoRunning ? " active" : ""}`}
          onClick={toggleAutoRun}
          style={{
            borderColor: isAutoRunning ? "#34d399" : undefined,
            color: isAutoRunning ? "#34d399" : undefined,
          }}
        >
          {isAutoRunning ? "Stop Auto" : "Auto Run"}
        </button>
        <button className="btn-mono" onClick={handleReset}>
          Reset
        </button>
      </div>

      {/* Inline animation keyframes */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
