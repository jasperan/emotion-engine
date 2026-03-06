// API client for EmotionSim backend

const API_BASE = '/api';

// Types
export interface Run {
	id: string;
	scenario_id: string;
	status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
	current_step: number;
	max_steps: number;
	seed: number | null;
	world_state: Record<string, unknown>;
	metrics: Record<string, unknown>;
	evaluation: Record<string, unknown>;
	created_at: string;
	started_at: string | null;
	completed_at: string | null;
}

export interface AgentPlan {
	goal: string;
	current_step: string;
	step_progress: string;
	deadline_step: number;
}

export interface Agent {
	id: string;
	name: string;
	role: string;
	model_id: string;
	provider: string;
	persona: Record<string, unknown> | null;
	dynamic_state: Record<string, unknown> | null;
	is_active: boolean;
	current_plan?: AgentPlan | null;
	last_reasoning?: string | null;
}

export interface Message {
	id: string;
	run_id: string;
	from_agent_id: string | null;
	to_target: string;
	message_type: string;
	content: string;
	metadata: Record<string, unknown>;
	step_index: number;
	timestamp: string;
}

export interface Scenario {
	id: string;
	name: string;
	description: string;
	config: Record<string, unknown>;
	agent_templates: AgentTemplate[];
	created_at: string;
	updated_at: string;
}

export interface AgentTemplate {
	name: string;
	role: 'human' | 'environment' | 'designer' | 'evaluator';
	model_id: string;
	provider: string;
	persona?: Persona;
	goals: string[];
}

export interface Persona {
	name: string;
	age: number;
	sex: string;
	occupation?: string;
	openness: number;
	conscientiousness: number;
	extraversion: number;
	agreeableness: number;
	neuroticism: number;
	risk_tolerance: number;
	empathy_level: number;
	leadership: number;
	backstory?: string;
	skills?: string[];
	stress_level: number;
	health: number;
	inventory?: string[];
	location?: string;
}

export interface GenerateResponse {
	id?: string;
	scenario: {
		name: string;
		description: string;
		config: Record<string, unknown>;
		agent_templates: AgentTemplate[];
	};
	filepath: string | null;
	message: string;
}

// Helper function for API calls
async function apiCall<T>(
	endpoint: string,
	options: RequestInit = {}
): Promise<T> {
	const response = await fetch(`${API_BASE}${endpoint}`, {
		headers: {
			'Content-Type': 'application/json',
			...options.headers,
		},
		...options,
	});

	if (!response.ok) {
		const error = await response.json().catch(() => ({ detail: response.statusText }));
		throw new Error(error.detail || `HTTP ${response.status}`);
	}

	return response.json();
}

// Runs API
export const runs = {
	list: async (scenarioId?: string): Promise<Run[]> => {
		const params = scenarioId ? `?scenario_id=${scenarioId}` : '';
		return apiCall<Run[]>(`/runs${params}`);
	},

	get: async (runId: string): Promise<Run> => {
		return apiCall<Run>(`/runs/${runId}`);
	},

	create: async (scenarioId: string, seed?: number, maxSteps?: number): Promise<Run> => {
		return apiCall<Run>('/runs/', {
			method: 'POST',
			body: JSON.stringify({
				scenario_id: scenarioId,
				seed,
				max_steps: maxSteps,
			}),
		});
	},

	control: async (runId: string, action: 'start' | 'pause' | 'resume' | 'stop' | 'step'): Promise<{ status: string; action: string; run_id: string }> => {
		return apiCall(`/runs/${runId}/control`, {
			method: 'POST',
			body: JSON.stringify({ action }),
		});
	},

	agents: async (runId: string): Promise<Agent[]> => {
		return apiCall<Agent[]>(`/runs/${runId}/agents`);
	},

	messages: async (runId: string, agentId?: string, skip = 0, limit = 200): Promise<Message[]> => {
		const params = new URLSearchParams({
			skip: skip.toString(),
			limit: limit.toString(),
		});
		if (agentId) params.append('agent_id', agentId);
		return apiCall<Message[]>(`/runs/${runId}/messages?${params}`);
	},
};

// Ollama API
export const ollama = {
	async models(): Promise<string[]> {
		try {
			const resp = await fetch('/api/ollama/models');
			if (!resp.ok) return ['qwen3.5:27b', 'qwen3.5:4b'];
			const data = await resp.json();
			return data.models || [];
		} catch {
			return ['qwen3.5:27b', 'qwen3.5:4b'];
		}
	}
};

// Scenarios API
export const scenarios = {
	list: async (): Promise<Scenario[]> => {
		return apiCall<Scenario[]>('/scenarios/');
	},

	get: async (scenarioId: string): Promise<Scenario> => {
		return apiCall<Scenario>(`/scenarios/${scenarioId}`);
	},

	create: async (data: {
		name: string;
		description: string;
		config: Record<string, unknown>;
		agent_templates: AgentTemplate[];
	}): Promise<Scenario> => {
		return apiCall<Scenario>('/scenarios/', {
			method: 'POST',
			body: JSON.stringify(data),
		});
	},

	update: async (scenarioId: string, data: {
		name?: string;
		description?: string;
		config?: Record<string, unknown>;
		agent_templates?: AgentTemplate[];
	}): Promise<Scenario> => {
		return apiCall<Scenario>(`/scenarios/${scenarioId}`, {
			method: 'PUT',
			body: JSON.stringify(data),
		});
	},

	delete: async (scenarioId: string): Promise<{ status: string; id: string }> => {
		return apiCall(`/scenarios/${scenarioId}`, {
			method: 'DELETE',
		});
	},

	generate: async (data: {
		prompt: string;
		persona_count?: number;
		archetypes?: string[];
		save_to_file?: boolean;
	}): Promise<GenerateResponse> => {
		return apiCall<GenerateResponse>('/scenarios/generate', {
			method: 'POST',
			body: JSON.stringify(data),
		});
	},

	importFile: async (filename: string): Promise<Scenario> => {
		return apiCall<Scenario>(`/scenarios/files/${filename}/import`, {
			method: 'POST',
		});
	},
};

