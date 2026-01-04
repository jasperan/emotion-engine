<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { scenarios, runs, type Scenario, type Run } from '$lib/api';

	let scenario: Scenario | null = null;
	let runList: Run[] = [];
	let loading = true;
	let error: string | null = null;
	let creating = false;

	$: scenarioId = $page.params.id;

	onMount(async () => {
		try {
			[scenario, runList] = await Promise.all([
				scenarios.get(scenarioId),
				runs.list(scenarioId)
			]);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load scenario';
		} finally {
			loading = false;
		}
	});

	async function createRun() {
		creating = true;
		try {
			const run = await runs.create(scenarioId);
			goto(`/runs/${run.id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create run';
		} finally {
			creating = false;
		}
	}

	async function deleteScenario() {
		if (!confirm('Are you sure you want to delete this scenario and all its runs?')) return;
		
		try {
			await scenarios.delete(scenarioId);
			goto('/');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete scenario';
		}
	}

	function getStatusColor(status: string): string {
		switch (status) {
			case 'running': return 'badge-success';
			case 'paused': return 'badge-warning';
			case 'completed': return 'badge-info';
			case 'failed':
			case 'cancelled': return 'badge-danger';
			default: return 'bg-storm-700 text-storm-300';
		}
	}

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleDateString(undefined, {
			month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
		});
	}
</script>

<svelte:head>
	<title>{scenario?.name || 'Scenario'} | EmotionSim</title>
</svelte:head>

{#if loading}
	<div class="card text-center py-12">
		<div class="w-8 h-8 border-2 border-flood-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
		<p class="text-storm-400 mt-4">Loading scenario...</p>
	</div>
{:else if error}
	<div class="card border-red-500/30 bg-red-900/10">
		<p class="text-red-400">{error}</p>
		<a href="/" class="text-flood-400 hover:text-flood-300 mt-2 inline-block">← Back to Dashboard</a>
	</div>
{:else if scenario}
	<div class="space-y-6">
		<!-- Header -->
		<div class="flex items-start justify-between">
			<div>
				<div class="flex items-center gap-2 text-sm text-storm-400 mb-2">
					<a href="/" class="hover:text-white">Dashboard</a>
					<span>/</span>
					<span>Scenarios</span>
				</div>
				<h1 class="text-3xl font-display font-bold">{scenario.name}</h1>
				{#if scenario.description}
					<p class="text-storm-300 mt-2 max-w-2xl">{scenario.description}</p>
				{/if}
			</div>
			<div class="flex gap-2">
				<button class="btn-primary" on:click={createRun} disabled={creating}>
					{creating ? 'Creating...' : '▶ Start New Run'}
				</button>
				<button class="btn-danger" on:click={deleteScenario}>Delete</button>
			</div>
		</div>

		<!-- Configuration -->
		<div class="grid md:grid-cols-2 gap-6">
			<div class="card">
				<h2 class="text-lg font-semibold font-display mb-4">Configuration</h2>
				<div class="space-y-2 text-sm">
					<div class="flex justify-between">
						<span class="text-storm-400">Max Steps</span>
						<span class="text-storm-200 font-mono">{scenario.config.max_steps || 100}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-storm-400">Tick Delay</span>
						<span class="text-storm-200 font-mono">{scenario.config.tick_delay || 0.5}s</span>
					</div>
					<div class="flex justify-between">
						<span class="text-storm-400">Created</span>
						<span class="text-storm-200">{formatDate(scenario.created_at)}</span>
					</div>
				</div>
			</div>

			<div class="card">
				<h2 class="text-lg font-semibold font-display mb-4">Agent Templates ({scenario.agent_templates?.length || 0})</h2>
				{#if scenario.agent_templates?.length > 0}
					<div class="space-y-2">
						{#each scenario.agent_templates as agent}
							<div class="flex items-center gap-3 p-2 bg-storm-800/50 rounded">
								<div class="flex-1">
									<span class="font-medium">{agent.name}</span>
									<span class="text-sm text-storm-400 ml-2 capitalize">({agent.role})</span>
								</div>
								{#if agent.persona}
									<span class="text-xs text-storm-400">
										{agent.persona.age}yo {agent.persona.occupation}
									</span>
								{/if}
							</div>
						{/each}
					</div>
				{:else}
					<p class="text-storm-400 text-sm">No agents configured.</p>
				{/if}
			</div>
		</div>

		<!-- Runs -->
		<div class="card">
			<h2 class="text-lg font-semibold font-display mb-4">Runs</h2>
			
			{#if runList.length === 0}
				<p class="text-storm-400 text-center py-8">No runs yet. Click "Start New Run" to begin!</p>
			{:else}
				<table class="w-full">
					<thead class="text-left text-sm text-storm-400 border-b border-storm-700/50">
						<tr>
							<th class="pb-2 font-medium">Run ID</th>
							<th class="pb-2 font-medium">Status</th>
							<th class="pb-2 font-medium">Progress</th>
							<th class="pb-2 font-medium">Created</th>
							<th class="pb-2"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-storm-700/30">
						{#each runList as run}
							<tr class="hover:bg-storm-800/30">
								<td class="py-3">
									<span class="font-mono text-sm text-storm-300">{run.id.slice(0, 8)}...</span>
								</td>
								<td class="py-3">
									<span class="badge {getStatusColor(run.status)} capitalize">{run.status}</span>
								</td>
								<td class="py-3">
									<div class="flex items-center gap-2">
										<div class="w-20 h-1.5 bg-storm-800 rounded-full overflow-hidden">
											<div 
												class="h-full bg-flood-500 rounded-full"
												style="width: {(run.current_step / run.max_steps) * 100}%"
											></div>
										</div>
										<span class="text-xs text-storm-400 font-mono">
											{run.current_step}/{run.max_steps}
										</span>
									</div>
								</td>
								<td class="py-3 text-sm text-storm-400">{formatDate(run.created_at)}</td>
								<td class="py-3 text-right">
									<a href="/runs/{run.id}" class="text-flood-400 hover:text-flood-300 text-sm">
										View →
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>
	</div>
{/if}

