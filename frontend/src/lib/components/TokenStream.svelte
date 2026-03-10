<script lang="ts">
	import type { WebSocketEvent } from '$lib/stores/websocket';
	import { afterUpdate } from 'svelte';

	export let events: WebSocketEvent[] = [];

	interface AgentStream {
		name: string;
		tokens: string;
		active: boolean;
		latencyMs: number | null;
		step: number;
		lastUpdate: number;
	}

	let streams: Record<string, AgentStream> = {};
	let container: HTMLDivElement;
	let autoScroll = true;
	let showCompleted = false;

	// Aggregate token throughput
	let totalTokens = 0;
	let startTime = 0;

	$: tokensPerSec = startTime > 0 ? (totalTokens / ((Date.now() - startTime) / 1000)).toFixed(1) : '0.0';

	// Process token_stream and token_done events
	$: {
		for (const ev of events) {
			if (ev.event === 'token_stream') {
				const { agent_id, agent_name, tokens, step } = ev.data as {
					agent_id: string;
					agent_name: string;
					tokens: string;
					step: number;
				};
				if (!streams[agent_id]) {
					streams[agent_id] = {
						name: agent_name,
						tokens: '',
						active: true,
						latencyMs: null,
						step,
						lastUpdate: Date.now(),
					};
				}
				const s = streams[agent_id];
				s.tokens += tokens;
				s.active = true;
				s.step = step;
				s.lastUpdate = Date.now();

				// Track throughput
				totalTokens += tokens.length;
				if (startTime === 0) startTime = Date.now();

				streams = streams; // trigger reactivity
			} else if (ev.event === 'token_done') {
				const { agent_id, agent_name, latency_ms } = ev.data as {
					agent_id: string;
					agent_name: string;
					latency_ms: number;
				};
				if (streams[agent_id]) {
					streams[agent_id].active = false;
					streams[agent_id].latencyMs = latency_ms;
				}
				streams = streams;
			} else if (ev.event === 'step_completed') {
				// Clear completed streams at step boundary
				for (const id of Object.keys(streams)) {
					if (!streams[id].active) {
						delete streams[id];
					}
				}
				streams = streams;
			}
		}
	}

	$: activeStreams = Object.entries(streams).filter(([, s]) => s.active);
	$: completedStreams = Object.entries(streams).filter(([, s]) => !s.active);
	$: activeCount = activeStreams.length;

	afterUpdate(() => {
		if (autoScroll && container) {
			container.scrollTop = container.scrollHeight;
		}
	});

	function onScroll() {
		if (!container) return;
		autoScroll = container.scrollHeight - container.scrollTop - container.clientHeight < 40;
	}

	function truncateTokens(text: string, maxLen: number = 500): string {
		if (text.length <= maxLen) return text;
		return '…' + text.slice(-maxLen);
	}
</script>

<div class="card h-full flex flex-col">
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-lg font-semibold font-display">Token Stream</h3>
		<div class="flex items-center gap-4">
			<span class="text-xs font-mono text-flood-400">{tokensPerSec} tok/s</span>
			<span class="flex items-center gap-1.5 text-xs text-storm-400">
				<span class="inline-block w-1.5 h-1.5 rounded-full {activeCount > 0 ? 'bg-green-500 animate-pulse' : 'bg-storm-600'}"></span>
				{activeCount} generating
			</span>
			{#if completedStreams.length > 0}
				<button
					class="text-xs text-storm-500 hover:text-storm-300"
					on:click={() => (showCompleted = !showCompleted)}
				>
					{showCompleted ? 'Hide' : 'Show'} done ({completedStreams.length})
				</button>
			{/if}
		</div>
	</div>

	<div
		class="flex-1 overflow-y-auto space-y-3 max-h-[500px] scrollbar-thin"
		style="scrollbar-color: #2f30a9 transparent;"
		bind:this={container}
		on:scroll={onScroll}
	>
		{#if activeStreams.length === 0 && completedStreams.length === 0}
			<div class="text-center py-8 text-storm-500 font-sans text-sm">
				Waiting for agent generations&hellip;
			</div>
		{/if}

		<!-- Active streams -->
		{#each activeStreams as [agentId, stream]}
			<div class="rounded-lg border border-flood-500/30 bg-storm-900/60 p-3">
				<div class="flex items-center justify-between mb-2">
					<div class="flex items-center gap-2">
						<span class="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
						<span class="text-sm font-semibold text-on-background">{stream.name}</span>
					</div>
					<span class="text-xs font-mono text-storm-400">step {stream.step}</span>
				</div>
				<div class="font-mono text-xs text-storm-200 whitespace-pre-wrap break-words leading-relaxed">
					{truncateTokens(stream.tokens)}<span class="inline-block w-1.5 h-4 bg-flood-400 animate-pulse ml-0.5 align-text-bottom"></span>
				</div>
			</div>
		{/each}

		<!-- Completed streams -->
		{#if showCompleted}
			{#each completedStreams as [agentId, stream]}
				<div class="rounded-lg border border-storm-700/50 bg-storm-900/30 p-3 opacity-70">
					<div class="flex items-center justify-between mb-2">
						<div class="flex items-center gap-2">
							<span class="inline-block w-2 h-2 rounded-full bg-storm-500"></span>
							<span class="text-sm font-semibold text-storm-300">{stream.name}</span>
						</div>
						<span class="text-xs font-mono text-storm-500">
							{stream.latencyMs ? `${(stream.latencyMs / 1000).toFixed(1)}s` : ''}
						</span>
					</div>
					<div class="font-mono text-xs text-storm-400 whitespace-pre-wrap break-words leading-relaxed max-h-24 overflow-hidden">
						{truncateTokens(stream.tokens, 200)}
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
