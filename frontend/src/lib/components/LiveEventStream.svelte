<script lang="ts">
	import type { WebSocketEvent } from '$lib/stores/websocket';
	import { afterUpdate } from 'svelte';

	export let events: WebSocketEvent[] = [];

	let container: HTMLDivElement;
	let autoScroll = true;

	afterUpdate(() => {
		if (autoScroll && container) {
			container.scrollTop = container.scrollHeight;
		}
	});

	function onScroll() {
		if (!container) return;
		autoScroll = container.scrollHeight - container.scrollTop - container.clientHeight < 40;
	}

	// Colour carries meaning only: failures, run lifecycle, everything else quiet.
	const ERROR_EVENTS = new Set(['agent_error', 'movement_failed', 'proposal_rejected']);
	const LIFECYCLE_EVENTS = new Set(['run_started', 'run_completed', 'initialized', 'resumed']);

	function eventColor(type: string): string {
		if (ERROR_EVENTS.has(type)) return 'text-red-400';
		if (LIFECYCLE_EVENTS.has(type)) return 'text-flood-400';
		return 'text-storm-300';
	}

	function tick(index: number): string {
		return `t·${String(index + 1).padStart(3, '0')}`;
	}

	function formatTime(ts?: string): string {
		if (!ts) return '--:--:--';
		try {
			return new Date(ts).toLocaleTimeString(undefined, {
				hour: '2-digit', minute: '2-digit', second: '2-digit'
			});
		} catch {
			return '--:--:--';
		}
	}

	function summarize(ev: WebSocketEvent): string {
		const d = ev.data;
		switch (ev.event) {
			case 'step_completed':
				return `Step ${d.step ?? '?'} — ${(d.messages as unknown[])?.length ?? 0} msg(s)`;
			case 'run_started':
				return `Simulation started at step ${d.step ?? 0}`;
			case 'run_completed':
				return `Simulation complete (step ${d.step ?? '?'})`;
			case 'run_stopped':
				return `Stopped at step ${d.step ?? '?'}`;
			case 'run_paused':
				return `Paused at step ${d.step ?? '?'}`;
			case 'agent_error':
				return `Agent ${d.agent_id ?? '?'}: ${d.error ?? 'error'}`;
			case 'movement_failed':
				return `${d.agent_name ?? d.agent_id ?? '?'} movement failed`;
			case 'message':
				return `[${d.message_type ?? 'msg'}] ${String(d.content ?? '').slice(0, 80)}`;
			case 'proposal_created':
				return `Proposal ${String(d.proposal_id ?? '').slice(0, 8)} by ${d.from_agent ?? '?'}`;
			case 'proposal_accepted':
				return `Proposal accepted by ${d.agent_id ?? '?'}`;
			case 'proposal_rejected':
				return `Proposal rejected by ${d.agent_id ?? '?'}`;
			case 'conversation_outcome':
				return `Conversation ${String(d.conversation_id ?? '').slice(0, 8)}: ${d.outcome ?? '?'}`;
			case 'connected':
				return 'WebSocket connected';
			case 'initialized':
				return `Engine initialized — ${d.agent_count ?? '?'} agents`;
			default:
				return JSON.stringify(d).slice(0, 100);
		}
	}

	// Filter out noisy heartbeat events for display
	$: displayEvents = events.filter(e => e.event !== 'ping' && e.event !== 'pong');
</script>

<div class="card h-full flex flex-col">
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-lg font-medium">Live Event Stream</h3>
		<div class="flex items-center gap-3">
			{#if !autoScroll}
				<button
					class="text-xs text-flood-400 hover:text-flood-300 underline"
					on:click={() => { autoScroll = true; if (container) container.scrollTop = container.scrollHeight; }}
				>↓ latest</button>
			{/if}
			<span class="flex items-center gap-1.5 text-xs text-storm-400">
				<span class="inline-block w-1.5 h-1.5 rounded-full {displayEvents.length > 0 ? 'bg-green-500 animate-pulse' : 'bg-storm-600'}"></span>
				{displayEvents.length} events
			</span>
		</div>
	</div>

	<div
		class="flex-1 overflow-y-auto font-mono text-xs space-y-0.5 max-h-[400px] scrollbar-thin"
		style="scrollbar-color: #3a3d48 transparent;"
		bind:this={container}
		on:scroll={onScroll}
	>
		{#if displayEvents.length === 0}
			<div class="text-center py-8 text-storm-500 font-sans text-sm">
				Waiting for simulation events&hellip;
			</div>
		{:else}
			{#each displayEvents as ev, i}
				<div class="flex items-start gap-2 py-0.5 px-1 hover:bg-surface-alt/60 rounded">
					<span class="text-storm-500 shrink-0 w-12">{tick(i)}</span>
					<span class="text-storm-500 shrink-0 w-20">{formatTime(ev.timestamp)}</span>
					<span class="shrink-0 w-36 {eventColor(ev.event)}">{ev.event}</span>
					<span class="text-storm-300 truncate">{summarize(ev)}</span>
				</div>
			{/each}
		{/if}
	</div>
</div>
