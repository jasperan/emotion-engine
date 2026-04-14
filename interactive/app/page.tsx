"use client";

import { useEffect } from "react";
import {
  BigFiveWidget,
  CognitiveEngineWidget,
  EmotionContagionWidget,
  TrustNetworkWidget,
  OpinionDynamicsWidget,
  SceneDirectorWidget,
  NegotiationWidget,
  MessageBusWidget,
  SimTickWidget,
  ScalingWidget,
} from "./components/widgets";

const sections = [
  { id: "personality", num: "01", title: "Personality", color: "text-personality" },
  { id: "cognitive", num: "02", title: "Cognitive", color: "text-cognitive" },
  { id: "emotion", num: "03", title: "Contagion", color: "text-emotion" },
  { id: "trust", num: "04", title: "Trust", color: "text-trust" },
  { id: "opinion", num: "05", title: "Opinion", color: "text-opinion" },
  { id: "scenes", num: "06", title: "Scenes", color: "text-scene" },
  { id: "negotiation", num: "07", title: "Negotiation", color: "text-negotiation" },
  { id: "messages", num: "08", title: "Messages", color: "text-message" },
  { id: "tick", num: "09", title: "Tick Loop", color: "text-tick" },
  { id: "scaling", num: "10", title: "Scaling", color: "text-scaling" },
];

export default function Home() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add("visible");
        }),
      { threshold: 0.08, rootMargin: "0px 0px -40px 0px" }
    );
    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <div className="min-h-screen">
      {/* ---- Skip Link ---- */}
      <a href="#main-content" className="skip-link">Skip to main content</a>

      {/* ---- Nav ---- */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-background/80 border-b border-border" aria-label="Section navigation">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-1.5 overflow-x-auto scrollbar-hide">
          <a href="#top" className="nav-link font-semibold text-foreground mr-3 tracking-tight">
            Emotion<span className="text-muted-foreground font-light">.sim</span>
          </a>
          {sections.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="nav-link">
              <span className={s.color}>{s.num}</span>
              <span className="hidden md:inline ml-1">{s.title}</span>
            </a>
          ))}
        </div>
      </nav>

      {/* ---- Hero ---- */}
      <header id="top" className="relative overflow-hidden py-28 md:py-40">
        <div className="hero-glow" style={{ top: "-200px", left: "10%", background: "#d4845a" }} />
        <div className="hero-glow" style={{ top: "-100px", right: "15%", background: "#5ab8c9" }} />
        <div className="max-w-6xl mx-auto px-6 relative z-10">
          <p className="font-mono text-xs text-muted-foreground tracking-[0.2em] uppercase mb-6">
            Interactive Explorer
          </p>
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-[-0.04em] leading-[1.05] mb-8" style={{ textWrap: "balance" as never }}>
            Inside the{" "}
            <span className="text-personality">Emotion Engine</span>
            <br className="hidden md:block" />{" "}
            multi-agent{" "}
            <span className="text-cognitive">simulation</span>
          </h1>
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl leading-relaxed" style={{ textWrap: "pretty" as never }}>
            Ten sections. Ten interactive widgets. Explore how{" "}
            <span className="text-personality">personality traits</span> drive{" "}
            <span className="text-cognitive">cognitive pipelines</span>, how{" "}
            <span className="text-emotion">emotions spread</span> through agent groups,
            how <span className="text-trust">trust networks</span> evolve, and how{" "}
            <span className="text-opinion">opinions shift</span> under social pressure.
          </p>
          <p className="text-sm text-muted-foreground/70 mt-6 font-mono tracking-wide">
            Every concept below is interactive. Drag sliders, click agents, trigger negotiations.
          </p>
        </div>
      </header>

      {/* ---- Table of Contents ---- */}
      <div className="max-w-6xl mx-auto px-6 mb-20">
        <div className="bg-card/60 border border-border rounded-2xl p-8 backdrop-blur-sm">
          <h2 className="text-sm font-mono text-muted-foreground/70 tracking-[0.15em] uppercase mb-6">
            Sections
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              { id: "personality", num: "01", title: "Personality", desc: "Trait-driven behavior probabilities", color: "text-personality" },
              { id: "cognitive", num: "02", title: "Cognitive", desc: "Think, plan, act, reflect pipeline", color: "text-cognitive" },
              { id: "emotion", num: "03", title: "Contagion", desc: "Stress propagation at rate 0.3", color: "text-emotion" },
              { id: "trust", num: "04", title: "Trust", desc: "Vouch and betray dynamics", color: "text-trust" },
              { id: "opinion", num: "05", title: "Opinion", desc: "Influence, trust, and bias", color: "text-opinion" },
              { id: "scenes", num: "06", title: "Scenes", desc: "Location-based parallelism", color: "text-scene" },
              { id: "negotiation", num: "07", title: "Negotiation", desc: "Proposal state machine", color: "text-negotiation" },
              { id: "messages", num: "08", title: "Messages", desc: "Multi-mode routing bus", color: "text-message" },
              { id: "tick", num: "09", title: "Tick loop", desc: "Four-phase simulation step", color: "text-tick" },
              { id: "scaling", num: "10", title: "Scaling", desc: "Full vs lightweight agents", color: "text-scaling" },
            ].map((ch) => (
              <a
                key={ch.id}
                href={`#${ch.id}`}
                className="group block p-4 rounded-xl border border-border bg-card/30 transition-all duration-200 hover:bg-white/[0.03] hover:border-white/[0.12] hover:-translate-y-0.5"
              >
                <span className={`font-mono text-xs font-medium ${ch.color}`}>{ch.num}</span>
                <h3 className="font-semibold text-sm mt-1.5 group-hover:text-foreground transition-colors">{ch.title}</h3>
                <p className="text-xs text-muted-foreground/70 mt-1 leading-relaxed">{ch.desc}</p>
              </a>
            ))}
          </div>
        </div>
      </div>

      <main id="main-content" className="max-w-6xl mx-auto px-6 prose-dark" tabIndex={-1}>
        {/* ================================================================
            01: BIG FIVE PERSONALITY TRAITS
            ================================================================ */}
        <section id="personality" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-personality">01</span>
            <div>
              <h2 className="mb-0">Big Five Personality Traits</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                The mechanical foundation of agent decision-making
              </p>
            </div>
          </div>

          <p>
            Every agent in the Emotion Engine has a <strong>persona</strong> defined by the{" "}
            <span className="text-personality">Big Five</span> personality model &mdash; the same
            framework used in psychology research. These five traits aren&apos;t just flavor text:
            they <em>mechanically drive</em> what agents do each simulation step.
          </p>
          <p>
            <strong>Openness</strong> makes agents explore. <strong>Conscientiousness</strong> makes
            them plan. <strong>Extraversion</strong> makes them speak up. <strong>Agreeableness</strong>{" "}
            makes them help others. <strong>Neuroticism</strong> makes them freeze under pressure.
            Drag the sliders below to see how trait values translate into behavior probabilities.
          </p>

          <BigFiveWidget />

          <p>
            Notice how an agent with high extraversion and agreeableness becomes a natural leader
            &mdash; they speak often and help readily. A high-neuroticism, low-agreeableness agent
            becomes an anxious loner. For lightweight agents, these trait-derived weights directly
            determine action selection via weighted random sampling. For full LLM agents, traits
            shape the <code className="bg-white/5 px-1 rounded text-sm">should_respond()</code>{" "}
            probability (whether to act at all), while the cognitive engine decides what to do.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            02: COGNITIVE ENGINE
            ================================================================ */}
        <section id="cognitive" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-cognitive">02</span>
            <div>
              <h2 className="mb-0">The Cognitive Engine</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                Think &rarr; Plan &rarr; Act &rarr; Reflect
              </p>
            </div>
          </div>

          <p>
            Each agent runs a four-stage <span className="text-cognitive">cognitive pipeline</span>{" "}
            every simulation step. First, they <strong>think</strong> &mdash; assessing the situation
            and determining urgency. Then they <strong>plan</strong> &mdash; generating an action
            plan with steps, deadlines, and contingencies. Then they <strong>act</strong> &mdash;
            executing their chosen action and emitting messages. Finally, they{" "}
            <strong>reflect</strong> &mdash; storing the experience in episodic memory and updating
            relationships.
          </p>
          <p>
            This pipeline runs for every LLM-driven agent on every tick. Smart replanning kicks in
            when a plan goes stale &mdash; if the deadline passes, progress stagnates, or the
            situation changes dramatically, the agent replans from scratch.
          </p>

          <CognitiveEngineWidget />

          <p>
            The cognitive engine is what separates the Emotion Engine from simple chatbot simulations.
            Agents don&apos;t just react &mdash; they form intentions, track progress, and learn
            from outcomes. The <strong>reflect</strong> stage is crucial: it creates{" "}
            <em>episodic memories</em> with emotional valence, so agents can recall past experiences
            when making future decisions.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            03: EMOTION CONTAGION
            ================================================================ */}
        <section id="emotion" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-emotion">03</span>
            <div>
              <h2 className="mb-0">Emotion Contagion</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                How panic spreads through a group
              </p>
            </div>
          </div>

          <p>
            In real disasters, emotions are contagious. One person panicking can trigger a cascade
            that spreads through an entire group. The Emotion Engine models this with an{" "}
            <span className="text-emotion">emotion contagion</span> system where stress propagates
            between co-located agents.
          </p>
          <p>
            The spread rate is <strong>0.3</strong>, meaning each step, an agent absorbs 30% of the
            average stress around them. A calm factor of <strong>0.5</strong> provides natural
            damping &mdash; agents gradually calm down if the source of stress is removed. The
            maximum stress delta per step is <strong>+2</strong>, preventing instant full-group panic.
          </p>

          <EmotionContagionWidget />

          <p>
            Click any agent to trigger panic, then watch it ripple outward. Notice how the calm
            factor creates a natural equilibrium &mdash; the group doesn&apos;t spiral to maximum
            stress indefinitely. In practice, this means a calm leader (low neuroticism, high
            conscientiousness) can stabilize a panicking group just by being present.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            04: TRUST NETWORK
            ================================================================ */}
        <section id="trust" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-trust">04</span>
            <div>
              <h2 className="mb-0">Trust Network</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                Bilateral vouch and betray signals
              </p>
            </div>
          </div>

          <p>
            Agents don&apos;t just interact &mdash; they build <span className="text-trust">relationships</span>.
            The trust network tracks a 1&ndash;10 trust score between every pair of agents. Trust
            increases when agents cooperate (vouch) and decreases when they compete or betray.
          </p>
          <p>
            Trust levels directly affect behavior: agents are more likely to share resources with
            high-trust partners, follow suggestions from trusted leaders, and avoid agents they
            distrust. Select two agents below and use vouch/betray to reshape the network.
          </p>

          <TrustNetworkWidget />

          <p>
            Watch how trust shapes the network topology. High-trust clusters form natural{" "}
            <strong>coalitions</strong> &mdash; groups of agents who cooperate preferentially. The
            coalition detector identifies these sub-groups automatically, tracking their stability
            over the simulation. Trust also feeds into the{" "}
            <span className="text-opinion">opinion dynamics</span> system, where high-trust agents
            have more influence over each other&apos;s beliefs.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            05: OPINION DYNAMICS
            ================================================================ */}
        <section id="opinion" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-opinion">05</span>
            <div>
              <h2 className="mb-0">Opinion Dynamics</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                How beliefs shift through social influence
              </p>
            </div>
          </div>

          <p>
            Agents hold <span className="text-opinion">opinions</span> on key topics &mdash; like
            whether to evacuate, where to go, or who to trust as leader. These opinions are numbers
            from &minus;1.0 (strongly against) to +1.0 (strongly for), and they shift when agents
            interact.
          </p>
          <p>
            The shift formula depends on four factors: the influencer&apos;s <strong>influence level</strong>,
            the <strong>trust</strong> between agents, the target&apos;s <strong>opinion bias</strong>{" "}
            (resistance to change), and the <strong>distance</strong> between their current positions.
            Highly resistant agents barely budge. Easily swayed agents converge quickly.
          </p>

          <OpinionDynamicsWidget />

          <p>
            The sentiment tracker monitors these opinion trajectories and detects{" "}
            <strong>tipping points</strong> &mdash; moments when the group suddenly converges or
            diverges on a topic. In practice, this determines when the group reaches consensus
            on evacuation plans, or when a faction splits off with a competing strategy.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            06: SCENE DIRECTOR
            ================================================================ */}
        <section id="scenes" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-scene">06</span>
            <div>
              <h2 className="mb-0">Scene Director</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                Location-based parallel processing
              </p>
            </div>
          </div>

          <p>
            With 10+ agents, processing everyone sequentially is slow. The{" "}
            <span className="text-scene">scene director</span> groups agents by location into
            independent &ldquo;scenes&rdquo; that can run in parallel. Agents on the rooftop
            form one scene. Agents at the bridge form another. Since they can&apos;t interact
            across locations, their scenes are independent.
          </p>
          <p>
            With vLLM&apos;s continuous batching, all scenes process simultaneously &mdash; turning
            a 3-scene simulation from 9 seconds to 3 seconds per step. Move agents between locations
            to see how scene groupings change.
          </p>

          <SceneDirectorWidget />

          <p>
            This is a key architectural insight: <strong>spatial locality enables parallelism</strong>.
            Agents who are physically apart can&apos;t influence each other within a single step, so
            their processing is embarrassingly parallel. The scene director also limits each scene
            to 3 turns to prevent runaway dialogues.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            07: NEGOTIATION THEATER
            ================================================================ */}
        <section id="negotiation" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-negotiation">07</span>
            <div>
              <h2 className="mb-0">Negotiation Theater</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                Proposals, counter-proposals, and resolution
              </p>
            </div>
          </div>

          <p>
            Agents don&apos;t just talk &mdash; they <span className="text-negotiation">negotiate</span>.
            The negotiation manager implements a proposal state machine where agents can create
            proposals, accept them, reject them, or counter with alternative terms.
          </p>
          <p>
            Each proposal has a default expiry of <strong>5 steps</strong>. If neither party
            responds in time, the proposal lapses. Counter-proposals create chains of offers that
            build toward agreement or impasse. Try creating proposals and resolving them below.
          </p>

          <NegotiationWidget />

          <p>
            In practice, negotiations emerge naturally from agent interactions. An agent with high
            conscientiousness might propose structured resource sharing, while a high-agreeableness
            agent is more likely to accept. The negotiation outcomes feed back into the trust
            network &mdash; accepting a proposal increases mutual trust, while rejecting decreases it.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            08: MESSAGE BUS
            ================================================================ */}
        <section id="messages" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-message">08</span>
            <div>
              <h2 className="mb-0">Message Bus</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                Three routing modes for agent communication
              </p>
            </div>
          </div>

          <p>
            All agent communication flows through a central{" "}
            <span className="text-message">message bus</span> with three routing modes:{" "}
            <strong>direct</strong> (one-to-one), <strong>broadcast</strong> (one-to-all), and{" "}
            <strong>room-scoped</strong> (one-to-same-location). The bus tracks full message history
            for persistence and replay.
          </p>
          <p>
            Room subscriptions update automatically as agents move between locations. When an agent
            arrives at a new location, they join that room&apos;s channel and leave the old one.
            Select a routing mode, pick a sender, and watch the message propagate.
          </p>

          <MessageBusWidget />

          <p>
            The conversation manager builds on top of the message bus, enabling{" "}
            <strong>multi-turn dialogues</strong> with explicit turn-taking. Conversations are
            capped at 20 turns per step to prevent infinite loops. The bus also feeds the TUI dashboard&apos;s
            live message feed, where observers can filter by location, type, or agent.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            09: SIMULATION TICK LOOP
            ================================================================ */}
        <section id="tick" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-tick">09</span>
            <div>
              <h2 className="mb-0">The Simulation Tick Loop</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                Environment &rarr; Agents &rarr; Reactions &rarr; Persist
              </p>
            </div>
          </div>

          <p>
            Every step of the simulation follows a strict{" "}
            <span className="text-tick">four-phase tick loop</span>. First, environment agents
            update the world &mdash; raising water levels, collapsing structures, spawning events.
            Then human agents process in parallel scenes. Then a reaction round lets agents respond
            to what just happened. Finally, the full state snapshot is persisted.
          </p>
          <p>
            This discrete event simulation model is <strong>deterministic and seedable</strong> &mdash;
            given the same random seed, the same scenario produces the same results. A safety cap of{" "}
            <strong>1,000 steps</strong> prevents infinite loops, and consensus detection auto-stops
            the simulation when agents converge on a resolution.
          </p>

          <SimTickWidget />

          <p>
            The tick loop is the heartbeat of every simulation. Each phase emits WebSocket events
            that the TUI dashboard and web frontend consume in real time. The token budget tracker
            monitors cumulative LLM usage &mdash; when it exceeds 50,000 characters, agents are
            forced to conclude, preventing runaway costs.
          </p>
        </section>

        <div className="section-divider" />

        {/* ================================================================
            10: SCALING
            ================================================================ */}
        <section id="scaling" className="reveal mb-20 scroll-mt-20">
          <div className="flex items-center gap-3 mb-6">
            <span className="font-mono text-3xl font-bold text-scaling">10</span>
            <div>
              <h2 className="mb-0">Full vs. Lightweight Agents</h2>
              <p className="text-sm text-muted-foreground mt-0 mb-0">
                Scaling to 100+ agents without proportional LLM cost
              </p>
            </div>
          </div>

          <p>
            Running 100 agents through full LLM cognitive pipelines would cost thousands of tokens
            per step and take minutes. <span className="text-scaling">Lightweight agents</span>{" "}
            solve this with personality-driven rule-based decisions that require zero LLM calls.
          </p>
          <p>
            Action weights are computed directly from Big Five traits: high extraversion drives
            speaking, high agreeableness drives helping, high openness drives exploration. The key
            innovation is <strong>dynamic promotion</strong> &mdash; a lightweight agent gets
            upgraded to full LLM when it&apos;s addressed directly, in an active scene with high
            extraversion, or when it has high leadership with low stress.
          </p>

          <ScalingWidget />

          <p>
            This hybrid approach means a 100-agent simulation might have 5&ndash;10 full agents at
            any time, with the rest running as lightweight background characters. The promoted agents
            provide rich dialogue and nuanced decisions where it matters, while the lightweight
            agents maintain a living, breathing world around them &mdash; all without proportional
            LLM costs.
          </p>
        </section>

        {/* ================================================================
            CONCLUSION
            ================================================================ */}
        <section className="mb-20">
          <h2 className="text-3xl font-bold leading-tight tracking-[-0.02em] mt-14 mb-6">The emergent whole</h2>
          <p>
            What makes the Emotion Engine unique is how these systems <strong>compose</strong>.{" "}
            <span className="text-personality">Personality traits</span> drive the{" "}
            <span className="text-cognitive">cognitive engine</span>, which produces actions that
            trigger <span className="text-emotion">emotion contagion</span>, reshape the{" "}
            <span className="text-trust">trust network</span>, shift{" "}
            <span className="text-opinion">opinions</span>, and generate{" "}
            <span className="text-negotiation">negotiations</span> &mdash; all coordinated by the{" "}
            <span className="text-scene">scene director</span>, routed through the{" "}
            <span className="text-message">message bus</span>, executed in the{" "}
            <span className="text-tick">tick loop</span>, and{" "}
            <span className="text-scaling">scaled</span> to hundreds of agents.
          </p>
          <p>
            The result is emergent behavior that no single system could produce alone. Agents
            form alliances, break promises, lead evacuations, panic and recover, negotiate
            resource sharing, and reach consensus &mdash; all from the interaction of simple,
            well-defined mechanisms. Run the same scenario with different random seeds and you
            get meaningfully different outcomes, because small personality differences compound
            through these feedback loops.
          </p>
          <p>
            This is the core thesis: <strong>emotional intelligence in AI isn&apos;t programmed
            &mdash; it emerges</strong> from the interaction of personality, memory, social dynamics,
            and environmental pressure. The Emotion Engine is a laboratory for studying that
            emergence.
          </p>
        </section>
      </main>

      {/* ---- Footer ---- */}
      <footer className="border-t border-border py-16 px-6 mt-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-white text-sm" style={{ background: "linear-gradient(135deg, #d4845a, #c47a9b)" }}>
                E
              </div>
              <div>
                <span className="font-semibold text-sm">Emotion Engine</span>
                <p className="text-muted-foreground/60 text-xs mt-0.5">
                  Multi-agent simulation for emergent cooperative behavior
                </p>
              </div>
            </div>
            <div className="flex items-center gap-6 text-xs text-muted-foreground/50">
              <span>Built with Next.js + React + TypeScript</span>
              <a href="https://github.com/jasperan/emotion-engine" className="hover:text-foreground transition-colors" target="_blank" rel="noopener noreferrer">GitHub</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
