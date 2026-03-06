<script lang="ts">
  import { onMount } from 'svelte';
  import { setHeader, resetHeader } from '$lib/stores/header';
  import { ollama } from '$lib/api';

  let autoScroll = true;
  let compactView = false;
  let autoFallback = true;

  // Configuration state
  let ollamaUrl = 'http://localhost:11434/v1';
  let defaultModel = 'qwen3.5:27b';
  let fallbackModel = 'qwen3.5:4b';

  // Model list state
  let availableModels: string[] = [];
  let modelsLoaded = false;
  let modelsError = false;

  let saving: Record<string, boolean> = {};
  type StatusMessage = { type: 'success' | 'error'; text: string } | null;
  let statusMsg: Record<string, StatusMessage> = {};
  let timeoutIds: Record<string, NodeJS.Timeout> = {};

  async function saveConfig(field: string) {
    saving[field] = true;
    statusMsg[field] = null; // Clear previous message

    if (timeoutIds[field]) {
      clearTimeout(timeoutIds[field]);
    }

    // Simulate API delay
    await new Promise(r => setTimeout(r, 800));

    saving[field] = false;
    statusMsg[field] = { type: 'success', text: 'Saved successfully' };

    // Clear success message after 3s
    timeoutIds[field] = setTimeout(() => {
        if (statusMsg[field]?.type === 'success') {
            statusMsg[field] = null;
        }
    }, 3000);
  }

  async function loadModels() {
    try {
      const models = await ollama.models();
      availableModels = models;
      modelsLoaded = true;
      modelsError = models.length === 0;
    } catch {
      modelsError = true;
      modelsLoaded = true;
    }
  }

  onMount(() => {
    setHeader({ title: 'Settings' });
    loadModels();
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
                        <input
                            bind:value={ollamaUrl}
                            type="text"
                            id="ollama-url"
                            placeholder="http://localhost:11434/v1"
                            class="input flex-1"
                        />
                        <button
                            class="btn btn-secondary min-w-[80px]"
                            on:click={() => saveConfig('ollamaUrl')}
                            disabled={saving['ollamaUrl']}
                        >
                            {#if saving['ollamaUrl']}
                                <div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mx-auto"></div>
                            {:else}
                                Save
                            {/if}
                        </button>
                    </div>
                    <div class="flex justify-between items-start">
                        <p class="text-[10px] text-on-surface/50">The endpoint for your Ollama instance (OpenAI-compatible).</p>
                        {#if statusMsg['ollamaUrl']}
                            <span role="alert" class="text-xs {statusMsg['ollamaUrl'].type === 'success' ? 'text-green-500' : 'text-red-500'} animate-in fade-in">
                                {statusMsg['ollamaUrl'].text}
                            </span>
                        {/if}
                    </div>
                </div>

                <div class="space-y-2">
                    <label for="default-model" class="text-sm font-medium text-on-surface">Primary Model</label>
                    <div class="flex gap-2">
                        {#if modelsLoaded && !modelsError && availableModels.length > 0}
                            <select
                                bind:value={defaultModel}
                                id="default-model"
                                class="input flex-1"
                            >
                                {#each availableModels as model}
                                    <option value={model}>{model}</option>
                                {/each}
                            </select>
                        {:else}
                            <input
                                bind:value={defaultModel}
                                type="text"
                                id="default-model"
                                placeholder="qwen3.5:27b"
                                class="input flex-1"
                            />
                        {/if}
                        <button
                            class="btn btn-secondary min-w-[80px]"
                            on:click={() => saveConfig('defaultModel')}
                            disabled={saving['defaultModel']}
                        >
                             {#if saving['defaultModel']}
                                <div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mx-auto"></div>
                            {:else}
                                Save
                            {/if}
                        </button>
                    </div>
                    <div class="flex justify-between items-start">
                         <p class="text-[10px] text-on-surface/50">The primary model to use for simulations.</p>
                         {#if statusMsg['defaultModel']}
                            <span role="alert" class="text-xs {statusMsg['defaultModel'].type === 'success' ? 'text-green-500' : 'text-red-500'} animate-in fade-in">
                                {statusMsg['defaultModel'].text}
                            </span>
                        {/if}
                    </div>
                </div>

                <div class="space-y-2">
                    <label for="fallback-model" class="text-sm font-medium text-on-surface">Fallback Model</label>
                    <div class="flex gap-2">
                        {#if modelsLoaded && !modelsError && availableModels.length > 0}
                            <select
                                bind:value={fallbackModel}
                                id="fallback-model"
                                class="input flex-1"
                            >
                                {#each availableModels as model}
                                    <option value={model}>{model}</option>
                                {/each}
                            </select>
                        {:else}
                            <input
                                bind:value={fallbackModel}
                                type="text"
                                id="fallback-model"
                                placeholder="qwen3.5:4b"
                                class="input flex-1"
                            />
                        {/if}
                        <button
                            class="btn btn-secondary min-w-[80px]"
                            on:click={() => saveConfig('fallbackModel')}
                            disabled={saving['fallbackModel']}
                        >
                             {#if saving['fallbackModel']}
                                <div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mx-auto"></div>
                            {:else}
                                Save
                            {/if}
                        </button>
                    </div>
                    <div class="flex justify-between items-start">
                         <p class="text-[10px] text-on-surface/50">Used when the primary model is unavailable or fails.</p>
                         {#if statusMsg['fallbackModel']}
                            <span role="alert" class="text-xs {statusMsg['fallbackModel'].type === 'success' ? 'text-green-500' : 'text-red-500'} animate-in fade-in">
                                {statusMsg['fallbackModel'].text}
                            </span>
                        {/if}
                    </div>
                </div>

                <div class="flex items-center justify-between p-3 bg-surface-alt/20 rounded-lg">
                    <div id="label-autofallback">
                        <span class="block font-medium text-sm">Auto-Fallback</span>
                        <span class="text-xs text-on-surface/60">Automatically switch to fallback model on primary failure.</span>
                    </div>
                    <button
                        role="switch"
                        aria-checked={autoFallback}
                        aria-labelledby="label-autofallback"
                        on:click={() => autoFallback = !autoFallback}
                        class="w-12 h-6 rounded-full border relative shadow-inner transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {autoFallback ? 'bg-primary/20 border-primary/30' : 'bg-outline/20 border-outline/30'}"
                    >
                        <div class="absolute top-1 left-1 w-4 h-4 rounded-full transition-transform {autoFallback ? 'translate-x-6 bg-primary' : 'translate-x-0 bg-outline'}"></div>
                    </button>
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
                    <div id="label-autoscroll">
                        <span class="block font-medium">Auto-scroll Message Log</span>
                        <span class="text-xs text-on-surface/60">Automatically scroll to the latest message during simulations.</span>
                    </div>
                    <button
                        role="switch"
                        aria-checked={autoScroll}
                        aria-labelledby="label-autoscroll"
                        on:click={() => autoScroll = !autoScroll}
                        class="w-12 h-6 rounded-full border relative shadow-inner transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {autoScroll ? 'bg-primary/20 border-primary/30' : 'bg-outline/20 border-outline/30'}"
                    >
                        <div class="absolute top-1 left-1 w-4 h-4 rounded-full transition-transform {autoScroll ? 'translate-x-6 bg-primary' : 'translate-x-0 bg-outline'}"></div>
                    </button>
                </div>
                
                <div class="flex items-center justify-between p-3 bg-surface-alt/20 rounded-lg">
                    <div id="label-compact">
                        <span class="block font-medium">Compact View</span>
                        <span class="text-xs text-on-surface/60">Use a more dense layout for agent cards and logs.</span>
                    </div>
                    <button
                        role="switch"
                        aria-checked={compactView}
                        aria-labelledby="label-compact"
                        on:click={() => compactView = !compactView}
                        class="w-12 h-6 rounded-full border relative shadow-inner transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {compactView ? 'bg-primary/20 border-primary/30' : 'bg-outline/20 border-outline/30'}"
                    >
                        <div class="absolute top-1 left-1 w-4 h-4 rounded-full transition-transform {compactView ? 'translate-x-6 bg-primary' : 'translate-x-0 bg-outline'}"></div>
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
