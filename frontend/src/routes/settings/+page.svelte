<script lang="ts">
  import { onMount } from 'svelte';
  import { setHeader, resetHeader } from '$lib/stores/header';

  onMount(() => {
    setHeader({ title: 'Settings' });
    return resetHeader;
  });
</script>

<div class="max-w-4xl mx-auto space-y-8">
    <div class="border-b border-outline/20 pb-6">
        <h1 class="text-3xl font-display font-bold text-on-background">Settings</h1>
        <p class="text-on-surface mt-2">Manage your simulation environment and API configurations.</p>
    </div>

    <div class="grid gap-8">
        <!-- LLM Configuration -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-6 flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l2 2m-2-2l-2-2"/></svg>
                LLM Configuration
            </h2>
            <div class="space-y-6">
                <div class="space-y-2">
                    <label for="ollama-url" class="text-sm font-medium text-on-surface">Ollama Base URL</label>
                    <div class="flex gap-2">
                        <input type="text" id="ollama-url" placeholder="http://localhost:11434/v1" class="input flex-1" value="http://localhost:11434/v1" />
                        <button class="btn btn-secondary">Save</button>
                    </div>
                    <p class="text-[10px] text-on-surface/50">The endpoint for your Ollama instance (OpenAI-compatible).</p>
                </div>

                <div class="space-y-2">
                    <label for="default-model" class="text-sm font-medium text-on-surface">Default Model</label>
                    <div class="flex gap-2">
                        <input type="text" id="default-model" placeholder="qwen2.5:7b" class="input flex-1" value="qwen2.5:7b" />
                        <button class="btn btn-secondary">Save</button>
                    </div>
                    <p class="text-[10px] text-on-surface/50">The model to use for simulations by default.</p>
                </div>
            </div>
        </section>

        <!-- UI Preferences -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-6 flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                Interface Preferences
            </h2>
            <div class="space-y-4">
                <div class="flex items-center justify-between p-3 bg-surface-alt/20 rounded-lg">
                    <div>
                        <span class="block font-medium">Auto-scroll Message Log</span>
                        <span class="text-xs text-on-surface/60">Automatically scroll to the latest message during simulations.</span>
                    </div>
                    <button class="w-12 h-6 rounded-full bg-primary/20 border border-primary/30 relative shadow-inner">
                        <div class="absolute right-1 top-1 w-4 h-4 rounded-full bg-primary"></div>
                    </button>
                </div>
                
                <div class="flex items-center justify-between p-3 bg-surface-alt/20 rounded-lg">
                    <div>
                        <span class="block font-medium">Compact View</span>
                        <span class="text-xs text-on-surface/60">Use a more dense layout for agent cards and logs.</span>
                    </div>
                    <button class="w-12 h-6 rounded-full bg-outline/20 border border-outline/30 relative shadow-inner">
                        <div class="absolute left-1 top-1 w-4 h-4 rounded-full bg-outline"></div>
                    </button>
                </div>
            </div>
        </section>

        <!-- System Status -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-6 flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                System Information
            </h2>
            <div class="grid grid-cols-2 gap-4">
                <div class="p-4 bg-surface-alt/10 border border-outline/10 rounded-lg">
                    <span class="text-xs text-on-surface/50 uppercase font-bold block mb-1">Backend Version</span>
                    <span class="font-mono text-primary">v0.1.0-alpha</span>
                </div>
                <div class="p-4 bg-surface-alt/10 border border-outline/10 rounded-lg">
                    <span class="text-xs text-on-surface/50 uppercase font-bold block mb-1">Frontend Version</span>
                    <span class="font-mono text-primary">v0.1.0-alpha</span>
                </div>
            </div>
        </section>
    </div>
</div>
