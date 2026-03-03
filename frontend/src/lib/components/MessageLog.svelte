<script lang="ts">
	import type { Message, Agent } from '$lib/api';

	export let messages: Message[] = [];
	export let agents: Agent[] = [];

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
				return 'border-flood-500/30 bg-flood-500/10';
			case 'broadcast':
				return 'border-storm-500/30 bg-storm-800/50';
			case 'room':
				return 'border-yellow-500/30 bg-yellow-500/10';
			case 'action':
				return 'border-purple-500/30 bg-purple-500/10';
			default:
				return 'border-storm-700/30 bg-storm-800/30';
		}
	}
</script>

<div class="card h-full flex flex-col">
	<div class="flex items-center justify-between mb-4">
		<h3 class="text-lg font-semibold font-display">Message Log</h3>
		<span class="text-xs text-storm-400">{messages.length} messages</span>
	</div>

	<div class="flex-1 overflow-y-auto space-y-3 max-h-[600px]">
		{#if messages.length === 0}
			<div class="text-center py-12 text-storm-400">
				<p>No messages yet. Start the simulation to see agent interactions.</p>
			</div>
		{:else}
			{#each messages as message}
				<div class="border-l-2 {getMessageTypeColor(message.message_type)} p-3 rounded-r-lg">
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
							<span class="badge badge-info text-xs capitalize">{message.message_type}</span>
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
							<summary class="text-xs text-storm-400 cursor-pointer hover:text-storm-300">
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

