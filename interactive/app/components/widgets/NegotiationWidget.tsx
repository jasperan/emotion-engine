"use client";

import React, { useState } from "react";

const AGENTS = ["Dr. Chen", "Marcus", "Sofia", "Amir", "Yuki", "Leo"];

type ProposalStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "COUNTERED";

interface Proposal {
  id: number;
  from: string;
  to: string;
  terms: string;
  step: number;
  status: ProposalStatus;
  parentId?: number;
}

const STATUS_COLORS: Record<ProposalStatus, string> = {
  PENDING: "#facc15",
  ACCEPTED: "#4ade80",
  REJECTED: "#f43f5e",
  COUNTERED: "#fb923c",
};

const STATUS_ICONS: Record<ProposalStatus, string> = {
  PENDING: "\u25CB",
  ACCEPTED: "\u2713",
  REJECTED: "\u2717",
  COUNTERED: "\u21C4",
};

const INITIAL_PROPOSALS: Proposal[] = [
  {
    id: 1,
    from: "Dr. Chen",
    to: "Marcus",
    terms: "Share medical supplies in exchange for help building a raft",
    step: 3,
    status: "PENDING",
  },
];

export default function NegotiationWidget() {
  const [proposals, setProposals] = useState<Proposal[]>(INITIAL_PROPOSALS);
  const [nextStep, setNextStep] = useState(4);
  const [showForm, setShowForm] = useState(false);
  const [nextId, setNextId] = useState(2);

  const [formFrom, setFormFrom] = useState(AGENTS[0]);
  const [formTo, setFormTo] = useState(AGENTS[1]);
  const [formTerms, setFormTerms] = useState("Share [item] for [item]");

  const updateStatus = (id: number, newStatus: ProposalStatus) => {
    setProposals((prev) =>
      prev.map((p) => (p.id === id ? { ...p, status: newStatus } : p))
    );
  };

  const handleAccept = (id: number) => updateStatus(id, "ACCEPTED");
  const handleReject = (id: number) => updateStatus(id, "REJECTED");

  const handleCounter = (proposal: Proposal) => {
    const counterProposal: Proposal = {
      id: nextId,
      from: proposal.to,
      to: proposal.from,
      terms: `Counter: ${proposal.terms}`,
      step: nextStep,
      status: "PENDING" as ProposalStatus,
      parentId: proposal.id,
    };
    setProposals((prev) =>
      prev.map((p): Proposal => (p.id === proposal.id ? { ...p, status: "COUNTERED" as ProposalStatus } : p))
        .concat(counterProposal)
    );
    setNextId((n) => n + 1);
    setNextStep((n) => n + 1);
  };

  const handleNewProposal = () => {
    const newProposal: Proposal = {
      id: nextId,
      from: formFrom,
      to: formTo,
      terms: formTerms,
      step: nextStep,
      status: "PENDING",
    };
    setProposals((prev) => [...prev, newProposal]);
    setNextId((n) => n + 1);
    setNextStep((n) => n + 1);
    setShowForm(false);
    setFormTerms("Share [item] for [item]");
  };

  const counts = {
    total: proposals.length,
    accepted: proposals.filter((p) => p.status === "ACCEPTED").length,
    rejected: proposals.filter((p) => p.status === "REJECTED").length,
    pending: proposals.filter((p) => p.status === "PENDING").length,
  };

  const renderProposalCard = (proposal: Proposal) => {
    const isChild = proposal.parentId != null;
    const statusColor = STATUS_COLORS[proposal.status];
    const statusIcon = STATUS_ICONS[proposal.status];
    const expiresIn = Math.max(1, 5 - (nextStep - proposal.step));

    return (
      <div
        key={proposal.id}
        className="animate-slide-in"
        style={{
          marginLeft: isChild ? "2rem" : 0,
          display: "flex",
          gap: "12px",
          alignItems: "flex-start",
          marginBottom: "16px",
          position: "relative",
        }}
      >
        {/* Timeline dot */}
        <div
          style={{
            width: "12px",
            height: "12px",
            borderRadius: "50%",
            backgroundColor: statusColor,
            flexShrink: 0,
            marginTop: "14px",
            position: "relative",
            zIndex: 1,
            boxShadow: `0 0 6px ${statusColor}40`,
          }}
        />

        {/* Proposal card */}
        <div
          style={{
            flex: 1,
            padding: "12px 14px",
            borderRadius: "8px",
            background: "#12131a",
            border: `1px solid ${statusColor}30`,
          }}
        >
          {/* Header row */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "8px",
              flexWrap: "wrap",
              gap: "6px",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                color: "#a1a1aa",
              }}
            >
              <span style={{ fontWeight: 600, color: "#fff" }}>
                Step {proposal.step}
              </span>
              {" \u2014 "}
              <span style={{ color: "#facc15", fontWeight: 500 }}>
                {proposal.from}
              </span>
              {" \u2192 "}
              <span style={{ color: "#facc15", fontWeight: 500 }}>
                {proposal.to}
              </span>
            </span>

            {/* Status badge */}
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "11px",
                fontWeight: 700,
                color: "#000",
                backgroundColor: statusColor,
                padding: "2px 8px",
                borderRadius: "9999px",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
              }}
            >
              {statusIcon} {proposal.status}
            </span>
          </div>

          {/* Terms */}
          <p
            style={{
              fontSize: "13px",
              color: "#d4d4d8",
              lineHeight: 1.5,
              margin: "0 0 8px 0",
              fontStyle: "italic",
            }}
          >
            &ldquo;{proposal.terms}&rdquo;
          </p>

          {/* Expiry + Actions */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            {proposal.status === "PENDING" && (
              <span
                style={{
                  fontSize: "11px",
                  color: "#71717a",
                }}
              >
                Expires in {expiresIn} step{expiresIn !== 1 ? "s" : ""}
              </span>
            )}
            {proposal.status !== "PENDING" && <span />}

            {proposal.status === "PENDING" && (
              <div style={{ display: "flex", gap: "6px" }}>
                <button
                  className="btn-mono"
                  style={{
                    fontSize: "11px",
                    padding: "3px 10px",
                    color: "#4ade80",
                    borderColor: "#4ade8040",
                  }}
                  onClick={() => handleAccept(proposal.id)}
                >
                  Accept
                </button>
                <button
                  className="btn-mono"
                  style={{
                    fontSize: "11px",
                    padding: "3px 10px",
                    color: "#f43f5e",
                    borderColor: "#f43f5e40",
                  }}
                  onClick={() => handleReject(proposal.id)}
                >
                  Reject
                </button>
                <button
                  className="btn-mono"
                  style={{
                    fontSize: "11px",
                    padding: "3px 10px",
                    color: "#fb923c",
                    borderColor: "#fb923c40",
                  }}
                  onClick={() => handleCounter(proposal)}
                >
                  Counter
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="widget-container s-negotiation" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Negotiation Theater</div>

      {/* New Proposal button */}
      <div style={{ marginBottom: "16px" }}>
        <button
          className="btn-mono"
          onClick={() => setShowForm((s) => !s)}
          style={{ color: "#facc15", borderColor: "#facc1540" }}
        >
          {showForm ? "Cancel" : "+ New Proposal"}
        </button>
      </div>

      {/* New Proposal form */}
      {showForm && (
        <div
          className="animate-slide-in"
          style={{
            padding: "14px",
            borderRadius: "8px",
            background: "#12131a",
            border: "1px solid rgba(255,255,255,0.08)",
            marginBottom: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "#facc15",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "2px",
            }}
          >
            New Proposal
          </div>

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            {/* From */}
            <div style={{ flex: 1, minWidth: "120px" }}>
              <label
                style={{
                  fontSize: "11px",
                  color: "#71717a",
                  display: "block",
                  marginBottom: "4px",
                }}
              >
                From
              </label>
              <select
                value={formFrom}
                onChange={(e) => setFormFrom(e.target.value)}
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "#0a0a0f",
                  color: "#fff",
                  outline: "none",
                }}
              >
                {AGENTS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>

            {/* To */}
            <div style={{ flex: 1, minWidth: "120px" }}>
              <label
                style={{
                  fontSize: "11px",
                  color: "#71717a",
                  display: "block",
                  marginBottom: "4px",
                }}
              >
                To
              </label>
              <select
                value={formTo}
                onChange={(e) => setFormTo(e.target.value)}
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "#0a0a0f",
                  color: "#fff",
                  outline: "none",
                }}
              >
                {AGENTS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Terms */}
          <div>
            <label
              style={{
                fontSize: "11px",
                color: "#71717a",
                display: "block",
                marginBottom: "4px",
              }}
            >
              Terms
            </label>
            <input
              type="text"
              value={formTerms}
              onChange={(e) => setFormTerms(e.target.value)}
              style={{
                width: "100%",
                padding: "6px 8px",
                fontSize: "13px",
                borderRadius: "6px",
                border: "1px solid rgba(255,255,255,0.12)",
                background: "#0a0a0f",
                color: "#fff",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <button
            className="btn-mono"
            onClick={handleNewProposal}
            style={{
              alignSelf: "flex-start",
              color: "#facc15",
              borderColor: "#facc1540",
            }}
          >
            Submit Proposal
          </button>
        </div>
      )}

      {/* Timeline */}
      <div
        style={{
          position: "relative",
          paddingLeft: "6px",
        }}
      >
        {/* Vertical timeline line */}
        <div
          style={{
            position: "absolute",
            left: "11px",
            top: 0,
            bottom: 0,
            width: "2px",
            background: "rgba(255,255,255,0.1)",
          }}
        />

        {proposals.map((p) => renderProposalCard(p))}
      </div>

      {/* Stats bar */}
      <div
        style={{
          marginTop: "16px",
          padding: "10px 14px",
          borderRadius: "8px",
          background: "#12131a",
          border: "1px solid rgba(255,255,255,0.08)",
          fontSize: "12px",
          color: "#71717a",
          display: "flex",
          flexWrap: "wrap",
          gap: "6px",
        }}
      >
        <span>
          Total proposals:{" "}
          <span style={{ color: "#fff", fontWeight: 600 }}>{counts.total}</span>
        </span>
        <span style={{ opacity: 0.3 }}>|</span>
        <span>
          Accepted:{" "}
          <span style={{ color: "#4ade80", fontWeight: 600 }}>
            {counts.accepted}
          </span>
        </span>
        <span style={{ opacity: 0.3 }}>|</span>
        <span>
          Rejected:{" "}
          <span style={{ color: "#f43f5e", fontWeight: 600 }}>
            {counts.rejected}
          </span>
        </span>
        <span style={{ opacity: 0.3 }}>|</span>
        <span>
          Pending:{" "}
          <span style={{ color: "#facc15", fontWeight: 600 }}>
            {counts.pending}
          </span>
        </span>
      </div>
    </div>
  );
}
