<script lang="ts">
	import type { Agent } from '$lib/api';

	export let agent: Agent;
</script>

<div class="card">
	<div class="flex items-start justify-between mb-2">
		<div>
			<h4 class="font-semibold text-storm-100">{agent.name}</h4>
		</div>
		{#if agent.is_active}
			<span class="badge badge-success text-xs">Active</span>
		{:else}
			<span class="badge badge-warning text-xs">Inactive</span>
		{/if}
	</div>

	{#if agent.persona}
		<div class="space-y-2 text-sm mt-3">
			{#if agent.persona.occupation}
				<div class="flex justify-between">
					<span class="text-storm-400">Occupation</span>
					<span class="text-storm-200">{agent.persona.occupation}</span>
				</div>
			{/if}
			{#if agent.persona.age}
				<div class="flex justify-between">
					<span class="text-storm-400">Age</span>
					<span class="text-storm-200">{agent.persona.age}</span>
				</div>
			{/if}
		</div>
	{/if}

	{#if agent.dynamic_state}
		<div class="mt-3 pt-3 border-t border-storm-700/30 space-y-2 text-sm">
			{#if agent.dynamic_state.health !== undefined}
				<div class="flex justify-between items-center">
					<span class="text-storm-400">Health</span>
					<div class="flex items-center gap-2">
						<div class="w-16 h-2 bg-storm-800 rounded-full overflow-hidden">
							<div
								class="h-full bg-gradient-to-r from-green-500 to-red-500 rounded-full transition-all"
								style="width: {((Number(agent.dynamic_state.health) || 0) / 10) * 100}%"
							></div>
						</div>
						<span class="text-storm-200 text-xs font-mono">
							{agent.dynamic_state.health}/10
						</span>
					</div>
				</div>
			{/if}
			{#if agent.dynamic_state.stress_level !== undefined}
				<div class="flex justify-between items-center">
					<span class="text-storm-400">Stress</span>
					<div class="flex items-center gap-2">
						<div class="w-16 h-2 bg-storm-800 rounded-full overflow-hidden">
							<div
								class="h-full bg-gradient-to-r from-yellow-500 to-red-500 rounded-full transition-all"
								style="width: {((Number(agent.dynamic_state.stress_level) || 0) / 10) * 100}%"
							></div>
						</div>
						<span class="text-storm-200 text-xs font-mono">
							{agent.dynamic_state.stress_level}/10
						</span>
					</div>
				</div>
			{/if}
			{#if agent.dynamic_state.location}
				<div class="flex justify-between">
					<span class="text-storm-400">Location</span>
					<span class="text-storm-200 text-xs">{agent.dynamic_state.location}</span>
				</div>
			{/if}
		</div>
	{/if}
</div>

