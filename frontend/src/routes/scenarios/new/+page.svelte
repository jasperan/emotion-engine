<script lang="ts">
	import { goto } from '$app/navigation';
	import { scenarios, type AgentTemplate, type Persona } from '$lib/api';

	let name = '';
	let description = '';
	let maxSteps = 10;
	let tickDelay = 1.0;
	let agentTemplates: AgentTemplate[] = [];
	let saving = false;
	let error: string | null = null;

	// New agent form state
	let showAddAgent = false;
	let newAgent: Partial<AgentTemplate> = {
		role: 'human',
		model_id: 'phi3',
		provider: 'ollama'
	};
	let newPersona: Partial<Persona> = {
		age: 30,
		sex: 'non-binary',
		openness: 5,
		conscientiousness: 5,
		extraversion: 5,
		agreeableness: 5,
		neuroticism: 5,
		risk_tolerance: 5,
		empathy_level: 5,
		leadership: 5,
		stress_level: 3,
		health: 10,
		skills: [],
		inventory: [],
		location: 'shelter'
	};

	function addAgent() {
		if (!newAgent.name) return;

		const template: AgentTemplate = {
			name: newAgent.name!,
			role: newAgent.role as AgentTemplate['role'],
			model_id: newAgent.model_id || 'phi3',
			provider: newAgent.provider || 'ollama',
			goals: []
		};

		if (newAgent.role === 'human') {
			template.persona = {
				name: newAgent.name!,
				age: newPersona.age || 30,
				sex: newPersona.sex || 'non-binary',
				occupation: newPersona.occupation || 'Civilian',
				openness: newPersona.openness || 5,
				conscientiousness: newPersona.conscientiousness || 5,
				extraversion: newPersona.extraversion || 5,
				agreeableness: newPersona.agreeableness || 5,
				neuroticism: newPersona.neuroticism || 5,
				risk_tolerance: newPersona.risk_tolerance || 5,
				empathy_level: newPersona.empathy_level || 5,
				leadership: newPersona.leadership || 5,
				backstory: newPersona.backstory || '',
				skills: newPersona.skills || [],
				stress_level: newPersona.stress_level || 3,
				health: newPersona.health || 10,
				inventory: newPersona.inventory || [],
				location: newPersona.location || 'shelter'
			};
		}

		agentTemplates = [...agentTemplates, template];
		showAddAgent = false;
		resetNewAgent();
	}

	function resetNewAgent() {
		newAgent = { role: 'human', model_id: 'phi3', provider: 'ollama' };
		newPersona = {
			age: 30,
			sex: 'non-binary',
			openness: 5,
			conscientiousness: 5,
			extraversion: 5,
			agreeableness: 5,
			neuroticism: 5,
			risk_tolerance: 5,
			empathy_level: 5,
			leadership: 5,
			stress_level: 3,
			health: 10,
			skills: [],
			inventory: [],
			location: 'shelter'
		};
	}

	function removeAgent(index: number) {
		agentTemplates = agentTemplates.filter((_, i) => i !== index);
	}

	async function handleSubmit() {
		if (!name.trim()) {
			error = 'Name is required';
			return;
		}

		saving = true;
		error = null;

		try {
			const scenario = await scenarios.create({
				name,
				description,
				config: {
					name: 'World',
					description: 'Simulation world',
					initial_state: {
						hazard_level: 1,
						locations: {
							shelter: { description: 'Emergency shelter', nearby: ['street', 'rooftop'] },
							street: { description: 'Flooded street', nearby: ['shelter', 'bridge'] },
							rooftop: { description: 'Building rooftop', nearby: ['shelter'] },
							bridge: { description: 'Damaged bridge', nearby: ['street'] }
						}
					},
					dynamics: { intensity_growth: 0.1 },
					max_steps: maxSteps,
					tick_delay: tickDelay
				},
				agent_templates: agentTemplates
			});

			goto(`/scenarios/${scenario.id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create scenario';
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head>
	<title>Create Scenario | EmotionSim</title>
</svelte:head>

<div class="max-w-4xl mx-auto space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-display font-bold">Create New Scenario</h1>
		<a href="/" class="text-storm-400 hover:text-white text-sm">← Back to Dashboard</a>
	</div>

	{#if error}
		<div class="card border-red-500/30 bg-red-900/10">
			<p class="text-red-400">{error}</p>
		</div>
	{/if}

	<form on:submit|preventDefault={handleSubmit} class="space-y-6">
		<!-- Basic Info -->
		<div class="card">
			<h2 class="text-lg font-semibold font-display mb-4">Basic Information</h2>
			<div class="space-y-4">
				<div>
					<label for="name" class="label">Scenario Name</label>
					<input
						id="name"
						type="text"
						bind:value={name}
						class="input"
						placeholder="e.g., Rising Flood"
						required
					/>
				</div>
				<div>
					<label for="description" class="label">Description</label>
					<textarea
						id="description"
						bind:value={description}
						class="input h-24 resize-none"
						placeholder="Describe the scenario..."
					></textarea>
				</div>
				<div class="grid grid-cols-2 gap-4">
					<div>
						<label for="maxSteps" class="label">Max Steps</label>
						<input
							id="maxSteps"
							type="number"
							bind:value={maxSteps}
							class="input"
							min="10"
							max="1000"
						/>
					</div>
					<div>
						<label for="tickDelay" class="label">Tick Delay (seconds)</label>
						<input
							id="tickDelay"
							type="number"
							bind:value={tickDelay}
							class="input"
							min="0.1"
							max="10"
							step="0.1"
						/>
					</div>
				</div>
			</div>
		</div>

		<!-- Agents -->
		<div class="card">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-lg font-semibold font-display">Agents</h2>
				<button type="button" class="btn-secondary text-sm" on:click={() => (showAddAgent = true)}>
					+ Add Agent
				</button>
			</div>

			{#if agentTemplates.length === 0}
				<p class="text-storm-400 text-center py-8">No agents added yet.</p>
			{:else}
				<div class="space-y-3">
					{#each agentTemplates as agent, i}
						<div class="flex items-center gap-4 p-3 bg-storm-800/50 rounded-lg">
							<div class="flex-1">
								<div class="font-medium">{agent.name}</div>
							</div>
							{#if agent.persona}
								<div class="text-sm text-storm-300">
									{agent.persona.age}yo {agent.persona.occupation}
								</div>
							{/if}
							<button
								type="button"
								class="text-red-400 hover:text-red-300"
								on:click={() => removeAgent(i)}
							>
								✕
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Submit -->
		<div class="flex gap-4">
			<button type="submit" class="btn-primary flex-1" disabled={saving}>
				{saving ? 'Creating...' : 'Create Scenario'}
			</button>
			<a href="/" class="btn-secondary">Cancel</a>
		</div>
	</form>

	<!-- Add Agent Modal -->
	{#if showAddAgent}
		<div
			class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
		>
			<div class="card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
				<h3 class="text-xl font-display font-semibold mb-4">Add Agent</h3>

				<div class="space-y-4">
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label for="agent-name" class="label">Agent Name</label>
							<input
								id="agent-name"
								type="text"
								bind:value={newAgent.name}
								class="input"
								placeholder="e.g., Dr. Sarah Chen"
							/>
						</div>
						<div>
							<label for="agent-role" class="label">Role</label>
							<select id="agent-role" bind:value={newAgent.role} class="input">
								<option value="human">Human</option>
								<option value="environment">Environment</option>
								<option value="designer">Designer</option>
							</select>
						</div>
					</div>

					{#if newAgent.role === 'human'}
						<hr class="border-storm-700" />
						<h4 class="font-medium text-storm-300">Persona</h4>

						<div class="grid grid-cols-3 gap-4">
							<div>
								<label for="persona-age" class="label">Age</label>
								<input id="persona-age" type="number" bind:value={newPersona.age} class="input" min="1" max="120" />
							</div>
							<div>
								<label for="persona-sex" class="label">Sex</label>
								<select id="persona-sex" bind:value={newPersona.sex} class="input">
									<option value="male">Male</option>
									<option value="female">Female</option>
									<option value="non-binary">Non-binary</option>
								</select>
							</div>
							<div>
								<label for="persona-occupation" class="label">Occupation</label>
								<input
									id="persona-occupation"
									type="text"
									bind:value={newPersona.occupation}
									class="input"
									placeholder="e.g., Doctor"
								/>
							</div>
						</div>

						<div>
							<label for="persona-backstory" class="label">Backstory</label>
							<textarea
								id="persona-backstory"
								bind:value={newPersona.backstory}
								class="input h-20 resize-none"
								placeholder="Brief life history..."
							></textarea>
						</div>

						<h5 class="font-medium text-storm-300 text-sm mt-4">Personality Traits (1-10)</h5>
						<div class="grid grid-cols-2 gap-4">
							<div>
								<label for="trait-openness" class="label text-xs">Openness</label>
								<input
									id="trait-openness"
									type="range"
									bind:value={newPersona.openness}
									min="1"
									max="10"
									class="w-full"
								/>
								<span class="text-xs text-storm-400">{newPersona.openness}</span>
							</div>
							<div>
								<label for="trait-conscientiousness" class="label text-xs">Conscientiousness</label>
								<input
									id="trait-conscientiousness"
									type="range"
									bind:value={newPersona.conscientiousness}
									min="1"
									max="10"
									class="w-full"
								/>
								<span class="text-xs text-storm-400">{newPersona.conscientiousness}</span>
							</div>
							<div>
								<label for="trait-extraversion" class="label text-xs">Extraversion</label>
								<input
									id="trait-extraversion"
									type="range"
									bind:value={newPersona.extraversion}
									min="1"
									max="10"
									class="w-full"
								/>
								<span class="text-xs text-storm-400">{newPersona.extraversion}</span>
							</div>
							<div>
								<label for="trait-agreeableness" class="label text-xs">Agreeableness</label>
								<input
									id="trait-agreeableness"
									type="range"
									bind:value={newPersona.agreeableness}
									min="1"
									max="10"
									class="w-full"
								/>
								<span class="text-xs text-storm-400">{newPersona.agreeableness}</span>
							</div>
							<div>
								<label for="trait-neuroticism" class="label text-xs">Neuroticism</label>
								<input
									id="trait-neuroticism"
									type="range"
									bind:value={newPersona.neuroticism}
									min="1"
									max="10"
									class="w-full"
								/>
								<span class="text-xs text-storm-400">{newPersona.neuroticism}</span>
							</div>
							<div>
								<label for="trait-risk" class="label text-xs">Risk Tolerance</label>
								<input
									id="trait-risk"
									type="range"
									bind:value={newPersona.risk_tolerance}
									min="1"
									max="10"
									class="w-full"
								/>
								<span class="text-xs text-storm-400">{newPersona.risk_tolerance}</span>
							</div>
						</div>
					{/if}
				</div>

				<div class="flex gap-4 mt-6">
					<button type="button" class="btn-primary flex-1" on:click={addAgent}>Add Agent</button>
					<button
						type="button"
						class="btn-secondary"
						on:click={() => {
							showAddAgent = false;
							resetNewAgent();
						}}>Cancel</button
					>
				</div>
			</div>
		</div>
	{/if}
</div>

