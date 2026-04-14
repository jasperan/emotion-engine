<script lang="ts">
	import { onMount } from 'svelte';
	import { scenarios, runs, type Scenario, type Run } from '$lib/api';
	import { setHeader, resetHeader } from '$lib/stores/header';

	let scenarioList: Scenario[] = [];
	let runList: Run[] = [];
	let loading = true;
	let error: string | null = null;

	onMount(() => {
		setHeader({ title: 'Library' });

		async function loadData() {
			try {
				[scenarioList, runList] = await Promise.all([scenarios.list(), runs.list()]);
			} catch (e) {
				error = e instanceof Error ? e.message : 'Failed to load data';
			} finally {
				loading = false;
			}
		}

		loadData();
		return () => resetHeader();
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
	<div class="card bg-surface/50 border-outline/15">
		<div class="flex items-center gap-5">
			<div
				class="w-14 h-14 rounded-xl flex items-center justify-center shadow-sm flex-shrink-0"
				style="background: linear-gradient(135deg, #5cd4c4, #8fb4e0);"
			>
				<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/></svg>
			</div>
			<div>
				<h1 class="text-2xl font-display font-bold tracking-tight mb-1">Emotion Engine</h1>
				<p class="text-on-surface/60 text-sm max-w-xl leading-relaxed">
					Run AI agent swarms in parallel disaster simulations. Create scenarios, watch agents cooperate and make decisions.
				</p>
			</div>
		</div>
	</div>

	<!-- Scenarios Section -->
	<section>
		<div class="flex items-center justify-between mb-5">
			<h2 class="text-lg font-display font-semibold tracking-tight">Scenarios</h2>
			<a href="/scenarios/new" class="btn btn-primary text-[13px] px-3.5 py-2">Create scenario</a>
		</div>

		{#if loading}
			<div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each Array(3) as _}
					<div class="card space-y-3">
						<div class="skeleton h-5 w-3/4"></div>
						<div class="skeleton h-4 w-full"></div>
						<div class="skeleton h-4 w-1/2"></div>
						<div class="flex justify-between mt-4">
							<div class="skeleton h-3 w-16"></div>
							<div class="skeleton h-3 w-20"></div>
						</div>
					</div>
				{/each}
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
						class="card-interactive block"
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
		<h2 class="text-lg font-display font-semibold tracking-tight mb-5">Recent runs</h2>

		{#if runList.length === 0}
			<div class="card text-center py-8">
				<p class="text-storm-400">No runs yet. Start a simulation from a scenario!</p>
			</div>
		{:else}
			<div class="card overflow-hidden p-0 border-outline/15">
				<table class="w-full">
					<thead class="bg-surface/50">
						<tr class="text-left text-xs text-on-surface/50">
							<th class="px-5 py-3 font-medium tracking-wide">Run ID</th>
							<th class="px-5 py-3 font-medium tracking-wide">Status</th>
							<th class="px-5 py-3 font-medium tracking-wide">Progress</th>
							<th class="px-5 py-3 font-medium tracking-wide">Created</th>
							<th class="px-5 py-3 font-medium"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-outline/10">
						{#each runList.slice(0, 10) as run}
							<tr class="hover:bg-storm-800/30 cursor-pointer transition-colors" on:click={() => window.location.href = `/runs/${run.id}`}>
								<td class="px-4 py-3">
									<span class="font-mono text-sm text-storm-300">{run.id.slice(0, 8)}...</span>
								</td>
								<td class="px-4 py-3">
									<span class="badge {getStatusColor(run.status)} capitalize">{run.status}</span>
								</td>
								<td class="px-4 py-3">
									<div class="flex items-center gap-2">
										<div
											class="w-24 h-2 bg-storm-800 rounded-full overflow-hidden"
											role="progressbar"
											aria-label="Simulation progress"
											aria-valuenow={Math.round((run.current_step / run.max_steps) * 100)}
											aria-valuemin="0"
											aria-valuemax="100"
										>
											<div
												class="h-full bg-flood-500 rounded-full transition-all"
												style="width: {(run.current_step / run.max_steps) * 100}%"
											></div>
										</div>
										<span class="text-xs text-storm-400 font-mono" aria-hidden="true">
											{run.current_step}/{run.max_steps}
										</span>
									</div>
								</td>
								<td class="px-4 py-3 text-sm text-storm-400">
									{formatDate(run.created_at)}
								</td>
								<td class="px-4 py-3 text-right">
									<a
										href="/runs/{run.id}"
										class="text-flood-400 hover:text-flood-300 text-sm"
										aria-label="View run {run.id}"
									>
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
