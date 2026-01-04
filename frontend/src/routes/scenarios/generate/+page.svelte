<script lang="ts">
	import { goto } from '$app/navigation';
	import { scenarios, type GenerateResponse, type AgentTemplate } from '$lib/api';

	// Generation state
	let prompt = '';
	let personaCount = 6;
	let archetypes: string[] = [];
	let saveToFile = true;
	let generating = false;
	let error: string | null = null;

	// Preview state
	let previewData: GenerateResponse | null = null;
	let showPreview = false;
	let importing = false;

	// Available archetypes
	const availableArchetypes = [
		'doctor',
		'nurse',
		'firefighter',
		'police',
		'teacher',
		'child',
		'elderly',
		'leader',
		'student',
		'engineer',
		'soldier',
		'journalist',
		'parent',
		'scientist'
	];

	function toggleArchetype(archetype: string) {
		if (archetypes.includes(archetype)) {
			archetypes = archetypes.filter((a) => a !== archetype);
		} else {
			archetypes = [...archetypes, archetype];
		}
	}

	async function handleGenerate() {
		if (!prompt.trim()) {
			error = 'Please enter a scenario description';
			return;
		}

		generating = true;
		error = null;

		try {
			const result = await scenarios.generate({
				prompt: prompt.trim(),
				persona_count: personaCount,
				archetypes: archetypes.length > 0 ? archetypes : undefined,
				save_to_file: saveToFile
			});

			previewData = result;
			showPreview = true;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Generation failed';
		} finally {
			generating = false;
		}
	}

	async function handleImport() {
		if (!previewData?.filepath) {
			error = 'No file to import';
			return;
		}

		importing = true;
		error = null;

		try {
			// Extract filename from filepath
			const filename = previewData.filepath.split(/[/\\]/).pop();
			if (!filename) throw new Error('Invalid filepath');

			const scenario = await scenarios.importFile(filename);
			goto(`/scenarios/${scenario.id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Import failed';
		} finally {
			importing = false;
		}
	}

	function resetPreview() {
		showPreview = false;
		previewData = null;
	}

	function getPersonaStats(templates: AgentTemplate[]) {
		const humans = templates.filter((t) => t.role === 'human');
		const ages = humans.map((t) => t.persona?.age || 0).filter((a) => a > 0);
		const occupations = humans.map((t) => t.persona?.occupation || 'Unknown');

		return {
			count: humans.length,
			ageRange: ages.length > 0 ? `${Math.min(...ages)}-${Math.max(...ages)}` : 'N/A',
			occupations: [...new Set(occupations)].slice(0, 4)
		};
	}
</script>

<svelte:head>
	<title>Generate Scenario | EmotionSim</title>
</svelte:head>

<div class="max-w-4xl mx-auto space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-display font-bold">AI Scenario Generator</h1>
			<p class="text-storm-400 mt-1">Describe your scenario and let phi3 create it for you</p>
		</div>
		<a href="/" class="text-storm-400 hover:text-white text-sm">← Back to Dashboard</a>
	</div>

	{#if error}
		<div class="card border-red-500/30 bg-red-900/10">
			<p class="text-red-400">{error}</p>
		</div>
	{/if}

	{#if !showPreview}
		<!-- Generation Form -->
		<div class="card">
			<h2 class="text-lg font-semibold font-display mb-4 flex items-center gap-2">
				<span class="text-2xl">✨</span>
				Describe Your Scenario
			</h2>

			<div class="space-y-6">
				<!-- Prompt Input -->
				<div>
					<label for="prompt" class="label">Scenario Prompt</label>
					<textarea
						id="prompt"
						bind:value={prompt}
						class="input h-32 resize-none"
						placeholder="Describe your scenario in natural language...

Examples:
• Earthquake in Tokyo with rescue workers and trapped civilians
• Zombie outbreak in a shopping mall during Black Friday
• Hostage situation at a bank with negotiators and hostages
• Wildfire evacuation in a small mountain town"
					></textarea>
				</div>

				<!-- Persona Count -->
				<div>
					<label class="label">Number of Characters: {personaCount}</label>
					<input
						type="range"
						bind:value={personaCount}
						min="2"
						max="12"
						class="w-full h-2 bg-storm-700 rounded-lg appearance-none cursor-pointer accent-flood-500"
					/>
					<div class="flex justify-between text-xs text-storm-500 mt-1">
						<span>2 (minimal)</span>
						<span>12 (complex)</span>
					</div>
				</div>

				<!-- Archetypes -->
				<div>
					<label class="label">Character Types (optional)</label>
					<p class="text-sm text-storm-500 mb-2">
						Select specific types to include, or leave empty for AI to decide
					</p>
					<div class="flex flex-wrap gap-2">
						{#each availableArchetypes as archetype}
							<button
								type="button"
								class="px-3 py-1.5 rounded-full text-sm transition-all duration-200 {archetypes.includes(
									archetype
								)
									? 'bg-flood-500 text-white'
									: 'bg-storm-700 text-storm-300 hover:bg-storm-600'}"
								on:click={() => toggleArchetype(archetype)}
							>
								{archetype}
							</button>
						{/each}
					</div>
					{#if archetypes.length > 0}
						<p class="text-sm text-flood-400 mt-2">Selected: {archetypes.join(', ')}</p>
					{/if}
				</div>

				<!-- Save Option -->
				<div class="flex items-center gap-3">
					<input
						type="checkbox"
						id="saveToFile"
						bind:checked={saveToFile}
						class="w-4 h-4 rounded bg-storm-700 border-storm-600 text-flood-500 focus:ring-flood-500"
					/>
					<label for="saveToFile" class="text-storm-300">
						Save to JSON file (can be imported later)
					</label>
				</div>

				<!-- Generate Button -->
				<button
					type="button"
					class="btn-primary w-full py-3 text-lg flex items-center justify-center gap-2"
					disabled={generating || !prompt.trim()}
					on:click={handleGenerate}
				>
					{#if generating}
						<span class="animate-spin">⚙️</span>
						Generating with phi3...
					{:else}
						<span>🎲</span>
						Generate Scenario
					{/if}
				</button>
			</div>
		</div>

		<!-- Example Prompts -->
		<div class="card bg-storm-800/30">
			<h3 class="font-medium text-storm-300 mb-3">Quick Start Examples</h3>
			<div class="grid gap-2">
				{#each [
					'Earthquake aftermath in a densely populated city with emergency responders',
					'Stranded cruise ship with diverse passengers and limited resources',
					'Pandemic outbreak in a small isolated village',
					'Train derailment in a remote area with injured passengers'
				] as example}
					<button
						type="button"
						class="text-left p-3 rounded-lg bg-storm-800/50 hover:bg-storm-700/50 text-storm-300 text-sm transition-colors"
						on:click={() => (prompt = example)}
					>
						"{example}"
					</button>
				{/each}
			</div>
		</div>
	{:else if previewData}
		<!-- Preview Mode -->
		<div class="card border-flood-500/30">
			<div class="flex items-start justify-between mb-4">
				<div>
					<h2 class="text-xl font-semibold font-display">{previewData.scenario.name}</h2>
					<p class="text-storm-400 mt-1">{previewData.scenario.description}</p>
				</div>
				<span class="badge badge-success">Generated</span>
			</div>

			{#if previewData.filepath}
				<p class="text-sm text-storm-500 mb-4">
					Saved to: <code class="text-flood-400">{previewData.filepath}</code>
				</p>
			{/if}
		</div>

		<!-- World Config Preview -->
		<div class="card">
			<h3 class="font-semibold font-display mb-3">World Configuration</h3>
			{@const config = previewData.scenario.config as Record<string, unknown>}
			<div class="grid grid-cols-2 gap-4 text-sm">
				<div>
					<span class="text-storm-500">Name:</span>
					<span class="text-white ml-2">{config.name || 'Unknown'}</span>
				</div>
				<div>
					<span class="text-storm-500">Max Steps:</span>
					<span class="text-white ml-2">{config.max_steps || 50}</span>
				</div>
			</div>

			{#if config.initial_state && typeof config.initial_state === 'object'}
				{@const state = config.initial_state as Record<string, unknown>}
				{#if state.locations && typeof state.locations === 'object'}
					<div class="mt-4">
						<h4 class="text-sm font-medium text-storm-400 mb-2">Locations</h4>
						<div class="flex flex-wrap gap-2">
							{#each Object.keys(state.locations) as location}
								<span class="badge bg-storm-700 text-storm-200">{location}</span>
							{/each}
						</div>
					</div>
				{/if}
			{/if}
		</div>

		<!-- Personas Preview -->
		<div class="card">
			<h3 class="font-semibold font-display mb-3">Characters</h3>
			{@const stats = getPersonaStats(previewData.scenario.agent_templates)}
			<p class="text-sm text-storm-400 mb-4">
				{stats.count} personas, ages {stats.ageRange}
			</p>

			<div class="space-y-3 max-h-96 overflow-y-auto">
				{#each previewData.scenario.agent_templates as agent}
					<div class="p-3 bg-storm-800/50 rounded-lg">
						<div class="flex items-start justify-between">
							<div>
								<div class="font-medium text-white">{agent.name}</div>
								<div class="text-sm text-storm-400 capitalize">{agent.role}</div>
							</div>
							{#if agent.persona}
								<span class="text-sm text-storm-300">
									{agent.persona.age}yo {agent.persona.occupation}
								</span>
							{/if}
						</div>
						{#if agent.persona?.backstory}
							<p class="text-sm text-storm-500 mt-2 line-clamp-2">
								{agent.persona.backstory}
							</p>
						{/if}
						{#if agent.persona?.skills && agent.persona.skills.length > 0}
							<div class="flex flex-wrap gap-1 mt-2">
								{#each agent.persona.skills.slice(0, 4) as skill}
									<span class="text-xs px-2 py-0.5 bg-storm-700 rounded text-storm-300"
										>{skill}</span
									>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>

		<!-- Actions -->
		<div class="flex gap-4">
			<button
				type="button"
				class="btn-primary flex-1 py-3"
				disabled={importing}
				on:click={handleImport}
			>
				{#if importing}
					Importing...
				{:else}
					Import to Database & Run
				{/if}
			</button>
			<button type="button" class="btn-secondary" on:click={resetPreview}>
				Generate Another
			</button>
		</div>
	{/if}
</div>

<style>
	.line-clamp-2 {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
</style>

