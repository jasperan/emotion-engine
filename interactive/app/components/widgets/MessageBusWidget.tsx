"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type MessageMode = "Direct" | "Broadcast" | "Room";

interface AgentDef {
  id: string;
  name: string;
  room: string;
}

interface LogEntry {
  id: number;
  mode: MessageMode;
  sender: string;
  target: string;
  text: string;
}

interface AnimatingEdge {
  id: number;
  fromId: string;
  toId: string;
  progress: number;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const ACCENT = "#fb923c";

const AGENTS: AgentDef[] = [
  { id: "chen", name: "Dr. Chen", room: "Rooftop" },
  { id: "marcus", name: "Marcus", room: "Rooftop" },
  { id: "sofia", name: "Sofia", room: "Rooftop" },
  { id: "amir", name: "Amir", room: "Bridge" },
  { id: "yuki", name: "Yuki", room: "Bridge" },
  { id: "leo", name: "Leo", room: "Bridge" },
];

const ROOMS = ["Rooftop", "Bridge"] as const;

const EXAMPLE_MESSAGES: LogEntry[] = [
  { id: -4, mode: "Direct", sender: "Dr. Chen", target: "Marcus", text: "Help me carry these supplies!" },
  { id: -3, mode: "Broadcast", sender: "Sofia", target: "All", text: "The water is rising fast!" },
  { id: -2, mode: "Room", sender: "Dr. Chen", target: "Rooftop", text: "Everyone to the stairwell!" },
  { id: -1, mode: "Direct", sender: "Amir", target: "Yuki", text: "Hand me the rope." },
];

const FLAVOR_DIRECT: Record<string, string> = {
  chen: "Can you help me with this?",
  marcus: "Stay close, I have an idea.",
  sofia: "Watch out for that ledge!",
  amir: "I found a way across.",
  yuki: "Take this, you need it more.",
  leo: "Follow me, I know the path.",
};

const FLAVOR_BROADCAST: Record<string, string> = {
  chen: "Everyone, stay calm and listen!",
  marcus: "We need to move NOW!",
  sofia: "The water is rising fast!",
  amir: "I see rescue boats approaching!",
  yuki: "Gather at the center, quickly!",
  leo: "Nobody panic, help is coming!",
};

const FLAVOR_ROOM: Record<string, string> = {
  chen: "Everyone to the stairwell!",
  marcus: "Check the barricade on our side!",
  sofia: "Is anyone here injured?",
  amir: "This bridge won't hold much longer!",
  yuki: "Secure the railing on the east side!",
  leo: "Hold formation, stay together!",
};

/* ------------------------------------------------------------------ */
/*  SVG Layout Positions                                               */
/* ------------------------------------------------------------------ */

const SVG_W = 600;
const SVG_H = 280;

const ROOM_PAD = 16;
const ROOM_W = 230;
const ROOM_H = 200;
const ROOM_Y = 40;
const ROOM_LEFT_X = 20;
const ROOM_RIGHT_X = SVG_W - ROOM_W - 20;

/*  Agent circle positions inside each room (3 per room).              */
function agentPos(agent: AgentDef): { cx: number; cy: number } {
  const isLeft = agent.room === "Rooftop";
  const roomX = isLeft ? ROOM_LEFT_X : ROOM_RIGHT_X;
  const roomAgents = AGENTS.filter((a) => a.room === agent.room);
  const idx = roomAgents.findIndex((a) => a.id === agent.id);

  /*  Row layout: top row has 2, bottom row has 1 centered.            */
  const positions = [
    { cx: roomX + ROOM_W * 0.3, cy: ROOM_Y + ROOM_H * 0.32 },
    { cx: roomX + ROOM_W * 0.7, cy: ROOM_Y + ROOM_H * 0.32 },
    { cx: roomX + ROOM_W * 0.5, cy: ROOM_Y + ROOM_H * 0.72 },
  ];
  return positions[idx] ?? positions[0];
}

const AGENT_R = 24;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function MessageBusWidget() {
  const [mode, setMode] = useState<MessageMode>("Direct");
  const [selectedSender, setSelectedSender] = useState<string | null>(null);
  const [messages, setMessages] = useState<LogEntry[]>([...EXAMPLE_MESSAGES]);
  const [animatingEdges, setAnimatingEdges] = useState<AnimatingEdge[]>([]);
  const [stats, setStats] = useState({ Direct: 2, Broadcast: 1, Room: 1 });
  const nextId = useRef(1);
  const logRef = useRef<HTMLDivElement>(null);

  /* Auto-scroll the message log */
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  /* ---- animation tick via requestAnimationFrame ---- */
  const animRef = useRef<number | null>(null);
  const edgesRef = useRef<AnimatingEdge[]>([]);
  edgesRef.current = animatingEdges;

  const startAnimation = useCallback((edges: AnimatingEdge[]) => {
    setAnimatingEdges(edges);
    const start = performance.now();
    const DURATION = 500; // ms

    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(elapsed / DURATION, 1);
      const updated = edges.map((e) => ({ ...e, progress: t }));
      setAnimatingEdges(updated);
      if (t < 1) {
        animRef.current = requestAnimationFrame(tick);
      } else {
        setAnimatingEdges([]);
        animRef.current = null;
      }
    };
    if (animRef.current) cancelAnimationFrame(animRef.current);
    animRef.current = requestAnimationFrame(tick);
  }, []);

  /* ---- sending logic ---- */
  const sendMessage = useCallback(
    (senderId: string, recipientIds: string[]) => {
      const sender = AGENTS.find((a) => a.id === senderId)!;
      const edges: AnimatingEdge[] = recipientIds.map((rid) => ({
        id: nextId.current++,
        fromId: senderId,
        toId: rid,
        progress: 0,
      }));

      startAnimation(edges);

      let target: string;
      let text: string;
      if (mode === "Direct") {
        const recipient = AGENTS.find((a) => a.id === recipientIds[0])!;
        target = recipient.name;
        text = FLAVOR_DIRECT[senderId] ?? "Message sent.";
      } else if (mode === "Broadcast") {
        target = "All";
        text = FLAVOR_BROADCAST[senderId] ?? "Attention everyone!";
      } else {
        target = sender.room;
        text = FLAVOR_ROOM[senderId] ?? "Room message sent.";
      }

      const entry: LogEntry = {
        id: nextId.current++,
        mode,
        sender: sender.name,
        target,
        text,
      };
      setMessages((prev) => [...prev.slice(-7), entry]);
      setStats((prev) => ({ ...prev, [mode]: prev[mode] + 1 }));
      setSelectedSender(null);
    },
    [mode, startAnimation],
  );

  /* ---- click handler on an agent circle ---- */
  const handleAgentClick = useCallback(
    (agentId: string) => {
      if (animatingEdges.length > 0) return; // busy

      if (!selectedSender) {
        /* first click: pick sender */
        setSelectedSender(agentId);

        /* For broadcast and room, auto-send immediately */
        if (mode === "Broadcast") {
          const targets = AGENTS.filter((a) => a.id !== agentId).map((a) => a.id);
          /* use setTimeout so the sender highlight renders first */
          setTimeout(() => {
            const sender = AGENTS.find((a) => a.id === agentId)!;
            const edges: AnimatingEdge[] = targets.map((rid) => ({
              id: nextId.current++,
              fromId: agentId,
              toId: rid,
              progress: 0,
            }));
            startAnimation(edges);

            const entry: LogEntry = {
              id: nextId.current++,
              mode: "Broadcast",
              sender: sender.name,
              target: "All",
              text: FLAVOR_BROADCAST[agentId] ?? "Attention everyone!",
            };
            setMessages((prev) => [...prev.slice(-7), entry]);
            setStats((prev) => ({ ...prev, Broadcast: prev.Broadcast + 1 }));
            setSelectedSender(null);
          }, 120);
        } else if (mode === "Room") {
          const sender = AGENTS.find((a) => a.id === agentId)!;
          const targets = AGENTS.filter(
            (a) => a.room === sender.room && a.id !== agentId,
          ).map((a) => a.id);
          setTimeout(() => {
            const edges: AnimatingEdge[] = targets.map((rid) => ({
              id: nextId.current++,
              fromId: agentId,
              toId: rid,
              progress: 0,
            }));
            startAnimation(edges);

            const entry: LogEntry = {
              id: nextId.current++,
              mode: "Room",
              sender: sender.name,
              target: sender.room,
              text: FLAVOR_ROOM[agentId] ?? "Room message sent.",
            };
            setMessages((prev) => [...prev.slice(-7), entry]);
            setStats((prev) => ({ ...prev, Room: prev.Room + 1 }));
            setSelectedSender(null);
          }, 120);
        }
      } else if (mode === "Direct") {
        /* second click: pick recipient (direct only) */
        if (agentId === selectedSender) {
          setSelectedSender(null);
          return;
        }
        sendMessage(selectedSender, [agentId]);
      }
    },
    [selectedSender, mode, animatingEdges.length, sendMessage, startAnimation],
  );

  /* ---- interpolated position along edge ---- */
  const lerpPos = (fromId: string, toId: string, t: number) => {
    const from = agentPos(AGENTS.find((a) => a.id === fromId)!);
    const to = agentPos(AGENTS.find((a) => a.id === toId)!);
    return {
      x: from.cx + (to.cx - from.cx) * t,
      y: from.cy + (to.cy - from.cy) * t,
    };
  };

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */
  return (
    <div className="widget-container s-message" suppressHydrationWarning>
      <div className="widget-label">Interactive &middot; Message Bus</div>

      {/* Mode toggle buttons */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "20px",
          flexWrap: "wrap",
        }}
      >
        {(["Direct", "Broadcast", "Room"] as MessageMode[]).map((m) => (
          <button
            key={m}
            className={`btn-mono${mode === m ? " active" : ""}`}
            onClick={() => {
              setMode(m);
              setSelectedSender(null);
            }}
          >
            {m}
          </button>
        ))}
      </div>

      {/* SVG Visualization */}
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        style={{
          width: "100%",
          maxWidth: `${SVG_W}px`,
          margin: "0 auto",
          display: "block",
          overflow: "visible",
        }}
      >
        {/* Room boxes */}
        {ROOMS.map((room) => {
          const isLeft = room === "Rooftop";
          const rx = isLeft ? ROOM_LEFT_X : ROOM_RIGHT_X;
          return (
            <g key={room}>
              <rect
                x={rx}
                y={ROOM_Y}
                width={ROOM_W}
                height={ROOM_H}
                rx={12}
                fill="rgba(255,255,255,0.03)"
                stroke="rgba(255,255,255,0.1)"
                strokeWidth={1}
              />
              <text
                x={rx + ROOM_W / 2}
                y={ROOM_Y + ROOM_PAD + 4}
                textAnchor="middle"
                fill="#a1a1aa"
                fontSize={11}
                fontWeight={600}
              >
                {room}
              </text>
            </g>
          );
        })}

        {/* Center "Message Bus" label */}
        <text
          x={SVG_W / 2}
          y={ROOM_Y + ROOM_H / 2 - 8}
          textAnchor="middle"
          fill={ACCENT}
          fontSize={12}
          fontWeight={700}
          letterSpacing="0.06em"
        >
          MESSAGE
        </text>
        <text
          x={SVG_W / 2}
          y={ROOM_Y + ROOM_H / 2 + 8}
          textAnchor="middle"
          fill={ACCENT}
          fontSize={12}
          fontWeight={700}
          letterSpacing="0.06em"
        >
          BUS
        </text>
        {/* Decorative lines from bus to rooms */}
        <line
          x1={ROOM_LEFT_X + ROOM_W}
          y1={ROOM_Y + ROOM_H / 2}
          x2={SVG_W / 2 - 30}
          y2={ROOM_Y + ROOM_H / 2}
          stroke="rgba(251,146,60,0.25)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />
        <line
          x1={SVG_W / 2 + 30}
          y1={ROOM_Y + ROOM_H / 2}
          x2={ROOM_RIGHT_X}
          y2={ROOM_Y + ROOM_H / 2}
          stroke="rgba(251,146,60,0.25)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />

        {/* Animated edges (lines) */}
        {animatingEdges.map((edge) => {
          const from = agentPos(AGENTS.find((a) => a.id === edge.fromId)!);
          const to = agentPos(AGENTS.find((a) => a.id === edge.toId)!);
          return (
            <line
              key={`line-${edge.id}`}
              x1={from.cx}
              y1={from.cy}
              x2={to.cx}
              y2={to.cy}
              stroke={ACCENT}
              strokeWidth={1.5}
              strokeOpacity={0.4}
            />
          );
        })}

        {/* Animated dots traveling along edges */}
        {animatingEdges.map((edge) => {
          const pos = lerpPos(edge.fromId, edge.toId, edge.progress);
          return (
            <circle
              key={`dot-${edge.id}`}
              cx={pos.x}
              cy={pos.y}
              r={5}
              fill={ACCENT}
              opacity={1 - edge.progress * 0.3}
            >
              <animate
                attributeName="r"
                values="4;6;4"
                dur="0.5s"
                repeatCount="indefinite"
              />
            </circle>
          );
        })}

        {/* Agent circles */}
        {AGENTS.map((agent) => {
          const { cx, cy } = agentPos(agent);
          const isSender = selectedSender === agent.id;
          const isAnimSender = animatingEdges.some(
            (e) => e.fromId === agent.id,
          );
          const isAnimTarget = animatingEdges.some(
            (e) => e.toId === agent.id && e.progress > 0.8,
          );

          return (
            <g
              key={agent.id}
              onClick={() => handleAgentClick(agent.id)}
              style={{ cursor: "pointer" }}
            >
              {/* Selection ring */}
              {isSender && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={AGENT_R + 5}
                  fill="none"
                  stroke={ACCENT}
                  strokeWidth={2}
                  strokeDasharray="4 3"
                >
                  <animateTransform
                    attributeName="transform"
                    type="rotate"
                    from={`0 ${cx} ${cy}`}
                    to={`360 ${cx} ${cy}`}
                    dur="4s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}
              {/* Glow on receive */}
              {isAnimTarget && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={AGENT_R + 8}
                  fill="none"
                  stroke={ACCENT}
                  strokeWidth={1.5}
                  strokeOpacity={0.5}
                />
              )}
              {/* Main circle */}
              <circle
                cx={cx}
                cy={cy}
                r={AGENT_R}
                fill={
                  isSender || isAnimSender
                    ? `${ACCENT}33`
                    : "rgba(255,255,255,0.06)"
                }
                stroke={
                  isSender || isAnimSender
                    ? ACCENT
                    : "rgba(255,255,255,0.15)"
                }
                strokeWidth={isSender ? 2.5 : 1.5}
              />
              {/* Initials */}
              <text
                x={cx}
                y={cy + 1}
                textAnchor="middle"
                dominantBaseline="central"
                fill={isSender || isAnimSender ? ACCENT : "#a1a1aa"}
                fontSize={11}
                fontWeight={700}
              >
                {agent.name
                  .split(" ")
                  .map((w) => w[0])
                  .join("")}
              </text>
              {/* Name label */}
              <text
                x={cx}
                y={cy + AGENT_R + 14}
                textAnchor="middle"
                fill="#71717a"
                fontSize={10}
              >
                {agent.name}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Instruction hint */}
      <p
        style={{
          textAlign: "center",
          fontSize: "11px",
          color: "#71717a",
          margin: "12px 0 0",
          minHeight: "16px",
        }}
      >
        {!selectedSender && mode === "Direct" && "Click a sender agent, then click a recipient."}
        {!selectedSender && mode === "Broadcast" && "Click a sender to broadcast to all agents."}
        {!selectedSender && mode === "Room" && "Click a sender to message their room."}
        {selectedSender && mode === "Direct" && (
          <>
            <span style={{ color: ACCENT, fontWeight: 600 }}>
              {AGENTS.find((a) => a.id === selectedSender)?.name}
            </span>
            {" selected \u2014 click a recipient."}
          </>
        )}
      </p>

      {/* Stats */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "20px",
          margin: "16px 0 12px",
          fontSize: "12px",
          color: "#a1a1aa",
        }}
      >
        {(["Direct", "Broadcast", "Room"] as MessageMode[]).map((m) => (
          <span key={m}>
            {m}:{" "}
            <span
              style={{
                color: ACCENT,
                fontWeight: 700,
                fontVariantNumeric: "tabular-nums",
              }}
              suppressHydrationWarning
            >
              {stats[m]}
            </span>
          </span>
        ))}
      </div>

      {/* Message Log */}
      <div
        style={{
          fontSize: "11px",
          fontWeight: 600,
          color: ACCENT,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "6px",
        }}
      >
        Message Log
      </div>
      <div
        ref={logRef}
        style={{
          maxHeight: "160px",
          overflowY: "auto",
          background: "#12131a",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: "8px",
          padding: "8px 10px",
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        }}
      >
        {messages.slice(-8).map((entry) => {
          const tag =
            entry.mode === "Room"
              ? `[Room:${entry.target}]`
              : `[${entry.mode}]`;
          const arrow =
            entry.mode === "Direct"
              ? `${entry.sender} \u2192 ${entry.target}`
              : entry.mode === "Broadcast"
                ? `${entry.sender} \u2192 All`
                : `${entry.sender} \u2192 ${entry.target}`;

          return (
            <div
              key={entry.id}
              style={{
                fontSize: "12px",
                color: "#a1a1aa",
                lineHeight: 1.4,
                fontFamily: "monospace",
              }}
            >
              <span style={{ color: ACCENT, fontWeight: 600 }}>{tag}</span>{" "}
              <span style={{ color: "#d4d4d8" }}>{arrow}:</span>{" "}
              <span style={{ color: "#71717a", fontStyle: "italic" }}>
                {entry.text}
              </span>
            </div>
          );
        })}
      </div>

      {/* Tip */}
      <p
        style={{
          textAlign: "center",
          fontSize: "11px",
          color: "#71717a",
          marginTop: "10px",
          marginBottom: 0,
        }}
      >
        Switch modes to see how Direct, Broadcast, and Room-Scoped routing
        differ.
      </p>
    </div>
  );
}
