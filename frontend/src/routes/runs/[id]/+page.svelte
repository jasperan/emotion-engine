<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, onDestroy } from 'svelte';
	import { runs, type Run, type Agent, type Message, type RunMetrics, type RunStep } from '$lib/api';
	import { websocket } from '$lib/stores/websocket';
	import AgentCard from '$lib/components/AgentCard.svelte';
	import MessageLog from '$lib/components/MessageLog.svelte';
	import LiveEventStream from '$lib/components/LiveEventStream.svelte';
	import TokenStream from '$lib/components/TokenStream.svelte';
	import SimulationControls from '$lib/components/SimulationControls.svelte';
	import { setHeader, resetHeader } from '$lib/stores/header';

	let run: Run | null = null;
	let agents: Agent[] = [];
	let messages: Message[] = [];
	let metrics: RunMetrics | null = null;
	let steps: RunStep[] = [];
	let expandedStep: number | null = null;
	let loading = true;
	let error: string | null = null;

	$: runId = $page.params.id as string;
	$: wsState = $websocket;

	// Update data when WebSocket events arrive
	$: if (wsState.lastEvent) {
		handleEvent(wsState.lastEvent);
	}

	function handleEvent(event: { event: string; data: Record<string, unknown> }) {
		if (event.event === 'step_completed') {
			// Update run state
			if (run) {
				run.current_step = (event.data.step as number) || run.current_step;
				run.world_state = (event.data.world_state as Record<string, unknown>) || run.world_state;
			}

			// Add new messages
			const stepMessages = (event.data.messages as Message[]) || [];
			if (stepMessages.length > 0) {
				messages = [...messages, ...stepMessages];
			}

			// Cap message accumulation
			const MAX_MESSAGES = 500;
			if (messages.length > MAX_MESSAGES) {
				messages = messages.slice(-MAX_MESSAGES);
			}
		} else if (event.event === 'run_completed' || event.event === 'run_stopped') {
			if (run) {
				run.status = event.event === 'run_completed' ? 'completed' : 'cancelled';
			}
			refreshData();
		} else if (event.event === 'run_paused') {
			if (run) {
				run.status = 'paused';
			}
		} else if (event.event === 'run_started') {
			if (run) {
				run.status = 'running';
			}
		}
	}

	async function refreshData() {
		try {
			[run, agents, messages] = await Promise.all([
				runs.get(runId),
				runs.agents(runId),
				runs.messages(runId)
			]);
		} catch (e) {
			console.error('Failed to refresh data:', e);
		}
	}

	async function loadAnalytics() {
		try {
			[metrics, steps] = await Promise.all([
				runs.metrics(runId),
				runs.steps(runId)
			]);
		} catch (e) {
			console.error('Failed to load analytics:', e);
		}
	}

	function metricValue(key: string): number | string {
		const m = metrics?.metrics;
		if (!m || m[key] === undefined) return '—';
		const v = m[key];
		return typeof v === 'number' ? v.toFixed(2) : String(v);
	}

	$: stressSeries = steps.map((s) => Number(s.step_metrics?.avg_stress) || 0);
	$: maxStress = Math.max(10, ...stressSeries);

	onMount(() => {
		async function init() {
			try {
				await refreshData();
				loadAnalytics();
				websocket.connect(runId);
				updateHeader();
			} catch (e) {
				error = e instanceof Error ? e.message : 'Failed to load run';
			} finally {
				loading = false;
			}
		}

		init();
		return () => resetHeader();
	});

	function updateHeader() {
		if (!run) return;
		
		const statusLabel = run.status === 'completed' ? 'Completed' : (wsState.connected ? 'Live' : 'Disconnected');
		
		setHeader({
			title: 'Run Detail',
			breadcrumb: [
				{ label: 'Library', href: '/library' },
				{ label: 'Scenario', href: `/scenarios/${run.scenario_id}` }
			],
			actions: [
				{ label: statusLabel, onclick: () => {}, primary: run.status === 'running' }
			]
		});
	}

	$: if (run || wsState.connected) {
		updateHeader();
	}

	onDestroy(() => {
		websocket.disconnect();
	});

	function handleControlAction() {
		// Refresh run data after control action
		setTimeout(refreshData, 500);
	}
</script>

<svelte:head>
	<title>Run {runId.slice(0, 8)} | EmotionSim</title>
</svelte:head>

{#if loading}
	<div class="space-y-6 max-w-7xl mx-auto">
		<div class="border-b border-outline/20 pb-4">
			<div class="skeleton h-7 w-64"></div>
		</div>
		<div class="grid lg:grid-cols-3 gap-6">
			<div class="space-y-6">
				<div class="skeleton h-44 rounded-xl"></div>
				<div class="skeleton h-32 rounded-xl"></div>
				{#each Array(3) as _}
					<div class="skeleton h-28 rounded-xl"></div>
				{/each}
			</div>
			<div class="lg:col-span-2">
				<div class="skeleton h-[500px] rounded-xl"></div>
			</div>
		</div>
	</div>
{:else if error}
	<div class="card border-red-500/30 bg-red-900/10">
		<p class="text-red-400">{error}</p>
		<a href="/" class="text-flood-400 hover:text-flood-300 mt-2 inline-block"
			>← Back to Dashboard</a
		>
	</div>
{:else if run}
	<div class="space-y-6 max-w-7xl mx-auto">
		<!-- Header -->
		<div class="flex items-end justify-between border-b border-outline/20 pb-4">
			<div>
				<h1 class="text-2xl font-display font-bold text-on-background">
					Simulation Run <span class="font-mono text-primary ml-1">#{run.id.slice(0, 8)}</span>
				</h1>
			</div>
		</div>

		<!-- Main Layout -->
		<div class="grid lg:grid-cols-3 gap-6">
			<!-- Left: Controls + Agents -->
			<div class="lg:col-span-1 space-y-6">
				<SimulationControls {run} on:action={handleControlAction} />

				<!-- World State -->
				<div class="card">
					<h3 class="text-lg font-semibold font-display mb-3">World State</h3>
					<div class="space-y-2 text-sm">
						<div class="flex justify-between">
							<span id="hazard-level-label" class="text-storm-400">Hazard Level</span>
							<div class="flex items-center gap-2">
								<div
									class="w-20 h-2 bg-storm-800 rounded-full overflow-hidden"
									role="progressbar"
									aria-labelledby="hazard-level-label"
									aria-valuenow={Number(run.world_state?.hazard_level) || 0}
									aria-valuemin="0"
									aria-valuemax="10"
								>
									<div
										class="h-full bg-gradient-to-r from-yellow-500 to-red-500 rounded-full"
										style="width: {(Number(run.world_state?.hazard_level) || 0) * 10}%"
									></div>
								</div>
								<span class="text-storm-200 font-mono" aria-hidden="true"
									>{Number(run.world_state?.hazard_level) || 0}/10</span
								>
							</div>
						</div>
					</div>
				</div>

				<!-- Agent Cards -->
				<div class="space-y-4">
					<h3 class="text-lg font-semibold font-display">Agents ({agents.length})</h3>
					{#each agents as agent}
						<AgentCard {agent} />
					{/each}
				</div>
			</div>

			<!-- Right: Token Stream + Message Log + Live Event Stream -->
			<div class="lg:col-span-2 space-y-6">
				{#if run.status === 'running'}
					<TokenStream events={wsState.events} />
				{/if}
				<MessageLog {messages} {agents} />
				<LiveEventStream events={wsState.events} />
			</div>
		</div>

		<!-- Evaluation (if completed) -->
		{#if run.status === 'completed' && run.evaluation && Object.keys(run.evaluation).length > 0}
			<div class="card border-flood-500/30">
				<h2 class="text-xl font-display font-semibold mb-4">Evaluation Results</h2>

				{#if run.evaluation.scores}
					<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
						{#each Object.entries(run.evaluation.scores) as [key, value]}
							<div class="text-center p-3 bg-storm-800/50 rounded-lg">
								<div class="text-2xl font-bold text-flood-400">{value}</div>
								<div class="text-xs text-storm-400 capitalize">{key.replace('_', ' ')}</div>
							</div>
						{/each}
					</div>
				{/if}

				{#if run.evaluation.narrative}
					<div class="prose prose-invert prose-sm max-w-none">
						<p class="text-storm-200 whitespace-pre-wrap">{run.evaluation.narrative}</p>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Analytics + Replay (Step 9) -->
		<div class="card">
			<h2 class="text-xl font-display font-semibold mb-4">Run Analytics</h2>
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
				<div class="text-center p-3 bg-storm-800/50 rounded-lg">
					<div class="text-2xl font-bold text-flood-400">{metricValue('avg_stress')}</div>
					<div class="text-xs text-storm-400">Avg Stress</div>
				</div>
				<div class="text-center p-3 bg-storm-800/50 rounded-lg">
					<div class="text-2xl font-bold text-flood-400">{metricValue('avg_health')}</div>
					<div class="text-xs text-storm-400">Avg Health</div>
				</div>
				<div class="text-center p-3 bg-storm-800/50 rounded-lg">
					<div class="text-2xl font-bold text-flood-400">{metricValue('tokens')}</div>
					<div class="text-xs text-storm-400">Streamed Tokens</div>
				</div>
				<div class="text-center p-3 bg-storm-800/50 rounded-lg">
					<div class="text-2xl font-bold text-flood-400">{metricValue('cost_estimate_usd')} $</div>
					<div class="text-xs text-storm-400">Est. Cost</div>
				</div>
				<div class="text-center p-3 bg-storm-800/50 rounded-lg">
					<div class="text-2xl font-bold text-flood-400">{metricValue('latency_ms')} ms</div>
					<div class="text-xs text-storm-400">Last Tick Latency</div>
				</div>
				<div class="text-center p-3 bg-storm-800/50 rounded-lg">
					<div class="text-2xl font-bold text-flood-400">{metricValue('message_count')}</div>
					<div class="text-xs text-storm-400">Messages</div>
				</div>
			</div>

			{#if stressSeries.length > 1}
				<h3 class="text-lg font-semibold font-display mb-2">Avg Stress per Step</h3>
				<div class="flex items-end gap-1 h-24 mb-6" role="img" aria-label="Average stress per step bar chart">
					{#each stressSeries as s, i}
						<div
							class="flex-1 rounded-t bg-flood-500/70 hover:bg-flood-400 transition-colors"
							style="height: {Math.max(4, (s / maxStress) * 100)}%"
							title="Step {i + 1}: stress {s.toFixed(1)}"
						></div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Replay timeline (Step 9) -->
		<div class="card">
			<h2 class="text-xl font-display font-semibold mb-4">Replay Timeline</h2>
			{#if steps.length === 0}
				<p class="text-storm-400 text-sm">No steps recorded yet.</p>
			{:else}
				<ol class="relative border-l border-outline/20 ml-3 space-y-4">
					{#each steps as step}
						<li class="ml-4">
							<button
								class="text-left w-full flex items-center justify-between gap-3 group"
								on:click={() => (expandedStep = expandedStep === step.step_index ? null : step.step_index)}
							>
								<div class="flex items-center gap-3">
									<span class="absolute -left-1.5 w-3 h-3 rounded-full bg-primary border-2 border-background"></span>
									<span class="font-mono text-primary">Step {step.step_index}</span>
								</div>
								<div class="text-xs text-storm-400 group-hover:text-storm-200">
									{step.actions?.length ?? 0} actions ·
									hazard {String(step.step_metrics?.hazard_level ?? '?')}
								</div>
							</button>
							{#if expandedStep === step.step_index && step.actions?.length}
								<ul class="mt-2 space-y-1 text-xs text-storm-300">
									{#each step.actions.slice(0, 30) as action}
										<li class="flex gap-2">
											<span class="text-primary font-mono">{action.action_type}</span>
											<span class="text-storm-400">
												{String(action.agent_name ?? '')} {String(action.target ?? '')}
											</span>
										</li>
									{/each}
								</ul>
							{/if}
						</li>
					{/each}
				</ol>
			{/if}
		</div>
	</div>
{/if}

