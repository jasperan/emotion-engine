<script>
	import '../app.css';
</script>

<div class="min-h-screen flex flex-col">
	<header class="border-b border-storm-700/30 bg-storm-900/50 backdrop-blur-sm sticky top-0 z-50">
		<nav class="container mx-auto px-6 py-4">
			<div class="flex items-center justify-between">
				<a href="/" class="flex items-center gap-3 group">
					<div
						class="w-10 h-10 bg-gradient-to-br from-flood-400 to-storm-500 rounded-lg flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform"
					>
						<span class="text-xl">🌊</span>
					</div>
					<div>
						<h1 class="text-xl font-display font-bold text-white">EmotionSim</h1>
						<p class="text-xs text-storm-400">Multi-Agent Simulation</p>
					</div>
				</a>

				<div class="flex items-center gap-4">
					<a href="/" class="text-storm-300 hover:text-white transition-colors">Dashboard</a>
					<a href="/scenarios/generate" class="text-storm-300 hover:text-white transition-colors flex items-center gap-1">
						<span>✨</span> Generate
					</a>
					<a href="/scenarios/new" class="btn-primary">New Scenario</a>
				</div>
			</div>
		</nav>
	</header>

	<main class="flex-1 container mx-auto px-6 py-8">
		<slot />
	</main>

	<footer class="border-t border-storm-700/30 py-6 text-center text-sm text-storm-500">
		EmotionSim v0.1.0 — Inspired by The Great Flood
	</footer>
</div>

