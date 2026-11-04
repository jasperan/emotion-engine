<script lang="ts">
  import { scenarios } from '$lib/api';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { setHeader, resetHeader } from '$lib/stores/header';
  import SimulationIntro from '$lib/components/SimulationIntro.svelte';

  let prompt = '';
  let isLoading = false;
  let error: string | null = null;
  let textareaElement: HTMLTextAreaElement;

  function applySuggestion(text: string) {
    prompt = text;
    textareaElement?.focus();
  }

  async function handleSubmit() {
    if (!prompt.trim()) return;

    isLoading = true;
    error = null;

    try {
      const result = await scenarios.generate({
        prompt,
        persona_count: 5, // Default for now, could act add controls later
        save_to_file: true
      });

      // Assuming result contains the created scenario or its ID.
      // If the API returns the scenario object with an ID:
      if (result && result.id) {
          goto(`/scenarios/${result.id}`);
      } else {
          // Fallback or handle differently based on actual response type
          // If need be, we can redirect to library or show success
           goto('/library');
      }

    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to generate scenario';
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    setHeader({ title: 'Simulation lab' });
    return resetHeader;
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
</script>

<svelte:head><title>Emotion Engine — Social simulation lab</title><meta name="description" content="Design personality-driven scenarios and observe emergent cooperation in multi-agent simulations." /></svelte:head>

<div class="simulation-entry flex flex-col items-center max-w-6xl mx-auto relative">

  <SimulationIntro />

  <div class="sim-prompt-heading border-t border-outline/15"><span>01 / Set the scene</span><span>Start with a question worth exploring</span></div>

  <!-- Chat Input Area -->
  <div class="w-full relative">
      <div class="sim-composer relative bg-surface rounded-lg border border-outline/40 overflow-hidden focus-within:border-flood-500 transition-colors duration-150">
         <textarea
            bind:this={textareaElement}
            bind:value={prompt}
            on:keydown={handleKeydown}
            class="w-full bg-transparent border-0 p-4 text-base text-on-background placeholder:text-on-surface/60 focus:ring-0 resize-none min-h-[120px]"
            placeholder="Describe a scenario"
            disabled={isLoading}
            aria-label="Simulation prompt"
            aria-invalid={error ? 'true' : undefined}
            aria-errormessage={error ? 'prompt-error' : undefined}
         ></textarea>

         <div class="flex justify-between items-center px-4 pb-3">
             <div class="flex gap-2">
                 <span class="sim-composer-hint">5 personalities · Enter to generate</span>
             </div>
             <button
                on:click={handleSubmit}
                disabled={!prompt.trim() || isLoading}
                class="btn-icon p-2 rounded-lg bg-surface-alt text-on-surface hover:bg-flood-500 hover:text-white transition-colors duration-150 disabled:opacity-30 disabled:cursor-not-allowed"
                aria-label={isLoading ? "Generating scenario" : "Send prompt"}
             >
                {#if isLoading}
                  <div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                {:else}
                  <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-arrow-up"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
                {/if}
             </button>
         </div>
      </div>

      {#if error}
         <div id="prompt-error" role="alert" class="mt-4 text-red-400 text-sm">
            {error}
         </div>
      {/if}
  </div>

  <p class="w-full mt-3 text-sm text-on-surface/60">
    Example: five neighbours in a small town share a limited water supply during a drought
  </p>

  <!-- Suggestions / Chips -->
  {#if !isLoading && !prompt}
  <div class="mt-6 flex flex-wrap justify-start gap-2 self-start">
      <button on:click={() => applySuggestion("Disaster Strike: A flash flood hits a coastal village.")} class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-outline/30 text-sm text-on-surface hover:bg-surface-alt hover:border-outline/50 hover:text-on-background transition-colors duration-150 cursor-pointer">
          <svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-on-surface/50"><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/></svg>
          Flash flood
      </button>
      <button on:click={() => applySuggestion("Mystery: Guests at a dinner party discover a theft.")} class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-outline/30 text-sm text-on-surface hover:bg-surface-alt hover:border-outline/50 hover:text-on-background transition-colors duration-150 cursor-pointer">
          <svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-on-surface/50"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
          Dinner party mystery
      </button>
       <button on:click={() => applySuggestion("Negotiation: Three companies bidding for a contract.")} class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-outline/30 text-sm text-on-surface hover:bg-surface-alt hover:border-outline/50 hover:text-on-background transition-colors duration-150 cursor-pointer">
          <svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-on-surface/50"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          Contract negotiation
      </button>
  </div>
  {/if}

</div>
