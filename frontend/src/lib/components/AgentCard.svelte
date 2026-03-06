<script lang="ts">
	import type { Agent } from '$lib/api';

	export let agent: Agent;

	// Big Five trait labels
	const traitLabels: Record<string, string> = {
		openness: 'Open',
		conscientiousness: 'Conscientious',
		extraversion: 'Extraverted',
		agreeableness: 'Agreeable',
		neuroticism: 'Neurotic',
		risk_tolerance: 'Risk-taker',
		empathy_level: 'Empathetic',
		leadership: 'Leader'
	};

	// Get top personality traits (highest values)
	function getTopTraits(persona: Record<string, unknown> | null, count = 3): { name: string; value: number }[] {
		if (!persona) return [];
		const traitKeys = Object.keys(traitLabels);
		const traits = traitKeys
			.filter((k) => typeof persona[k] === 'number')
			.map((k) => ({ name: traitLabels[k], value: Number(persona[k]) }))
			.sort((a, b) => b.value - a.value);
		return traits.slice(0, count);
	}

	function truncate(text: string, maxLen = 120): string {
		if (text.length <= maxLen) return text;
		return text.slice(0, maxLen) + '...';
	}

	$: topTraits = getTopTraits(agent.persona);
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

	{#if agent.current_plan}
		<div class="mt-3 pt-3 border-t border-storm-700/30 space-y-1.5">
			<div class="flex items-center gap-1.5 mb-1">
				<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-flood-400"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
				<span class="text-xs font-semibold text-flood-400 uppercase tracking-wide">Current Plan</span>
			</div>
			<p class="text-sm text-storm-200">{agent.current_plan.goal}</p>
			<div class="flex items-center justify-between text-xs">
				<span class="text-storm-400">{agent.current_plan.step_progress}</span>
				<span class="text-storm-500">deadline: step {agent.current_plan.deadline_step}</span>
			</div>
			<p class="text-xs text-storm-300">{agent.current_plan.current_step}</p>
		</div>
	{/if}

	{#if agent.last_reasoning}
		<div class="mt-3 pt-3 border-t border-storm-700/30">
			<span class="text-xs font-semibold text-storm-400 uppercase tracking-wide">Last Reasoning</span>
			<p class="text-xs text-storm-300 italic mt-1">{truncate(agent.last_reasoning)}</p>
		</div>
	{/if}

	{#if topTraits.length > 0}
		<div class="mt-3 pt-3 border-t border-storm-700/30 flex flex-wrap gap-1.5">
			{#each topTraits as trait}
				<span class="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 font-medium">
					{trait.name}
				</span>
			{/each}
		</div>
	{/if}
</div>

