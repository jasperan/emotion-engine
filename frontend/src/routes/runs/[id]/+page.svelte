<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, onDestroy } from 'svelte';
	import { runs, type Run, type Agent, type Message } from '$lib/api';
	import { websocket } from '$lib/stores/websocket';
	import AgentCard from '$lib/components/AgentCard.svelte';
	import MessageLog from '$lib/components/MessageLog.svelte';
	import SimulationControls from '$lib/components/SimulationControls.svelte';

	let run: Run | null = null;
	let agents: Agent[] = [];
	let messages: Message[] = [];
	let loading = true;
	let error: string | null = null;

	$: runId = $page.params.id;
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

	onMount(async () => {
		try {
			await refreshData();
			websocket.connect(runId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load run';
		} finally {
			loading = false;
		}
	});

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
	<div class="card text-center py-12">
		<div
			class="w-8 h-8 border-2 border-flood-500 border-t-transparent rounded-full animate-spin mx-auto"
		></div>
		<p class="text-storm-400 mt-4">Loading run...</p>
	</div>
{:else if error}
	<div class="card border-red-500/30 bg-red-900/10">
		<p class="text-red-400">{error}</p>
		<a href="/" class="text-flood-400 hover:text-flood-300 mt-2 inline-block"
			>← Back to Dashboard</a
		>
	</div>
{:else if run}
	<div class="space-y-6">
		<!-- Header -->
		<div class="flex items-start justify-between">
			<div>
				<div class="flex items-center gap-2 text-sm text-storm-400 mb-2">
					<a href="/" class="hover:text-white">Dashboard</a>
					<span>/</span>
					<a href="/scenarios/{run.scenario_id}" class="hover:text-white">Scenario</a>
					<span>/</span>
					<span>Run</span>
				</div>
				<h1 class="text-2xl font-display font-bold">
					Run <span class="font-mono text-flood-400">{run.id.slice(0, 8)}</span>
				</h1>
			</div>
			<div class="flex items-center gap-2">
				{#if wsState.connected}
					<span class="badge badge-success">
						<span class="w-2 h-2 bg-green-400 rounded-full mr-1 animate-pulse"></span>
						Live
					</span>
				{:else}
					<span class="badge badge-warning">Disconnected</span>
				{/if}
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
							<span class="text-storm-400">Hazard Level</span>
							<div class="flex items-center gap-2">
								<div class="w-20 h-2 bg-storm-800 rounded-full overflow-hidden">
									<div
										class="h-full bg-gradient-to-r from-yellow-500 to-red-500 rounded-full"
										style="width: {((run.world_state?.hazard_level as number) || 0) * 10}%"
									></div>
								</div>
								<span class="text-storm-200 font-mono"
									>{(run.world_state?.hazard_level as number) || 0}/10</span
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

			<!-- Right: Message Log -->
			<div class="lg:col-span-2">
				<MessageLog {messages} {agents} />
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
	</div>
{/if}

