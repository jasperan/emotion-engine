"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";

interface Location {
  name: string;
  hazard: "HIGH" | "MEDIUM" | "LOW";
  agents: string[];
}

const ACCENT = "#38bdf8";

const HAZARD_COLORS: Record<string, { bg: string; text: string }> = {
  HIGH: { bg: "rgba(239,68,68,0.15)", text: "#ef4444" },
  MEDIUM: { bg: "rgba(234,179,8,0.15)", text: "#eab308" },
  LOW: { bg: "rgba(34,197,94,0.15)", text: "#22c55e" },
};

const INITIAL_LOCATIONS: Location[] = [
  { name: "Rooftop", hazard: "HIGH", agents: ["Dr. Chen", "Marcus", "Sofia"] },
  { name: "Bridge", hazard: "MEDIUM", agents: ["Amir", "Yuki"] },
  { name: "Town Hall", hazard: "LOW", agents: ["Leo", "Priya", "Noah"] },
];

function deepCloneLocations(locs: Location[]): Location[] {
  return locs.map((l) => ({ ...l, agents: [...l.agents] }));
}

export default function SceneDirectorWidget() {
  const [locations, setLocations] = useState<Location[]>(
    deepCloneLocations(INITIAL_LOCATIONS)
  );
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [processingMode, setProcessingMode] = useState<
    "Parallel" | "Sequential"
  >("Parallel");
  const [sceneStates, setSceneStates] = useState<
    Record<string, "Idle" | "Running" | "Done">
  >({});
  const [isSimulating, setIsSimulating] = useState(false);
  const timerRefs = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      timerRefs.current.forEach(clearTimeout);
    };
  }, []);

  // Compute active scenes (locations with at least 1 agent)
  const activeScenes = locations.filter((l) => l.agents.length > 0);
  const sceneCount = activeScenes.length;
  const maxSceneSize = Math.max(...locations.map((l) => l.agents.length), 0);
  const parallelGain = sceneCount > 0 ? sceneCount : 1;

  const handleAgentClick = useCallback(
    (agentName: string) => {
      if (isSimulating) return;
      setSelectedAgent((prev) => (prev === agentName ? null : agentName));
    },
    [isSimulating]
  );

  const handleLocationClick = useCallback(
    (targetLocationName: string) => {
      if (!selectedAgent || isSimulating) return;

      setLocations((prev) => {
        const next = deepCloneLocations(prev);
        // Find and remove agent from current location
        for (const loc of next) {
          const idx = loc.agents.indexOf(selectedAgent);
          if (idx !== -1) {
            loc.agents.splice(idx, 1);
            break;
          }
        }
        // Add to target location
        const target = next.find((l) => l.name === targetLocationName);
        if (target && !target.agents.includes(selectedAgent)) {
          target.agents.push(selectedAgent);
        }
        return next;
      });
      setSelectedAgent(null);
    },
    [selectedAgent, isSimulating]
  );

  const handleReset = useCallback(() => {
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
    setLocations(deepCloneLocations(INITIAL_LOCATIONS));
    setSelectedAgent(null);
    setSceneStates({});
    setIsSimulating(false);
  }, []);

  const handleSimulateStep = useCallback(() => {
    if (isSimulating) return;
    setIsSimulating(true);

    const scenes = locations.filter((l) => l.agents.length > 0);

    if (processingMode === "Parallel") {
      // All scenes run at once
      const running: Record<string, "Running"> = {};
      scenes.forEach((s) => {
        running[s.name] = "Running";
      });
      setSceneStates(running);

      const t = setTimeout(() => {
        const done: Record<string, "Done"> = {};
        scenes.forEach((s) => {
          done[s.name] = "Done";
        });
        setSceneStates(done);

        const t2 = setTimeout(() => {
          setSceneStates({});
          setIsSimulating(false);
        }, 800);
        timerRefs.current.push(t2);
      }, 1000);
      timerRefs.current.push(t);
    } else {
      // Sequential: one at a time
      scenes.forEach((scene, i) => {
        const tStart = setTimeout(() => {
          setSceneStates((prev) => ({ ...prev, [scene.name]: "Running" }));
        }, i * 1000);
        timerRefs.current.push(tStart);

        const tDone = setTimeout(() => {
          setSceneStates((prev) => ({ ...prev, [scene.name]: "Done" }));
        }, (i + 1) * 1000);
        timerRefs.current.push(tDone);
      });

      const tClear = setTimeout(() => {
        setSceneStates({});
        setIsSimulating(false);
      }, scenes.length * 1000 + 800);
      timerRefs.current.push(tClear);
    }
  }, [isSimulating, locations, processingMode]);

  // Find which location the selected agent is in
  const selectedAgentLocation = selectedAgent
    ? locations.find((l) => l.agents.includes(selectedAgent))?.name ?? null
    : null;

  // Assign scene numbers only to locations with agents
  const sceneNumberMap: Record<string, number> = {};
  let sceneIdx = 1;
  for (const loc of locations) {
    if (loc.agents.length > 0) {
      sceneNumberMap[loc.name] = sceneIdx++;
    }
  }

  return (
    <div className="widget-container s-scene" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Scene Director</div>

      {/* Controls Row */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "16px",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {/* Processing Mode Toggle */}
        <div
          style={{
            display: "flex",
            borderRadius: "6px",
            overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          {(["Parallel", "Sequential"] as const).map((mode) => (
            <button
              key={mode}
              className="btn-mono"
              onClick={() => !isSimulating && setProcessingMode(mode)}
              style={{
                background:
                  processingMode === mode ? ACCENT : "rgba(255,255,255,0.04)",
                color: processingMode === mode ? "#0c0d14" : "#a1a1aa",
                fontWeight: processingMode === mode ? 700 : 500,
                border: "none",
                borderRadius: 0,
                padding: "6px 14px",
                fontSize: "12px",
                cursor: isSimulating ? "not-allowed" : "pointer",
                transition: "all 0.2s ease",
              }}
            >
              {mode}
            </button>
          ))}
        </div>

        <button
          className="btn-mono"
          onClick={handleSimulateStep}
          disabled={isSimulating}
          style={{
            opacity: isSimulating ? 0.5 : 1,
            cursor: isSimulating ? "not-allowed" : "pointer",
          }}
        >
          Simulate Step
        </button>
        <button className="btn-mono" onClick={handleReset}>
          Reset
        </button>

        {selectedAgent && (
          <span
            style={{
              fontSize: "12px",
              color: ACCENT,
              marginLeft: "8px",
              fontStyle: "italic",
            }}
          >
            Click a location to move {selectedAgent}
          </span>
        )}
      </div>

      {/* Location Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {locations.map((loc) => {
          const hazardStyle = HAZARD_COLORS[loc.hazard];
          const isTarget = selectedAgent !== null && selectedAgentLocation !== loc.name;
          const sceneNum = sceneNumberMap[loc.name];
          const sceneState = sceneStates[loc.name];

          return (
            <div
              key={loc.name}
              onClick={() => isTarget && handleLocationClick(loc.name)}
              style={{
                padding: "16px",
                borderRadius: "10px",
                background: isTarget
                  ? "rgba(56,189,248,0.06)"
                  : "rgba(255,255,255,0.03)",
                border: isTarget
                  ? `1.5px dashed ${ACCENT}`
                  : "1px solid rgba(255,255,255,0.08)",
                cursor: isTarget ? "pointer" : "default",
                transition: "all 0.25s ease",
                minHeight: "120px",
              }}
            >
              {/* Location header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    style={{
                      fontSize: "14px",
                      fontWeight: 700,
                      color: "#fff",
                    }}
                  >
                    {loc.name}
                  </span>
                  {/* Hazard badge */}
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      padding: "2px 7px",
                      borderRadius: "4px",
                      background: hazardStyle.bg,
                      color: hazardStyle.text,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {loc.hazard}
                  </span>
                </div>
                {/* Scene label */}
                {sceneNum !== undefined && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11px",
                        color: "#a1a1aa",
                        fontWeight: 500,
                      }}
                    >
                      Scene {sceneNum}
                    </span>
                    {sceneState && (
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "2px 7px",
                          borderRadius: "4px",
                          background:
                            sceneState === "Running"
                              ? "rgba(34,197,94,0.15)"
                              : "rgba(99,102,241,0.15)",
                          color:
                            sceneState === "Running" ? "#22c55e" : "#818cf8",
                          textTransform: "uppercase",
                          letterSpacing: "0.04em",
                          animation:
                            sceneState === "Running"
                              ? "pulse-badge 1s ease-in-out infinite"
                              : "none",
                        }}
                      >
                        {sceneState}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Agent pills */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "6px",
                  minHeight: "32px",
                }}
              >
                {loc.agents.length === 0 && (
                  <span
                    style={{
                      fontSize: "12px",
                      color: "#52525b",
                      fontStyle: "italic",
                    }}
                  >
                    No agents
                  </span>
                )}
                {loc.agents.map((agent) => {
                  const isSelected = selectedAgent === agent;
                  return (
                    <button
                      key={agent}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAgentClick(agent);
                      }}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "4px 10px",
                        borderRadius: "999px",
                        fontSize: "12px",
                        fontWeight: 600,
                        color: isSelected ? "#0c0d14" : "#d4d4d8",
                        background: isSelected
                          ? ACCENT
                          : "rgba(255,255,255,0.07)",
                        border: isSelected
                          ? `2px solid ${ACCENT}`
                          : "1px solid rgba(255,255,255,0.12)",
                        cursor: isSimulating ? "not-allowed" : "pointer",
                        transition: "all 0.2s ease",
                        transform: isSelected ? "scale(1.05)" : "scale(1)",
                        fontFamily: "inherit",
                        lineHeight: 1.4,
                      }}
                    >
                      {agent}
                    </button>
                  );
                })}
              </div>

              {/* Agent count */}
              <div
                style={{
                  marginTop: "10px",
                  fontSize: "11px",
                  color: "#52525b",
                }}
              >
                {loc.agents.length} agent{loc.agents.length !== 1 ? "s" : ""}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Panel */}
      <div
        style={{
          marginTop: "20px",
          padding: "14px 16px",
          borderRadius: "8px",
          background: "#12131a",
          border: "1px solid rgba(255,255,255,0.08)",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "12px",
        }}
      >
        <SummaryStat label="Scenes" value={String(sceneCount)} />
        <SummaryStat
          label="Max scene size"
          value={`${maxSceneSize} agent${maxSceneSize !== 1 ? "s" : ""}`}
        />
        <SummaryStat label="Parallelism gain" value={`${parallelGain}x`} />
        <div>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: ACCENT,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "4px",
            }}
          >
            Processing time estimate
          </div>
          <div
            style={{
              fontSize: "13px",
              color: "#a1a1aa",
              lineHeight: 1.5,
            }}
            suppressHydrationWarning
          >
            Sequential: ~{sceneCount}s per step | Parallel: ~1s per step
          </div>
        </div>
      </div>

      {/* Inline keyframes for the pulse animation */}
      <style>{`
        @keyframes pulse-badge {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{
          fontSize: "11px",
          fontWeight: 600,
          color: ACCENT,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "4px",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "18px",
          fontWeight: 700,
          color: "#fff",
          fontVariantNumeric: "tabular-nums",
        }}
        suppressHydrationWarning
      >
        {value}
      </div>
    </div>
  );
}
