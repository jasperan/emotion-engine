<script lang="ts">
	import type { Message, Agent } from '$lib/api';

	export let messages: Message[] = [];
	export let agents: Agent[] = [];

	const WINDOW_SIZE = 50;
	let showAll = false;

	$: visibleMessages = showAll ? messages : messages.slice(-WINDOW_SIZE);
	$: hasMore = messages.length > WINDOW_SIZE && !showAll;

	function getAgentName(agentId: string | null): string {
		if (!agentId) return 'System';
		const agent = agents.find((a) => a.id === agentId);
		return agent?.name || 'Unknown';
	}

	function formatTimestamp(timestamp: string | Date): string {
		const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
		return date.toLocaleTimeString(undefined, {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});
	}

	function getMessageTypeColor(type: string): string {
		switch (type) {
			case 'direct':
				return 'border-l-blue-500 bg-blue-500/5';
			case 'broadcast':
				return 'border-l-green-500 bg-green-500/5';
			case 'room':
				return 'border-l-purple-500 bg-purple-500/5';
			case 'action':
				return 'border-l-amber-500 bg-amber-500/5';
			default:
				return 'border-l-storm-600 bg-storm-800/30';
		}
	}

	function getMessageTypeLabel(type: string): string {
		switch (type) {
			case 'direct': return 'Direct';
			case 'broadcast': return 'Broadcast';
			case 'room': return 'Room';
			case 'action': return 'Action';
			default: return type;
		}
	}
</script>

<div class="card h-full flex flex-col">
	<div class="flex items-center justify-between mb-4">
		<h3 class="text-lg font-semibold font-display">Message Log</h3>
		<span class="text-xs text-storm-400">{messages.length} messages</span>
	</div>

	<div class="flex-1 overflow-y-auto space-y-3 max-h-[600px] scrollbar-thin" style="scrollbar-color: #2f30a9 transparent;">
		{#if messages.length === 0}
			<div class="text-center py-12 text-storm-400">
				<p>No messages yet. Start the simulation to see agent interactions.</p>
			</div>
		{:else}
			{#if hasMore}
				<button
					class="w-full text-center py-2.5 text-sm text-flood-400 hover:text-flood-300 bg-surface hover:bg-surface_alt rounded-lg border border-outline/30 hover:border-flood-500/30 transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
					on:click={() => (showAll = true)}
				>
					Load earlier ({messages.length - WINDOW_SIZE} more)
				</button>
			{/if}
			{#each visibleMessages as message}
				<div class="message-item border-l-3 {getMessageTypeColor(message.message_type)} p-3 rounded-r-lg transition-all duration-200">
					<div class="flex items-start justify-between mb-1">
						<div class="flex items-center gap-2">
							<span class="font-semibold text-storm-100">
								{getAgentName(message.from_agent_id)}
							</span>
							{#if message.to_target && message.to_target !== 'broadcast'}
								<span class="text-storm-500">→</span>
								<span class="text-storm-400 text-sm">
									{message.to_target === 'room' ? 'Room' : getAgentName(message.to_target)}
								</span>
							{/if}
							<span class="badge badge-info text-xs capitalize">{getMessageTypeLabel(message.message_type)}</span>
						</div>
						<div class="flex items-center gap-2 text-xs text-storm-500">
							<span>Step {message.step_index}</span>
							<span>•</span>
							<span>{formatTimestamp(message.timestamp)}</span>
						</div>
					</div>
					<p class="text-storm-200 text-sm whitespace-pre-wrap">{message.content}</p>
					{#if message.metadata && Object.keys(message.metadata).length > 0}
						<details class="mt-2">
							<summary class="text-xs text-storm-400 cursor-pointer hover:text-storm-300 transition-colors duration-150">
								Metadata
							</summary>
							<pre class="mt-1 text-xs text-storm-400 overflow-x-auto">{JSON.stringify(message.metadata, null, 2)}</pre>
						</details>
					{/if}
				</div>
			{/each}
		{/if}
	</div>
</div>

<style>
	.border-l-3 {
		border-left-width: 3px;
	}

	@media (prefers-reduced-motion: no-preference) {
		.message-item {
			animation: messageFadeIn 0.25s ease-out;
		}
	}

	@keyframes messageFadeIn {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>

