"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";

/* ── Phase Definitions ─────────────────────────────────────────────── */

type PhaseIconName = "globe" | "users" | "message" | "save";

const PHASE_ICONS: Record<PhaseIconName, React.ReactNode> = {
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
    </>
  ),
  users: (
    <>
      <path d="M16 19v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V19" />
      <circle cx="9.5" cy="7.5" r="3" />
      <path d="M21 19v-1.5a4 4 0 0 0-3-3.87M16 4.6a3 3 0 0 1 0 5.8" />
    </>
  ),
  message: (
    <>
      <path d="M20 15a2 2 0 0 1-2 2H8l-4 3V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z" />
    </>
  ),
  save: (
    <>
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <path d="M17 21v-7H7v7M7 3v4h7" />
    </>
  ),
};

function PhaseIcon({ name }: { name: PhaseIconName }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PHASE_ICONS[name]}
    </svg>
  );
}

interface Phase {
  name: string;
  icon: PhaseIconName;
  description: string;
  detail: Record<string, unknown>;
}

const PHASES: Phase[] = [
  {
    name: "Environment",
    icon: "globe",
    description:
      "Environment agents generate world events and update hazard levels",
    detail: {
      hazard_level: "RISING \u2192 CRITICAL",
      new_event: "Bridge partially collapsed",
      locations_affected: ["Bridge", "River Bank"],
    },
  },
  {
    name: "Agents",
    icon: "users",
    description: "Human agents process in parallel scenes by location",
    detail: {
      "Scene 1 (Rooftop)": "Dr. Chen speaks, Marcus moves",
      "Scene 2 (Bridge)": "Amir plans evacuation",
      "Scene 3 (Town Hall)": "Leo helps Priya",
    },
  },
  {
    name: "Reactions",
    icon: "message",
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
    name: "Persist",
    icon: "save",
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
      border: "2px solid var(--accent)",
      boxShadow: "0 0 12px var(--accent-dim)",
    };
  }
  if (phaseIndex < completedUpTo) {
    return { border: "2px solid var(--pos)" };
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
            <span style={{ color: "var(--pos)" }}>
              &quot;{String(v)}&quot;
            </span>
          </span>
        ))}
        ]
      </span>
    );
  }
  if (typeof value === "boolean") {
    return <span style={{ color: value ? "var(--pos)" : "var(--agent)" }}>{String(value)}</span>;
  }
  if (typeof value === "number") {
    return <span style={{ color: "var(--accent)" }}>{value}</span>;
  }
  return <span style={{ color: "var(--text-primary)" }}>&quot;{String(value)}&quot;</span>;
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
    <div className="widget-container" suppressHydrationWarning>
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
            color: "var(--text-secondary)",
          }}
        >
          Step:{" "}
          <span style={{ color: "var(--pos)", fontWeight: 700 }}>
            {stepNumber}
          </span>{" "}
          of &infin;
        </span>
        {tickComplete && (
          <span
            style={{
              fontFamily: "var(--font-mono, monospace)",
              fontSize: "13px",
              color: "var(--pos)",
              fontWeight: 700,
              animation: "rise var(--dur) var(--ease)",
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
                    ? "var(--accent-dim)"
                    : completedUpTo > idx
                      ? "var(--pos-dim)"
                      : "rgba(255,255,255,0.03)",
                cursor: "pointer",
                transition: "border-color var(--dur) var(--ease), background-color var(--dur) var(--ease)",
                ...borderStyle(idx, currentPhase, completedUpTo),
              }}
            >
              {/* Icon */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  color:
                    currentPhase === idx
                      ? "var(--accent)"
                      : completedUpTo > idx
                        ? "var(--pos)"
                        : "var(--text-muted)",
                  marginBottom: "8px",
                }}
              >
                <PhaseIcon name={phase.icon} />
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
                    borderRadius: "4px",
                    fontSize: "11px",
                    fontWeight: 500,
                    fontFamily: "var(--font-mono, monospace)",
                    color:
                      currentPhase === idx
                        ? "var(--accent)"
                        : "var(--text-secondary)",
                    background:
                      currentPhase === idx
                        ? "var(--accent-dim)"
                        : "var(--surface-alt)",
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
                  color: "var(--text-secondary)",
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
                    completedUpTo > idx ? "var(--pos)" : "rgba(255,255,255,0.2)",
                  fontSize: "18px",
                  fontWeight: 700,
                  transition: "color var(--dur) var(--ease)",
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
            border: "1px solid var(--line)",
            background: "var(--inset)",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "12px",
            lineHeight: 1.7,
            animation: "rise var(--dur) var(--ease)",
          }}
        >
          {/* Description */}
          <div
            style={{
              color: "var(--text-primary)",
              fontWeight: 500,
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
              <span style={{ color: "var(--text-secondary)", minWidth: "160px", flexShrink: 0 }}>
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
            background: "var(--pos)",
            borderRadius: "4px",
            transition: "width var(--dur) var(--ease)",
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
            borderColor: isAutoRunning ? "var(--pos)" : undefined,
            color: isAutoRunning ? "var(--pos)" : undefined,
          }}
        >
          {isAutoRunning ? "Stop Auto" : "Auto Run"}
        </button>
        <button className="btn-mono" onClick={handleReset}>
          Reset
        </button>
      </div>

    </div>
  );
}
