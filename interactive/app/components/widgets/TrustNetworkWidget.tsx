"use client";

import React, { useState } from "react";

const AGENTS = ["Dr. Chen", "Marcus", "Sofia", "Amir", "Yuki", "Leo"];

// Fixed hexagonal layout positions (no Math.random)
const NODE_POSITIONS: [number, number][] = [
  [250, 55],   // Dr. Chen (top center)
  [415, 140],  // Marcus (top right)
  [415, 280],  // Sofia (bottom right)
  [250, 355],  // Amir (bottom center)
  [85, 280],   // Yuki (bottom left)
  [85, 140],   // Leo (top left)
];

function makeDefaultMatrix(): number[][] {
  return Array.from({ length: 6 }, () => Array(6).fill(5));
}

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

function getEdgeColor(trust: number): string {
  if (trust <= 3) return "#f43f5e";
  if (trust >= 7) return "#4ade80";
  return "rgba(255,255,255,0.15)";
}

function getEdgeOpacity(trust: number): number {
  if (trust <= 3) return 0.8;
  if (trust >= 7) return 0.4 + (trust - 7) * 0.2; // 0.4 at 7, 1.0 at 10
  return 0.3;
}

function getEdgeLabel(trust: number): string | null {
  if (trust <= 3) return "Conflict";
  return null;
}

interface Preset {
  label: string;
  apply: (matrix: number[][]) => number[][];
}

const PRESETS: Preset[] = [
  {
    label: "Alliance",
    apply: (matrix) => {
      const m = matrix.map((row) => [...row]);
      m[0][1] = 9; m[1][0] = 9; // Dr. Chen <-> Marcus
      m[0][2] = 8; m[2][0] = 8; // Dr. Chen <-> Sofia
      m[1][2] = 9; m[2][1] = 9; // Marcus <-> Sofia
      return m;
    },
  },
  {
    label: "Conflict",
    apply: (matrix) => {
      const m = matrix.map((row) => [...row]);
      m[3][5] = 2; m[5][3] = 2; // Amir <-> Leo
      m[4][5] = 1; m[5][4] = 1; // Yuki <-> Leo
      return m;
    },
  },
  {
    label: "Fresh Start",
    apply: () => makeDefaultMatrix(),
  },
];

// Generate all unique pairs (i < j)
function allPairs(): [number, number][] {
  const pairs: [number, number][] = [];
  for (let i = 0; i < 6; i++) {
    for (let j = i + 1; j < 6; j++) {
      pairs.push([i, j]);
    }
  }
  return pairs;
}

export default function TrustNetworkWidget() {
  const [matrix, setMatrix] = useState<number[][]>(makeDefaultMatrix);
  const [selected, setSelected] = useState<number[]>([]);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  const pairs = allPairs();

  const handleNodeClick = (idx: number) => {
    setSelected((prev) => {
      if (prev.length === 0) return [idx];
      if (prev.length === 1) {
        if (prev[0] === idx) return [];
        return [prev[0], idx];
      }
      // Two already selected: start fresh
      return [idx];
    });
  };

  const handleVouch = () => {
    if (selected.length !== 2) return;
    const [a, b] = selected;
    setMatrix((prev) => {
      const m = prev.map((row) => [...row]);
      m[a][b] = clamp(m[a][b] + 2, 1, 10);
      m[b][a] = clamp(m[b][a] + 2, 1, 10);
      return m;
    });
    setActivePreset(null);
  };

  const handleBetray = () => {
    if (selected.length !== 2) return;
    const [a, b] = selected;
    setMatrix((prev) => {
      const m = prev.map((row) => [...row]);
      m[a][b] = clamp(m[a][b] - 2, 1, 10);
      m[b][a] = clamp(m[b][a] - 2, 1, 10);
      return m;
    });
    setActivePreset(null);
  };

  const applyPreset = (preset: Preset) => {
    setMatrix((prev) => preset.apply(prev));
    setActivePreset(preset.label);
    setSelected([]);
  };

  const pairTrust =
    selected.length === 2 ? matrix[selected[0]][selected[1]] : null;

  return (
    <div className="widget-container s-trust" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Trust Network</div>

      {/* Preset Buttons */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", flexWrap: "wrap" }}>
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            className={`btn-mono${activePreset === preset.label ? " active" : ""}`}
            onClick={() => applyPreset(preset)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* SVG Network Graph */}
      <svg
        viewBox="0 0 500 400"
        style={{
          width: "100%",
          maxWidth: "500px",
          background: "rgba(0,0,0,0.3)",
          borderRadius: "8px",
          border: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        {/* Edges */}
        {pairs.map(([i, j]) => {
          const trust = matrix[i][j];
          const [x1, y1] = NODE_POSITIONS[i];
          const [x2, y2] = NODE_POSITIONS[j];
          const color = getEdgeColor(trust);
          const opacity = getEdgeOpacity(trust);
          const thickness = 1 + trust / 5;
          const label = getEdgeLabel(trust);
          const isSelected =
            selected.length === 2 &&
            ((selected[0] === i && selected[1] === j) ||
              (selected[0] === j && selected[1] === i));

          return (
            <g key={`edge-${i}-${j}`}>
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={isSelected ? "#22d3ee" : color}
                strokeWidth={isSelected ? thickness + 1 : thickness}
                opacity={isSelected ? 1 : opacity}
                strokeLinecap="round"
              />
              {label && (
                <text
                  x={(x1 + x2) / 2}
                  y={(y1 + y2) / 2 - 6}
                  fill="#f43f5e"
                  fontSize="9"
                  textAnchor="middle"
                  fontWeight={600}
                  opacity={0.9}
                >
                  {label}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {AGENTS.map((name, idx) => {
          const [cx, cy] = NODE_POSITIONS[idx];
          const isSelected = selected.includes(idx);

          return (
            <g
              key={name}
              style={{ cursor: "pointer" }}
              onClick={() => handleNodeClick(idx)}
            >
              {/* Selection ring */}
              {isSelected && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={36}
                  fill="none"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  opacity={0.9}
                />
              )}
              {/* Node circle */}
              <circle cx={cx} cy={cy} r={30} fill="#4ade80" opacity={0.85} />
              {/* Initials inside node */}
              <text
                x={cx}
                y={cy + 1}
                fill="#000"
                fontSize="13"
                fontWeight={700}
                textAnchor="middle"
                dominantBaseline="central"
                style={{ pointerEvents: "none" }}
              >
                {name.split(" ").map((w) => w[0]).join("")}
              </text>
              {/* Name label below */}
              <text
                x={cx}
                y={cy + 46}
                fill="#fff"
                fontSize="11"
                textAnchor="middle"
                style={{ pointerEvents: "none" }}
              >
                {name}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Selected Pair Controls */}
      {selected.length === 2 && (
        <div
          style={{
            marginTop: "14px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          <span style={{ fontSize: "13px", color: "#a1a1aa" }}>
            {AGENTS[selected[0]]} &harr; {AGENTS[selected[1]]}:
            <span
              style={{
                fontWeight: 700,
                color: pairTrust !== null && pairTrust <= 3
                  ? "#f43f5e"
                  : pairTrust !== null && pairTrust >= 7
                    ? "#4ade80"
                    : "#fff",
                marginLeft: "6px",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              Trust {pairTrust}
            </span>
          </span>
          <button className="btn-mono" onClick={handleVouch}>
            Vouch (+2)
          </button>
          <button className="btn-mono" onClick={handleBetray}>
            Betray (-2)
          </button>
        </div>
      )}

      {selected.length === 1 && (
        <div style={{ marginTop: "14px", fontSize: "13px", color: "#a1a1aa" }}>
          Selected {AGENTS[selected[0]]} &mdash; click another node to form a pair
        </div>
      )}

      {/* Trust Matrix */}
      <div style={{ marginTop: "20px" }}>
        <h3
          style={{
            fontSize: "13px",
            fontWeight: 600,
            color: "#4ade80",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            marginBottom: "10px",
          }}
        >
          Trust Matrix
        </h3>
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              fontSize: "11px",
              fontVariantNumeric: "tabular-nums",
              width: "100%",
              maxWidth: "480px",
            }}
          >
            <thead>
              <tr>
                <th
                  style={{
                    padding: "4px 6px",
                    color: "#a1a1aa",
                    fontWeight: 500,
                    textAlign: "left",
                    borderBottom: "1px solid rgba(255,255,255,0.08)",
                  }}
                />
                {AGENTS.map((name) => (
                  <th
                    key={name}
                    style={{
                      padding: "4px 6px",
                      color: "#a1a1aa",
                      fontWeight: 500,
                      textAlign: "center",
                      borderBottom: "1px solid rgba(255,255,255,0.08)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {name.split(" ").pop()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {AGENTS.map((rowName, i) => (
                <tr key={rowName}>
                  <td
                    style={{
                      padding: "4px 6px",
                      color: "#a1a1aa",
                      fontWeight: 500,
                      whiteSpace: "nowrap",
                      borderRight: "1px solid rgba(255,255,255,0.08)",
                    }}
                  >
                    {rowName.split(" ").pop()}
                  </td>
                  {AGENTS.map((_, j) => {
                    const val = matrix[i][j];
                    const isSelf = i === j;
                    const isHighlighted =
                      selected.length === 2 &&
                      ((selected[0] === i && selected[1] === j) ||
                        (selected[0] === j && selected[1] === i));

                    let cellColor = "rgba(255,255,255,0.5)";
                    if (!isSelf) {
                      if (val <= 3) cellColor = "#f43f5e";
                      else if (val >= 7) cellColor = "#4ade80";
                      else cellColor = "rgba(255,255,255,0.5)";
                    }

                    return (
                      <td
                        key={j}
                        style={{
                          padding: "4px 6px",
                          textAlign: "center",
                          color: isSelf ? "rgba(255,255,255,0.2)" : cellColor,
                          fontWeight: isHighlighted ? 700 : 400,
                          background: isHighlighted
                            ? "rgba(34,211,238,0.15)"
                            : "transparent",
                          borderRadius: isHighlighted ? "3px" : undefined,
                        }}
                      >
                        {isSelf ? "\u2014" : val}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
