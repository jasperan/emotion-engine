<script lang="ts">
	import { onMount } from 'svelte';
	import { scenarios, runs, type Scenario, type Run } from '$lib/api';

	let scenarioList: Scenario[] = [];
	let runList: Run[] = [];
	let loading = true;
	let error: string | null = null;

	onMount(async () => {
		try {
			[scenarioList, runList] = await Promise.all([scenarios.list(), runs.list()]);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load data';
		} finally {
			loading = false;
		}
	});

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function getStatusColor(status: string): string {
		switch (status) {
			case 'running':
				return 'badge-success';
			case 'paused':
				return 'badge-warning';
			case 'completed':
				return 'badge-info';
			case 'failed':
			case 'cancelled':
				return 'badge-danger';
			default:
				return 'bg-storm-700 text-storm-300';
		}
	}
</script>

<svelte:head>
	<title>EmotionSim Dashboard</title>
</svelte:head>

<div class="space-y-8">
	<!-- Hero Section -->
	<div class="card bg-gradient-to-br from-storm-900/80 to-flood-950/50 border-flood-700/30">
		<div class="flex items-center gap-6">
			<div
				class="w-20 h-20 bg-gradient-to-br from-flood-400 to-storm-600 rounded-2xl flex items-center justify-center shadow-xl animate-float"
			>
				<span class="text-4xl">🌊</span>
			</div>
			<div>
				<h1 class="text-3xl font-display font-bold mb-2">Emotion Engine</h1>
				<p class="text-storm-300 max-w-2xl">
					Run AI agent swarms in parallel disaster simulations. Create scenarios, watch agents
					roleplay with unique personalities, and analyze their cooperation and decision-making.
				</p>
			</div>
		</div>
	</div>

	<!-- Scenarios Section -->
	<section>
		<div class="flex items-center justify-between mb-4">
			<h2 class="text-xl font-display font-semibold">Scenarios</h2>
			<a href="/scenarios/new" class="btn-primary text-sm">+ Create Scenario</a>
		</div>

		{#if loading}
			<div class="card text-center py-12">
				<div
					class="w-8 h-8 border-2 border-flood-500 border-t-transparent rounded-full animate-spin mx-auto"
				></div>
				<p class="text-storm-400 mt-4">Loading scenarios...</p>
			</div>
		{:else if error}
			<div class="card border-red-500/30 bg-red-900/10">
				<p class="text-red-400">Error: {error}</p>
			</div>
		{:else if scenarioList.length === 0}
			<div class="card text-center py-12">
				<p class="text-storm-400 mb-4">No scenarios yet. Create your first one!</p>
				<a href="/scenarios/new" class="btn-primary">Create Scenario</a>
			</div>
		{:else}
			<div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each scenarioList as scenario}
					<a
						href="/scenarios/{scenario.id}"
						class="card hover:border-flood-500/50 transition-all hover:shadow-lg hover:shadow-flood-500/10"
					>
						<h3 class="text-lg font-semibold font-display mb-2">{scenario.name}</h3>
						<p class="text-sm text-storm-400 mb-3 line-clamp-2">
							{scenario.description || 'No description'}
						</p>
						<div class="flex items-center justify-between text-xs text-storm-500">
							<span>{scenario.agent_templates?.length || 0} agents</span>
							<span>{formatDate(scenario.created_at)}</span>
						</div>
					</a>
				{/each}
			</div>
		{/if}
	</section>

	<!-- Recent Runs Section -->
	<section>
		<h2 class="text-xl font-display font-semibold mb-4">Recent Runs</h2>

		{#if runList.length === 0}
			<div class="card text-center py-8">
				<p class="text-storm-400">No runs yet. Start a simulation from a scenario!</p>
			</div>
		{:else}
			<div class="card overflow-hidden p-0">
				<table class="w-full">
					<thead class="bg-storm-800/50">
						<tr class="text-left text-sm text-storm-400">
							<th class="px-4 py-3 font-medium">Run ID</th>
							<th class="px-4 py-3 font-medium">Status</th>
							<th class="px-4 py-3 font-medium">Progress</th>
							<th class="px-4 py-3 font-medium">Created</th>
							<th class="px-4 py-3 font-medium"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-storm-700/30">
						{#each runList.slice(0, 10) as run}
							<tr class="hover:bg-storm-800/30">
								<td class="px-4 py-3">
									<span class="font-mono text-sm text-storm-300">{run.id.slice(0, 8)}...</span>
								</td>
								<td class="px-4 py-3">
									<span class="badge {getStatusColor(run.status)} capitalize">{run.status}</span>
								</td>
								<td class="px-4 py-3">
									<div class="flex items-center gap-2">
										<div class="w-24 h-2 bg-storm-800 rounded-full overflow-hidden">
											<div
												class="h-full bg-flood-500 rounded-full transition-all"
												style="width: {(run.current_step / run.max_steps) * 100}%"
											></div>
										</div>
										<span class="text-xs text-storm-400 font-mono">
											{run.current_step}/{run.max_steps}
										</span>
									</div>
								</td>
								<td class="px-4 py-3 text-sm text-storm-400">
									{formatDate(run.created_at)}
								</td>
								<td class="px-4 py-3 text-right">
									<a href="/runs/{run.id}" class="text-flood-400 hover:text-flood-300 text-sm">
										View →
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
</div>

