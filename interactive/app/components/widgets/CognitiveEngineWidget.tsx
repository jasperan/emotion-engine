"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";

/* ------------------------------------------------------------------ */
/*  Stage definitions                                                  */
/* ------------------------------------------------------------------ */

interface StageInfo {
  name: string;
  description: string;
}

const STAGES: StageInfo[] = [
  {
    name: "THINK",
    description: "Assess situation, determine urgency, identify top needs",
  },
  {
    name: "PLAN",
    description: "Generate action plan with steps, deadlines, contingencies",
  },
  {
    name: "ACT",
    description: "Execute action, emit message, update state",
  },
  {
    name: "REFLECT",
    description: "Store in memory, update relationships, adjust stress",
  },
];

/* ------------------------------------------------------------------ */
/*  Detail data for each stage                                         */
/* ------------------------------------------------------------------ */

const THINK_DETAIL = {
  situation: "Flood water rising to 2nd floor. 3 people stranded on roof.",
  urgency: "HIGH",
  topNeeds: ["Evacuation route", "Medical supplies", "Communication"],
};

const PLAN_DETAIL = {
  goal: "Evacuate to high ground",
  steps: [
    "1. Check bridge status",
    "2. Gather supplies",
    "3. Lead group north",
  ],
  deadline: "Step 15",
  progress: 0,
};

const ACT_DETAIL = {
  action: "MOVE to Bridge",
  message: "Everyone follow me \u2014 the bridge is still passable!",
  stateChange: {
    location: { from: "Rooftop", to: "Bridge" },
    stress: { from: 6, to: 5 },
  },
};

const REFLECT_DETAIL = {
  memoryStored: "Led successful evacuation via bridge route",
  emotionalValence: "+0.7 (positive)",
  relationshipUpdate: "Trust with Maria: 5 \u2192 7 (she helped carry supplies)",
  stressAdjustment: "5 \u2192 4",
};

/* ------------------------------------------------------------------ */
/*  Shared inline styles                                               */
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

const keyStyle: React.CSSProperties = {
  color: "#22d3ee",
  fontWeight: 600,
};

const valStyle: React.CSSProperties = {
  color: "#e4e4e7",
};

const AUTO_PLAY_INTERVAL = 1500;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function CognitiveEngineWidget() {
  const [currentStage, setCurrentStage] = useState<number>(-1); // -1 = not started
  const [isPlaying, setIsPlaying] = useState(false);
  const [detailOpen, setDetailOpen] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* ---------- helpers ---------- */

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stageClassName = (index: number) => {
    if (index === currentStage) return "pipeline-stage active";
    if (currentStage > index) return "pipeline-stage completed";
    return "pipeline-stage";
  };

  /* ---------- auto-play ---------- */

  useEffect(() => {
    if (!isPlaying) {
      clearTimer();
      return;
    }

    // If we haven't started yet, begin at stage 0
    if (currentStage < 0) {
      setCurrentStage(0);
      return;
    }

    // If we're at the last stage, stop playing after the interval
    if (currentStage >= STAGES.length - 1) {
      timerRef.current = setTimeout(() => {
        setIsPlaying(false);
      }, AUTO_PLAY_INTERVAL);
      return () => clearTimer();
    }

    timerRef.current = setTimeout(() => {
      setCurrentStage((s) => s + 1);
    }, AUTO_PLAY_INTERVAL);

    return () => clearTimer();
  }, [isPlaying, currentStage, clearTimer]);

  /* ---------- button handlers ---------- */

  const handleStepThrough = () => {
    setIsPlaying(false);
    clearTimer();
    if (currentStage < STAGES.length - 1) {
      setCurrentStage((s) => s + 1);
    } else {
      setCurrentStage(0);
    }
  };

  const handleAutoPlay = () => {
    if (isPlaying) {
      setIsPlaying(false);
      return;
    }
    if (currentStage >= STAGES.length - 1) {
      setCurrentStage(-1);
    }
    setIsPlaying(true);
  };

  const handleReset = () => {
    setIsPlaying(false);
    clearTimer();
    setCurrentStage(-1);
  };

  /* ---------- detail panel content ---------- */

  const renderDetail = () => {
    if (currentStage < 0) {
      return (
        <div style={monoBlock}>
          <span style={{ color: "#a1a1aa", fontStyle: "italic" }}>
            Press <strong style={{ color: "#e4e4e7" }}>Step Through</strong> or{" "}
            <strong style={{ color: "#e4e4e7" }}>Auto Play</strong> to begin the
            cognitive cycle.
          </span>
        </div>
      );
    }

    switch (currentStage) {
      case 0:
        return (
          <div style={monoBlock} className="animate-fade-in">
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>situation: </span>
              <span style={valStyle}>&quot;{THINK_DETAIL.situation}&quot;</span>
            </div>
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>urgency: </span>
              <span
                style={{
                  background: "rgba(239,68,68,0.2)",
                  color: "#f87171",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  fontSize: "11px",
                  fontWeight: 700,
                  letterSpacing: "0.05em",
                }}
              >
                {THINK_DETAIL.urgency}
              </span>
            </div>
            <div>
              <span style={keyStyle}>topNeeds: </span>
              <span style={valStyle}>[</span>
              {THINK_DETAIL.topNeeds.map((need, i) => (
                <span key={need}>
                  <br />
                  <span style={{ paddingLeft: "16px", color: "#e4e4e7" }}>
                    &quot;{need}&quot;
                    {i < THINK_DETAIL.topNeeds.length - 1 ? "," : ""}
                  </span>
                </span>
              ))}
              <br />
              <span style={valStyle}>]</span>
            </div>
          </div>
        );
      case 1:
        return (
          <div style={monoBlock} className="animate-fade-in">
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>goal: </span>
              <span style={valStyle}>&quot;{PLAN_DETAIL.goal}&quot;</span>
            </div>
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>steps: </span>
              <span style={valStyle}>[</span>
              {PLAN_DETAIL.steps.map((step, i) => (
                <span key={step}>
                  <br />
                  <span style={{ paddingLeft: "16px", color: "#e4e4e7" }}>
                    &quot;{step}&quot;
                    {i < PLAN_DETAIL.steps.length - 1 ? "," : ""}
                  </span>
                </span>
              ))}
              <br />
              <span style={valStyle}>]</span>
            </div>
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>deadline: </span>
              <span style={valStyle}>&quot;{PLAN_DETAIL.deadline}&quot;</span>
            </div>
            <div>
              <span style={keyStyle}>progress: </span>
              <span style={valStyle}>{PLAN_DETAIL.progress}%</span>
            </div>
          </div>
        );
      case 2:
        return (
          <div style={monoBlock} className="animate-fade-in">
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>action: </span>
              <span style={valStyle}>&quot;{ACT_DETAIL.action}&quot;</span>
            </div>
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>message: </span>
              <span style={valStyle}>&quot;{ACT_DETAIL.message}&quot;</span>
            </div>
            <div>
              <span style={keyStyle}>stateChange: </span>
              <span style={valStyle}>{"{"}</span>
              <br />
              <span style={{ paddingLeft: "16px" }}>
                <span style={{ color: "#a1a1aa" }}>location: </span>
                <span style={valStyle}>
                  {ACT_DETAIL.stateChange.location.from}
                </span>
                <span style={{ color: "#22d3ee" }}> {"\u2192"} </span>
                <span style={valStyle}>
                  {ACT_DETAIL.stateChange.location.to}
                </span>
              </span>
              <br />
              <span style={{ paddingLeft: "16px" }}>
                <span style={{ color: "#a1a1aa" }}>stress: </span>
                <span style={valStyle}>
                  {ACT_DETAIL.stateChange.stress.from}
                </span>
                <span style={{ color: "#22d3ee" }}> {"\u2192"} </span>
                <span style={valStyle}>
                  {ACT_DETAIL.stateChange.stress.to}
                </span>
              </span>
              <br />
              <span style={valStyle}>{"}"}</span>
            </div>
          </div>
        );
      case 3:
        return (
          <div style={monoBlock} className="animate-fade-in">
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>memoryStored: </span>
              <span style={valStyle}>
                &quot;{REFLECT_DETAIL.memoryStored}&quot;
              </span>
            </div>
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>emotionalValence: </span>
              <span style={{ color: "#4ade80", fontWeight: 600 }}>
                {REFLECT_DETAIL.emotionalValence}
              </span>
            </div>
            <div style={{ marginBottom: "8px" }}>
              <span style={keyStyle}>relationshipUpdate: </span>
              <span style={valStyle}>
                &quot;{REFLECT_DETAIL.relationshipUpdate}&quot;
              </span>
            </div>
            <div>
              <span style={keyStyle}>stressAdjustment: </span>
              <span style={valStyle}>
                {REFLECT_DETAIL.stressAdjustment}
              </span>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  /* ---------- render ---------- */

  return (
    <div className="widget-container s-cognitive" suppressHydrationWarning>
      <div className="widget-label">
        Interactive &middot; Cognitive Engine
      </div>

      {/* ---- Controls ---- */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "20px",
          flexWrap: "wrap",
        }}
      >
        <button className="btn-mono" onClick={handleStepThrough}>
          Step Through
        </button>
        <button
          className={`btn-mono${isPlaying ? " active" : ""}`}
          onClick={handleAutoPlay}
        >
          {isPlaying ? "Pause" : "Auto Play"}
        </button>
        <button className="btn-mono" onClick={handleReset}>
          Reset
        </button>
      </div>

      {/* ---- Pipeline ---- */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0",
          overflowX: "auto",
          paddingBottom: "4px",
        }}
      >
        {STAGES.map((stage, i) => (
          <React.Fragment key={stage.name}>
            {/* Stage box */}
            <div
              className={stageClassName(i)}
              style={{
                flex: "1 1 0%",
                minWidth: "120px",
                cursor: "pointer",
              }}
              onClick={() => {
                setIsPlaying(false);
                clearTimer();
                setCurrentStage(i);
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color:
                    i === currentStage
                      ? "#22d3ee"
                      : i < currentStage
                        ? "#4ade80"
                        : "#e4e4e7",
                  letterSpacing: "0.05em",
                  marginBottom: "4px",
                  fontFamily: "var(--font-mono), ui-monospace, monospace",
                }}
              >
                {stage.name}
              </div>
              <div
                style={{
                  fontSize: "11px",
                  color: "#a1a1aa",
                  lineHeight: 1.4,
                }}
              >
                {stage.description}
              </div>
            </div>

            {/* Arrow between stages */}
            {i < STAGES.length - 1 && (
              <div
                style={{
                  flexShrink: 0,
                  padding: "0 6px",
                  fontSize: "18px",
                  color:
                    i < currentStage
                      ? "#4ade80"
                      : i === currentStage
                        ? "#22d3ee"
                        : "rgba(255,255,255,0.15)",
                  fontWeight: 700,
                  transition: "color 0.3s",
                  userSelect: "none",
                }}
              >
                {"\u2192"}
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* ---- Detail Panel ---- */}
      <div style={{ marginTop: "20px" }}>
        <button
          className="btn-mono"
          style={{ marginBottom: "12px", fontSize: "12px" }}
          onClick={() => setDetailOpen((o) => !o)}
        >
          {detailOpen ? "\u25BC" : "\u25B6"} Stage Detail
          {currentStage >= 0 ? ` \u2014 ${STAGES[currentStage].name}` : ""}
        </button>

        {detailOpen && renderDetail()}
      </div>
    </div>
  );
}
