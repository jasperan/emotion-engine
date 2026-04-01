"use client";

import React, { useState } from "react";

interface TraitConfig {
  key: string;
  label: string;
  shortLabel: string;
  defaultValue: number;
}

interface Preset {
  label: string;
  values: Record<string, number>;
}

const TRAITS: TraitConfig[] = [
  { key: "O", label: "Openness", shortLabel: "O", defaultValue: 7 },
  { key: "C", label: "Conscientiousness", shortLabel: "C", defaultValue: 5 },
  { key: "E", label: "Extraversion", shortLabel: "E", defaultValue: 6 },
  { key: "A", label: "Agreeableness", shortLabel: "A", defaultValue: 8 },
  { key: "N", label: "Neuroticism", shortLabel: "N", defaultValue: 3 },
];

const PRESETS: Preset[] = [
  {
    label: "ER Doctor",
    values: { O: 6, C: 9, E: 7, A: 8, N: 2 },
  },
  {
    label: "Scared Child",
    values: { O: 8, C: 2, E: 4, A: 6, N: 9 },
  },
  {
    label: "Retired Firefighter",
    values: { O: 5, C: 8, E: 6, A: 7, N: 3 },
  },
];

function computeProbabilities(traits: Record<string, number>) {
  return [
    {
      label: "Speak",
      formula: "max(0.1, E / 10)",
      value: Math.max(0.1, traits.E / 10),
    },
    {
      label: "Help",
      formula: "max(0.1, A / 10)",
      value: Math.max(0.1, traits.A / 10),
    },
    {
      label: "Move / Explore",
      formula: "max(0.1, O / 10)",
      value: Math.max(0.1, traits.O / 10),
    },
    {
      label: "Gather / Plan",
      formula: "max(0.1, C / 10)",
      value: Math.max(0.1, traits.C / 10),
    },
    {
      label: "Wait / Observe",
      formula: "max(0.1, (10 \u2212 E) / 10)",
      value: Math.max(0.1, (10 - traits.E) / 10),
    },
  ];
}

function generatePersonaPreview(traits: Record<string, number>): string {
  const high = (key: string) => traits[key] >= 7;
  const low = (key: string) => traits[key] <= 3;

  if (high("E") && high("A"))
    return "Outgoing team leader who rallies the group";
  if (high("N") && low("A"))
    return "Anxious loner who avoids cooperation";
  if (high("O") && high("C"))
    return "Methodical explorer who plans careful routes";
  if (high("N") && high("E"))
    return "Energetic but nervous agent, oscillates between action and panic";
  if (high("C") && low("O"))
    return "Rigid planner who sticks to familiar strategies";
  if (high("O") && high("E"))
    return "Adventurous socialite who explores boldly with others";
  if (high("A") && low("N"))
    return "Calm peacemaker who stabilizes the group";
  if (high("N") && low("E"))
    return "Withdrawn worrier who freezes under pressure";
  if (high("C") && high("A"))
    return "Reliable helper who follows through on promises";
  if (low("C") && low("A"))
    return "Chaotic free agent who ignores the group";
  if (high("O") && low("N"))
    return "Confident explorer unafraid of the unknown";
  if (high("E") && low("C"))
    return "Talkative but disorganized, often starts things without finishing";

  return "Balanced agent with no dominant behavioral tendency";
}

export default function BigFiveWidget() {
  const defaults: Record<string, number> = {};
  for (const t of TRAITS) {
    defaults[t.key] = t.defaultValue;
  }

  const [traits, setTraits] = useState<Record<string, number>>(defaults);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  const updateTrait = (key: string, value: number) => {
    setTraits((prev) => ({ ...prev, [key]: value }));
    setActivePreset(null);
  };

  const applyPreset = (preset: Preset) => {
    setTraits({ ...preset.values });
    setActivePreset(preset.label);
  };

  const probabilities = computeProbabilities(traits);
  const personaText = generatePersonaPreview(traits);

  return (
    <div className="widget-container s-personality" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Big Five Personality</div>

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

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* LEFT SIDE: Trait Sliders */}
        <div>
          <h3
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: "#f97316",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "16px",
            }}
          >
            Trait Sliders
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {TRAITS.map((trait) => (
              <div key={trait.key}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "4px",
                  }}
                >
                  <label
                    style={{
                      fontSize: "13px",
                      color: "#a1a1aa",
                      fontWeight: 500,
                    }}
                  >
                    <span
                      style={{
                        display: "inline-block",
                        width: "20px",
                        color: "#f97316",
                        fontWeight: 700,
                      }}
                    >
                      {trait.shortLabel}
                    </span>
                    {trait.label}
                  </label>
                  <span
                    style={{
                      fontSize: "14px",
                      fontWeight: 700,
                      color: "#fff",
                      fontVariantNumeric: "tabular-nums",
                      minWidth: "20px",
                      textAlign: "right",
                    }}
                    suppressHydrationWarning
                  >
                    {traits[trait.key]}
                  </span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={traits[trait.key]}
                  onChange={(e) => updateTrait(trait.key, Number(e.target.value))}
                  style={{
                    width: "100%",
                    accentColor: "#f97316",
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT SIDE: Behavior Probabilities */}
        <div>
          <h3
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: "#f97316",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "16px",
            }}
          >
            Behavior Probabilities
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {probabilities.map((prob) => {
              const pct = Math.round(prob.value * 100);
              return (
                <div key={prob.label}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "baseline",
                      marginBottom: "4px",
                    }}
                  >
                    <span style={{ fontSize: "13px", color: "#a1a1aa" }}>
                      {prob.label}
                    </span>
                    <span
                      style={{
                        fontSize: "13px",
                        fontWeight: 700,
                        color: "#fff",
                        fontVariantNumeric: "tabular-nums",
                      }}
                      suppressHydrationWarning
                    >
                      {pct}%
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
                        background: "#f97316",
                        transition: "width 0.2s ease",
                      }}
                      suppressHydrationWarning
                    />
                  </div>
                  <div
                    style={{
                      fontSize: "11px",
                      color: "#a1a1aa",
                      marginTop: "2px",
                      opacity: 0.6,
                      fontFamily: "monospace",
                    }}
                  >
                    {prob.formula}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Persona Preview */}
          <div
            style={{
              marginTop: "20px",
              padding: "12px 14px",
              borderRadius: "8px",
              background: "#12131a",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            <div
              style={{
                fontSize: "11px",
                fontWeight: 600,
                color: "#f97316",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: "6px",
              }}
            >
              Persona Preview
            </div>
            <p
              style={{
                fontSize: "13px",
                color: "#a1a1aa",
                lineHeight: 1.5,
                margin: 0,
              }}
              suppressHydrationWarning
            >
              {personaText}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
