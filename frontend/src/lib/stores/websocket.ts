import { writable } from 'svelte/store';

interface WebSocketEvent {
	event: string;
	data: Record<string, unknown>;
	timestamp?: string;
}

interface WebSocketState {
	connected: boolean;
	lastEvent: WebSocketEvent | null;
}

function createWebSocketStore() {
	const { subscribe, set, update } = writable<WebSocketState>({
		connected: false,
		lastEvent: null,
	});

	let ws: WebSocket | null = null;
	let currentRunId: string | null = null;
	let reconnectTimeout: NodeJS.Timeout | null = null;
	let reconnectDelay = 1000;
	const MAX_RECONNECT_DELAY = 30000;

	function connect(runId: string) {
		// Disconnect existing connection if any
		if (ws) {
			disconnect();
		}

		currentRunId = runId;
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		const host = window.location.host;
		const wsUrl = `${protocol}//${host}/api/ws/${runId}`;

		try {
			ws = new WebSocket(wsUrl);

			ws.onopen = () => {
				reconnectDelay = 1000;
				update((state) => ({
					...state,
					connected: true,
				}));
			};

			ws.onmessage = (event) => {
				try {
					const message: WebSocketEvent = JSON.parse(event.data);
					update((state) => ({
						...state,
						lastEvent: message,
					}));
				} catch (e) {
					console.error('Failed to parse WebSocket message:', e);
				}
			};

			ws.onerror = (error) => {
				console.error('WebSocket error:', error);
			};

			ws.onclose = () => {
				update((state) => ({
					...state,
					connected: false,
				}));

				// Attempt to reconnect with exponential backoff if we still have a runId
				if (currentRunId) {
					reconnectTimeout = setTimeout(() => {
						if (currentRunId) {
							connect(currentRunId);
						}
					}, reconnectDelay);
					reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
				}
			};
		} catch (error) {
			console.error('Failed to create WebSocket connection:', error);
			update((state) => ({
				...state,
				connected: false,
			}));
		}
	}

	function disconnect() {
		currentRunId = null;
		reconnectDelay = 1000;

		if (reconnectTimeout) {
			clearTimeout(reconnectTimeout);
			reconnectTimeout = null;
		}

		if (ws) {
			ws.close();
			ws = null;
		}

		update((state) => ({
			...state,
			connected: false,
			lastEvent: null,
		}));
	}

	return {
		subscribe,
		connect,
		disconnect,
	};
}

export const websocket = createWebSocketStore();

