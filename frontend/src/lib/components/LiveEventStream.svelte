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

	const EVENT_COLORS: Record<string, string> = {
		run_started:          'text-green-400',
		run_completed:        'text-green-300',
		run_stopped:          'text-amber-400',
		run_paused:           'text-amber-300',
		step_completed:       'text-blue-400',
		message:              'text-storm-300',
		agent_error:          'text-red-400',
		movement_failed:      'text-orange-400',
		proposal_created:     'text-purple-400',
		proposal_accepted:    'text-purple-300',
		proposal_rejected:    'text-red-300',
		counter_proposal:     'text-purple-200',
		conversation_outcome: 'text-teal-400',
		vouch_for:            'text-cyan-400',
		plan_shared:          'text-cyan-300',
		initialized:          'text-storm-400',
		resumed:              'text-storm-400',
		connected:            'text-storm-500',
		ping:                 'text-storm-600',
		pong:                 'text-storm-600',
	};

	function eventColor(type: string): string {
		return EVENT_COLORS[type] ?? 'text-storm-400';
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
		<h3 class="text-lg font-semibold font-display">Live Event Stream</h3>
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
		style="scrollbar-color: #2f30a9 transparent;"
		bind:this={container}
		on:scroll={onScroll}
	>
		{#if displayEvents.length === 0}
			<div class="text-center py-8 text-storm-500 font-sans text-sm">
				Waiting for simulation events&hellip;
			</div>
		{:else}
			{#each displayEvents as ev}
				<div class="flex items-start gap-2 py-0.5 px-1 hover:bg-storm-800/40 rounded">
					<span class="text-storm-600 shrink-0 w-20">{formatTime(ev.timestamp)}</span>
					<span class="shrink-0 w-36 {eventColor(ev.event)} font-semibold">{ev.event}</span>
					<span class="text-storm-300 truncate">{summarize(ev)}</span>
				</div>
			{/each}
		{/if}
	</div>
</div>
