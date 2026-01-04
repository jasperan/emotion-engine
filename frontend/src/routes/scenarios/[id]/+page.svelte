<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { scenarios, runs, type Scenario, type Run } from '$lib/api';
	import { setHeader, resetHeader } from '$lib/stores/header';

	let scenario: Scenario | null = null;
	let runList: Run[] = [];
	let loading = true;
	let error: string | null = null;
	let creating = false;

	$: scenarioId = $page.params.id as string;

	onMount(async () => {
		try {
			[scenario, runList] = await Promise.all([
				scenarios.get(scenarioId),
				runs.list(scenarioId)
			]);

			if (scenario) {
				setHeader({
					title: 'Scenario Detail',
					breadcrumb: [
						{ label: 'Library', href: '/library' }
					],
					actions: [
						{ label: '▶ Start Run', primary: true, onclick: createRun }
					]
				});
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load scenario';
		} finally {
			loading = false;
		}

		return resetHeader;
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
<div class="space-y-8 max-w-7xl mx-auto">
	<!-- Header Area -->
	<div class="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-outline/20 pb-6">
		<div>
			<h1 class="text-4xl font-display font-bold tracking-tight text-on-background">{scenario.name}</h1>
			{#if scenario.description}
				<p class="text-on-surface mt-2 max-w-3xl text-lg leading-relaxed">{scenario.description}</p>
			{/if}
		</div>
		<div class="flex gap-3">
			<button class="btn btn-secondary text-sm" on:click={() => { /* Edit logic */ }}>Edit</button>
			<button class="btn bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white border border-red-500/20 text-sm" on:click={deleteScenario}>Delete</button>
		</div>
	</div>

	<!-- Main Content Grid -->
	<div class="grid lg:grid-cols-4 gap-8">
		<!-- Sidebar Grid: Configuration -->
		<div class="lg:col-span-1 space-y-6">
			<div class="card p-4 bg-surface-alt/30 border-outline/10">
				<h2 class="text-xs font-bold uppercase tracking-wider text-on-surface/60 mb-4">Configuration</h2>
				<div class="space-y-3">
					<div class="flex flex-col">
						<span class="text-[10px] uppercase text-on-surface/40 font-bold">Max Steps</span>
						<span class="text-sm font-mono text-primary">{scenario.config.max_steps || 100}</span>
					</div>
					<div class="flex flex-col">
						<span class="text-[10px] uppercase text-on-surface/40 font-bold">Tick Delay</span>
						<span class="text-sm font-mono text-primary">{scenario.config.tick_delay || 0.5}s</span>
					</div>
					<div class="flex flex-col">
						<span class="text-[10px] uppercase text-on-surface/40 font-bold">Created</span>
						<span class="text-sm text-on-surface/80">{formatDate(scenario.created_at)}</span>
					</div>
				</div>
			</div>
		</div>

		<!-- Main Grid Area -->
		<div class="lg:col-span-3 space-y-8">
			<!-- Agent Templates -->
			<section>
				<h2 class="text-xl font-display font-semibold mb-4 flex items-center gap-2">
					Agent Templates
					<span class="text-sm font-normal text-on-surface/50 font-mono">({scenario.agent_templates?.length || 0})</span>
				</h2>
				
				{#if scenario.agent_templates?.length > 0}
					<div class="grid sm:grid-cols-2 gap-4">
						{#each scenario.agent_templates as agent}
							<div class="group relative p-4 bg-surface border border-outline/30 rounded-xl hover:border-primary/50 transition-all duration-300">
								<div class="flex items-start justify-between mb-2">
									<h3 class="font-bold text-on-background group-hover:text-primary transition-colors">{agent.name}</h3>
								</div>
								
								{#if agent.persona}
									<p class="text-sm text-on-surface leading-snug mb-3">
										{agent.persona.age} year old {agent.persona.occupation}
									</p>
									<div class="flex items-center gap-2 flex-wrap">
										<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-alt border border-outline/20 text-on-surface/70">
											{agent.model_id.split('/').pop()}
										</span>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{:else}
					<div class="p-8 text-center border-2 border-dashed border-outline/20 rounded-2xl">
						<p class="text-on-surface/50">No agents configured for this scenario.</p>
					</div>
				{/if}
			</section>

			<!-- Runs -->
			<section>
				<h2 class="text-xl font-display font-semibold mb-4">Past Simulation Runs</h2>
				
				{#if runList.length === 0}
					<div class="p-12 text-center bg-surface-alt/10 border border-outline/10 rounded-2xl">
						<p class="text-on-surface/50 mb-4 font-body">No simulations have been run yet.</p>
						<button class="btn btn-primary" on:click={createRun} disabled={creating}>
							Start Your First Run
						</button>
					</div>
				{:else}
					<div class="overflow-hidden border border-outline/20 rounded-xl">
						<table class="w-full text-left">
							<thead class="bg-surface-alt/50 border-b border-outline/20">
								<tr>
									<th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-on-surface/60">Run ID</th>
									<th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-on-surface/60">Status</th>
									<th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-on-surface/60">Progress</th>
									<th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-on-surface/60">Started</th>
									<th class="px-6 py-4"></th>
								</tr>
							</thead>
							<tbody class="divide-y divide-outline/10 bg-surface/30">
								{#each runList as run}
									<tr class="hover:bg-primary/5 transition-colors group">
										<td class="px-6 py-4">
											<span class="font-mono text-sm text-on-surface/80">#{run.id.slice(0, 8)}</span>
										</td>
										<td class="px-6 py-4 text-sm">
											<span class="badge {getStatusColor(run.status)}">
												{run.status}
											</span>
										</td>
										<td class="px-6 py-4">
											<div class="flex items-center gap-3">
												<div class="w-24 h-1.5 bg-outline/20 rounded-full overflow-hidden">
													<div 
														class="h-full bg-primary transition-all duration-500"
														style="width: {(run.current_step / run.max_steps) * 100}%"
													></div>
												</div>
												<span class="text-[10px] font-mono text-on-surface/60">
													{run.current_step}/{run.max_steps}
												</span>
											</div>
										</td>
										<td class="px-6 py-4 text-sm text-on-surface/60">{formatDate(run.created_at)}</td>
										<td class="px-6 py-4 text-right">
											<a href="/runs/{run.id}" class="text-primary hover:text-accent-blue font-medium transition-colors">
												View Results
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
	</div>
</div>
{/if}

