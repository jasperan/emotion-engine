"use client";

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
  { id: "personality", title: "Personality" },
  { id: "cognitive", title: "Cognitive" },
  { id: "emotion", title: "Contagion" },
  { id: "trust", title: "Trust" },
  { id: "opinion", title: "Opinion" },
  { id: "scenes", title: "Scenes" },
  { id: "negotiation", title: "Negotiation" },
  { id: "messages", title: "Messages" },
  { id: "tick", title: "Tick loop" },
  { id: "scaling", title: "Scaling" },
];

const contents = [
  { id: "personality", tick: "t·01", title: "Big Five personality traits", desc: "Trait-driven behavior" },
  { id: "cognitive", tick: "t·02", title: "The cognitive engine", desc: "Think, plan, act, reflect" },
  { id: "emotion", tick: "t·03", title: "Emotion contagion", desc: "Spread rate 0.3" },
  { id: "trust", tick: "t·04", title: "Trust network", desc: "Vouch and betray dynamics" },
  { id: "opinion", tick: "t·05", title: "Opinion dynamics", desc: "Influence, trust, and bias" },
  { id: "scenes", tick: "t·06", title: "Scene director", desc: "Location-based parallelism" },
  { id: "negotiation", tick: "t·07", title: "Negotiation", desc: "Proposal state machine" },
  { id: "messages", tick: "t·08", title: "Message bus", desc: "Three routing modes" },
  { id: "tick", tick: "t·09", title: "The tick loop", desc: "Four-phase simulation step" },
  { id: "scaling", tick: "t·10", title: "Scaling", desc: "Full and lightweight" },
];

/* A run in progress: the one place on this page that shows the product
   itself, with plausible values from the harbor-flood scenario. */
const agents = [
  { name: "Dr. Chen", stress: 2.0, tone: "pos" },
  { name: "Marcus", stress: 6.4, tone: "warn" },
  { name: "Sofia", stress: 3.1, tone: "pos" },
  { name: "Amir", stress: 8.2, tone: "neg" },
] as const;

const events = [
  { tick: "t·012", who: "Marcus → Sofia", what: "east stair gone", tone: "plain" },
  { tick: "t·013", who: "Sofia → Marcus", what: "vouch · 5→7", tone: "pos" },
  { tick: "t·014", who: "Amir", what: "panics · stress 8.2", tone: "neg" },
] as const;

export default function Home() {
  return (
    <div className="min-h-screen">
      <a href="#main-content" className="skip-link">Skip to main content</a>

      {/* ---- Nav ---- */}
      <nav
        className="sticky top-0 z-50 bg-background border-b border-border"
        aria-label="Section navigation"
      >
        <div className="page-shell py-2.5 flex items-center gap-1 overflow-x-auto scrollbar-hide">
          <a href="#top" className="font-display text-[15px] font-medium text-foreground mr-4 whitespace-nowrap">
            Emotion Engine
          </a>
          {sections.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="nav-link">
              {s.title}
            </a>
          ))}
        </div>
      </nav>

      {/* ---- Hero ---- */}
      <header id="top" className="page-shell pt-16 pb-12 md:pt-24 md:pb-16">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_440px] lg:gap-16 lg:items-center">
          <div>
            <p className="font-mono text-xs text-muted-foreground mb-5">
              Interactive explorer
            </p>
            <h1
              className="font-display text-[40px] md:text-[56px] font-medium leading-[1.05] tracking-[-0.02em] mb-6"
              style={{ textWrap: "balance" as never }}
            >
              Inside the Emotion Engine
            </h1>
            <p
              className="text-[17px] text-muted-foreground leading-relaxed max-w-[54ch]"
              style={{ textWrap: "pretty" as never }}
            >
              Ten mechanisms of a multi-agent simulator, each one you can drive by hand:
              how personality traits set behavior, how a cognitive pipeline decides,
              how stress and trust and opinion move between agents.
            </p>
            <div className="flex flex-wrap items-center gap-4 mt-8">
              <a
                href="#personality"
                className="inline-flex items-center h-11 px-5 rounded-lg bg-[#249eb3] hover:bg-[#40bace] text-white text-[14px] font-medium transition-colors duration-150"
              >
                Start with personality
              </a>
              <a
                href="https://github.com/jasperan/emotion-engine"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[14px] text-muted-foreground hover:text-foreground transition-colors duration-150"
              >
                Source on GitHub
              </a>
            </div>
          </div>

          {/* ---- The run ---- */}
          <div className="instrument" aria-label="A simulation run in progress">
            <div className="instrument-head">
              <span>harbor-flood · run 04</span>
              <span className="text-foreground">t·014</span>
            </div>

            <div className="px-4 py-3 grid grid-cols-2 gap-x-4 gap-y-3 border-b border-border">
              {agents.map((a) => (
                <div key={a.name}>
                  <div className="flex items-baseline justify-between font-mono text-xs">
                    <span className="text-muted-foreground">{a.name}</span>
                    <span
                      className="tabular-nums"
                      style={{ color: `var(--${a.tone})` }}
                    >
                      {a.stress.toFixed(1)}
                    </span>
                  </div>
                  <div className="mt-2 h-[2px] rounded-full bg-white/10">
                    <div
                      className="h-[2px] rounded-full"
                      style={{ width: `${a.stress * 10}%`, background: `var(--${a.tone})` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="py-1">
              {events.map((e) => (
                <div key={e.tick} className="instrument-row">
                  <span className="tick">{e.tick}</span>
                  <span className="text-foreground/80 shrink-0">{e.who}</span>
                  <span
                    className="truncate"
                    style={{ color: e.tone === "plain" ? "var(--text-muted)" : `var(--${e.tone})` }}
                  >
                    {e.what}
                  </span>
                </div>
              ))}
            </div>

            <div className="instrument-head border-t border-b-0">
              <span>4 full · 12 lightweight</span>
              <span>stress avg 4.9</span>
            </div>
          </div>
        </div>
      </header>

      {/* ---- Contents ---- */}
      <div className="page-shell pb-16">
        <div className="border-t border-border pt-5">
          <h2 className="font-mono text-xs text-muted-foreground mb-4">Sections</h2>
          <div className="grid gap-x-12 sm:grid-cols-2">
            {contents.map((ch) => (
              <a
                key={ch.id}
                href={`#${ch.id}`}
                className="group grid grid-cols-[44px_minmax(0,1fr)_168px] items-baseline gap-3 py-3 border-b border-border"
              >
                <span className="tick">{ch.tick}</span>
                <span className="text-sm font-medium text-foreground/90 group-hover:text-foreground truncate">
                  {ch.title}
                </span>
                <span className="text-xs text-muted-foreground hidden sm:block">
                  {ch.desc}
                </span>
              </a>
            ))}
          </div>
        </div>
      </div>

      <main id="main-content" className="page-shell prose-dark pb-8" tabIndex={-1}>
        {/* ================================================================
            01: BIG FIVE PERSONALITY TRAITS
            ================================================================ */}
        <section id="personality" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·01</span>
            <div>
              <h2>Big Five personality traits</h2>
              <p className="section-sub">The mechanical foundation of agent decision-making</p>
            </div>
          </div>

          <p>
            Every agent in the Emotion Engine has a <strong>persona</strong>{" "}defined by the Big Five
            personality model &mdash; the same framework used in psychology research. These five
            traits aren&apos;t just flavor text: they <strong>mechanically drive</strong> what agents
            do each simulation step.
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
            shape the <code>should_respond()</code> probability (whether to act at all), while the
            cognitive engine decides what to do.
          </p>
        </section>

        {/* ================================================================
            02: COGNITIVE ENGINE
            ================================================================ */}
        <section id="cognitive" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·02</span>
            <div>
              <h2>The cognitive engine</h2>
              <p className="section-sub">Think, plan, act, reflect</p>
            </div>
          </div>

          <p>
            Each agent runs a four-stage cognitive pipeline every simulation step. First, they{" "}
            <strong>think</strong> &mdash; assessing the situation and determining urgency. Then
            they <strong>plan</strong> &mdash; generating an action plan with steps, deadlines, and
            contingencies. Then they <strong>act</strong> &mdash; executing their chosen action and
            emitting messages. Finally, they <strong>reflect</strong> &mdash; storing the experience
            in episodic memory and updating relationships.
          </p>
          <p>
            This pipeline runs for every LLM-driven agent on every tick. Smart replanning kicks in
            when a plan goes stale &mdash; if the deadline passes, progress stagnates, or the
            situation changes dramatically, the agent replans from scratch.
          </p>

          <CognitiveEngineWidget />

          <p>
            The cognitive engine is what separates the Emotion Engine from simple chatbot
            simulations. Agents don&apos;t just react &mdash; they form intentions, track progress,
            and learn from outcomes. The <strong>reflect</strong> stage is crucial: it creates{" "}
            <strong>episodic memories</strong> with emotional valence, so agents can recall past
            experiences when making future decisions.
          </p>
        </section>

        {/* ================================================================
            03: EMOTION CONTAGION
            ================================================================ */}
        <section id="emotion" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·03</span>
            <div>
              <h2>Emotion contagion</h2>
              <p className="section-sub">How panic spreads through a group</p>
            </div>
          </div>

          <p>
            In real disasters, emotions are contagious. One person panicking can trigger a cascade
            that spreads through an entire group. The Emotion Engine models this with an emotion
            contagion system where stress propagates between co-located agents.
          </p>
          <p>
            The spread rate is <strong>0.3</strong>, meaning each step, an agent absorbs 30% of the
            average stress around them. A calm factor of <strong>0.5</strong>{" "}provides natural
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

        {/* ================================================================
            04: TRUST NETWORK
            ================================================================ */}
        <section id="trust" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·04</span>
            <div>
              <h2>Trust network</h2>
              <p className="section-sub">Bilateral vouch and betray signals</p>
            </div>
          </div>

          <p>
            Agents don&apos;t just interact &mdash; they build relationships. The trust network
            tracks a 1&ndash;10 trust score between every pair of agents. Trust increases when
            agents cooperate (vouch) and decreases when they compete or betray.
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
            over the simulation. Trust also feeds into the opinion dynamics system, where
            high-trust agents have more influence over each other&apos;s beliefs.
          </p>
        </section>

        {/* ================================================================
            05: OPINION DYNAMICS
            ================================================================ */}
        <section id="opinion" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·05</span>
            <div>
              <h2>Opinion dynamics</h2>
              <p className="section-sub">How beliefs shift through social influence</p>
            </div>
          </div>

          <p>
            Agents hold opinions on key topics &mdash; like whether to evacuate, where to go, or who
            to trust as leader. These opinions are numbers from &minus;1.0 (strongly against) to
            +1.0 (strongly for), and they shift when agents interact.
          </p>
          <p>
            The shift formula depends on four factors: the influencer&apos;s{" "}
            <strong>influence level</strong>, the <strong>trust</strong>{" "}between agents, the
            target&apos;s <strong>opinion bias</strong> (resistance to change), and the{" "}
            <strong>distance</strong> between their current positions. Highly resistant agents
            barely budge. Easily swayed agents converge quickly.
          </p>

          <OpinionDynamicsWidget />

          <p>
            The sentiment tracker monitors these opinion trajectories and detects{" "}
            <strong>tipping points</strong> &mdash; moments when the group suddenly converges or
            diverges on a topic. In practice, this determines when the group reaches consensus on
            evacuation plans, or when a faction splits off with a competing strategy.
          </p>
        </section>

        {/* ================================================================
            06: SCENE DIRECTOR
            ================================================================ */}
        <section id="scenes" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·06</span>
            <div>
              <h2>Scene director</h2>
              <p className="section-sub">Location-based parallel processing</p>
            </div>
          </div>

          <p>
            With 10+ agents, processing everyone sequentially is slow. The scene director groups
            agents by location into independent &ldquo;scenes&rdquo; that can run in parallel. Agents
            on the rooftop form one scene. Agents at the bridge form another. Since they can&apos;t
            interact across locations, their scenes are independent.
          </p>
          <p>
            With vLLM&apos;s continuous batching, all scenes process simultaneously &mdash; turning a
            3-scene simulation from 9 seconds to 3 seconds per step. Move agents between locations
            to see how scene groupings change.
          </p>

          <SceneDirectorWidget />

          <p>
            This is a key architectural insight: <strong>spatial locality enables parallelism</strong>.
            Agents who are physically apart can&apos;t influence each other within a single step, so
            their processing is embarrassingly parallel. The scene director also limits each scene to
            3 turns to prevent runaway dialogues.
          </p>
        </section>

        {/* ================================================================
            07: NEGOTIATION THEATER
            ================================================================ */}
        <section id="negotiation" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·07</span>
            <div>
              <h2>Negotiation</h2>
              <p className="section-sub">Proposals, counter-proposals, and resolution</p>
            </div>
          </div>

          <p>
            Agents don&apos;t just talk &mdash; they negotiate. The negotiation manager implements a
            proposal state machine where agents can create proposals, accept them, reject them, or
            counter with alternative terms.
          </p>
          <p>
            Each proposal has a default expiry of <strong>5 steps</strong>. If neither party responds
            in time, the proposal lapses. Counter-proposals create chains of offers that build toward
            agreement or impasse. Try creating proposals and resolving them below.
          </p>

          <NegotiationWidget />

          <p>
            In practice, negotiations emerge naturally from agent interactions. An agent with high
            conscientiousness might propose structured resource sharing, while a high-agreeableness
            agent is more likely to accept. The negotiation outcomes feed back into the trust network
            &mdash; accepting a proposal increases mutual trust, while rejecting decreases it.
          </p>
        </section>

        {/* ================================================================
            08: MESSAGE BUS
            ================================================================ */}
        <section id="messages" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·08</span>
            <div>
              <h2>Message bus</h2>
              <p className="section-sub">Three routing modes for agent communication</p>
            </div>
          </div>

          <p>
            All agent communication flows through a central message bus with three routing modes:{" "}
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
            <strong>multi-turn dialogues</strong>{" "}with explicit turn-taking. Conversations are capped
            at 20 turns per step to prevent infinite loops. The bus also feeds the TUI
            dashboard&apos;s live message feed, where observers can filter by location, type, or agent.
          </p>
        </section>

        {/* ================================================================
            09: SIMULATION TICK LOOP
            ================================================================ */}
        <section id="tick" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·09</span>
            <div>
              <h2>The tick loop</h2>
              <p className="section-sub">Environment, agents, reactions, persist</p>
            </div>
          </div>

          <p>
            Every step of the simulation follows a strict four-phase tick loop. First, environment
            agents update the world &mdash; raising water levels, collapsing structures, spawning
            events. Then human agents process in parallel scenes. Then a reaction round lets agents
            respond to what just happened. Finally, the full state snapshot is persisted.
          </p>
          <p>
            This discrete event simulation model is <strong>deterministic and seedable</strong>{" "}
            &mdash; given the same random seed, the same scenario produces the same results. A safety
            cap of <strong>1,000 steps</strong> prevents infinite loops, and consensus detection
            auto-stops the simulation when agents converge on a resolution.
          </p>

          <SimTickWidget />

          <p>
            The tick loop is the heartbeat of every simulation. Each phase emits WebSocket events
            that the TUI dashboard and web frontend consume in real time. The token budget tracker
            monitors cumulative LLM usage &mdash; when it exceeds 50,000 characters, agents are forced
            to conclude, preventing runaway costs.
          </p>
        </section>

        {/* ================================================================
            10: SCALING
            ================================================================ */}
        <section id="scaling" className="mb-20 scroll-mt-16">
          <div className="section-head">
            <span className="tick">t·10</span>
            <div>
              <h2>Scaling</h2>
              <p className="section-sub">Full and lightweight agents in one run</p>
            </div>
          </div>

          <p>
            Running 100 agents through full LLM cognitive pipelines would cost thousands of tokens
            per step and take minutes. Lightweight agents solve this with personality-driven
            rule-based decisions that require zero LLM calls.
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
            This hybrid approach means a 100-agent simulation might have 5&ndash;10 full agents at any
            time, with the rest running as lightweight background characters. The promoted agents
            provide rich dialogue and nuanced decisions where it matters, while the lightweight
            agents maintain a living, breathing world around them &mdash; all without proportional
            LLM costs.
          </p>
        </section>

        {/* ================================================================
            CONCLUSION
            ================================================================ */}
        <section className="mb-20">
          <div className="section-head">
            <span className="tick">t·∞</span>
            <div>
              <h2>The emergent whole</h2>
              <p className="section-sub">What the ten mechanisms produce together</p>
            </div>
          </div>
          <p>
            What makes the Emotion Engine unique is how these systems <strong>compose</strong>.
            Personality traits drive the cognitive engine, which produces actions that trigger
            emotion contagion, reshape the trust network, shift opinions, and generate negotiations
            &mdash; all coordinated by the scene director, routed through the message bus, executed in
            the tick loop, and scaled to hundreds of agents.
          </p>
          <p>
            The result is emergent behavior that no single system could produce alone. Agents form
            alliances, break promises, lead evacuations, panic and recover, negotiate resource
            sharing, and reach consensus &mdash; all from the interaction of simple, well-defined
            mechanisms. Run the same scenario with different random seeds and you get meaningfully
            different outcomes, because small personality differences compound through these feedback
            loops.
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
      <footer className="border-t border-border py-12">
        <div className="page-shell">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[var(--surface-alt)] border border-border flex items-center justify-center font-display font-medium text-[15px] text-[var(--accent)]">
                E
              </div>
              <div>
                <span className="text-sm font-medium">Emotion Engine</span>
                <p className="text-muted-foreground text-xs mt-0.5">
                  Multi-agent simulation for emergent cooperative behavior
                </p>
              </div>
            </div>
            <div className="flex items-center gap-6 text-xs text-muted-foreground">
              <span>Next.js, React, TypeScript</span>
              <a
                href="https://github.com/jasperan/emotion-engine"
                className="hover:text-foreground transition-colors duration-150"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
