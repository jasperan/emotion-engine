"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";

interface Location {
  name: string;
  hazard: "HIGH" | "MEDIUM" | "LOW";
  agents: string[];
}

const ACCENT = "var(--accent)";

const HAZARD_COLORS: Record<string, { bg: string; text: string }> = {
  HIGH: { bg: "var(--neg-dim)", text: "var(--neg)" },
  MEDIUM: { bg: "var(--warn-dim)", text: "var(--warn)" },
  LOW: { bg: "var(--pos-dim)", text: "var(--pos)" },
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
    <div className="widget-container" suppressHydrationWarning>
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
                  processingMode === mode ? "var(--accent-dim)" : "transparent",
                color: processingMode === mode ? "var(--accent)" : "var(--text-secondary)",
                fontWeight: 500,
                border: "none",
                borderRadius: 0,
                padding: "6px 14px",
                fontSize: "12px",
                cursor: isSimulating ? "not-allowed" : "pointer",
                transition: "border-color var(--dur) var(--ease), background-color var(--dur) var(--ease)",
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
              color: "var(--text-muted)",
              marginLeft: "8px",
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
                  ? "var(--accent-dim)"
                  : "rgba(255,255,255,0.03)",
                border: isTarget
                  ? `1.5px dashed ${ACCENT}`
                  : "1px solid rgba(255,255,255,0.08)",
                cursor: isTarget ? "pointer" : "default",
                transition: "border-color var(--dur) var(--ease), background-color var(--dur) var(--ease)",
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
                      color: "var(--text-primary)",
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
                    }}
                  >
                    {loc.hazard.toLowerCase()}
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
                        color: "var(--text-secondary)",
                        fontWeight: 500,
                      }}
                    >
                      Scene {sceneNum}
                    </span>
                    {sceneState && (
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 500,
                          padding: "2px 7px",
                          borderRadius: "4px",
                          background:
                            sceneState === "Running"
                              ? "var(--pos-dim)"
                              : "var(--agent-dim)",
                          color:
                            sceneState === "Running" ? "var(--pos)" : "var(--agent)",
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
                      color: "var(--text-muted)",
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
                        color: isSelected ? "var(--inset)" : "var(--text-primary)",
                        background: isSelected
                          ? ACCENT
                          : "rgba(255,255,255,0.07)",
                        border: isSelected
                          ? `2px solid ${ACCENT}`
                          : "1px solid rgba(255,255,255,0.12)",
                        cursor: isSimulating ? "not-allowed" : "pointer",
                        transition: "border-color var(--dur) var(--ease), background-color var(--dur) var(--ease)",
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
                  color: "var(--text-muted)",
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
          background: "var(--inset)",
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
              fontSize: "12px",
              fontWeight: 500,
              color: "var(--text-muted)",
              marginBottom: "4px",
            }}
          >
            Processing time estimate
          </div>
          <div
            style={{
              fontSize: "13px",
              color: "var(--text-secondary)",
              lineHeight: 1.5,
            }}
            suppressHydrationWarning
          >
            Sequential ~{sceneCount}s per step &middot; parallel ~1s per step
          </div>
        </div>
      </div>

    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{
          fontSize: "12px",
          fontWeight: 500,
          color: "var(--text-muted)",
          marginBottom: "4px",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "18px",
          fontWeight: 700,
          color: "var(--text-primary)",
          fontVariantNumeric: "tabular-nums",
        }}
        suppressHydrationWarning
      >
        {value}
      </div>
    </div>
  );
}
