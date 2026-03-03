<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { runs, type Run } from '$lib/api';

	export let run: Run | null = null;

	const dispatch = createEventDispatcher();

	let controlling = false;
	let error: string | null = null;

	async function handleAction(action: 'start' | 'pause' | 'resume' | 'stop' | 'step') {
		if (!run) return;

		controlling = true;
		error = null;

		try {
			await runs.control(run.id, action);
			dispatch('action', { action });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Control action failed';
		} finally {
			controlling = false;
		}
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

<div class="card">
	<h3 class="text-lg font-semibold font-display mb-4">Simulation Controls</h3>

	{#if run}
		<!-- Status -->
		<div class="mb-4">
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm text-storm-400">Status</span>
				<span class="badge {getStatusColor(run.status)} capitalize">{run.status}</span>
			</div>
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm text-storm-400">Progress</span>
				<span class="text-sm text-storm-200 font-mono">
					{run.current_step}/{run.max_steps}
				</span>
			</div>
			<div class="w-full h-2 bg-storm-800 rounded-full overflow-hidden">
				<div
					class="h-full bg-flood-500 rounded-full transition-all"
					style="width: {(run.current_step / run.max_steps) * 100}%"
				></div>
			</div>
		</div>

		{#if error}
			<div class="mb-4 p-2 bg-red-900/20 border border-red-500/30 rounded text-sm text-red-400">
				{error}
			</div>
		{/if}

		<!-- Control Buttons -->
		<div class="space-y-2">
			{#if run.status === 'pending' || run.status === 'paused'}
				<button
					class="btn-primary w-full"
					disabled={controlling}
					on:click={() => handleAction(run.status === 'paused' ? 'resume' : 'start')}
				>
					{controlling ? '...' : run.status === 'paused' ? 'Resume' : 'Start'}
				</button>
			{/if}

			{#if run.status === 'running'}
				<div class="grid grid-cols-2 gap-2">
					<button
						class="btn-secondary"
						disabled={controlling}
						on:click={() => handleAction('pause')}
					>
						{controlling ? '...' : 'Pause'}
					</button>
					<button
						class="btn-secondary"
						disabled={controlling}
						on:click={() => handleAction('step')}
					>
						{controlling ? '...' : 'Step'}
					</button>
				</div>
				<button
					class="btn-danger w-full"
					disabled={controlling}
					on:click={() => handleAction('stop')}
				>
					{controlling ? '...' : 'Stop'}
				</button>
			{/if}

			{#if run.status === 'completed' || run.status === 'cancelled' || run.status === 'failed'}
				<p class="text-sm text-storm-400 text-center py-2">
					Simulation {run.status === 'completed' ? 'completed' : 'ended'}
				</p>
			{/if}
		</div>
	{:else}
		<p class="text-storm-400 text-sm">No run data available</p>
	{/if}
</div>

