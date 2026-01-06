<script lang="ts">
  import { scenarios } from '$lib/api';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { setHeader, resetHeader } from '$lib/stores/header';

  let prompt = '';
  let isLoading = false;
  let error: string | null = null;

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
    setHeader({ title: 'New Chat' });
    return resetHeader;
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
</script>

<div class="flex flex-col items-center justify-center min-h-[calc(100vh-10rem)] max-w-6xl mx-auto px-6 relative">
  
  <div class="text-center mb-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
     <h1 class="text-5xl font-medium tracking-tighter mb-4 bg-clip-text text-transparent bg-gradient-to-r from-accent-blue via-accent-purple to-accent-teal">
       Hello, User
     </h1>
     <p class="text-xl text-on-surface">
       Describe a social simulation scenario to generate agents and environment.
     </p>
  </div>

  <!-- Chat Input Area -->
  <div class="w-full max-w-2xl relative group">
      <div class="absolute -inset-0.5 bg-gradient-to-r from-accent-blue/30 to-accent-purple/30 rounded-2xl blur opacity-30 group-hover:opacity-60 transition duration-500"></div>
      
      <div class="relative bg-surface rounded-2xl border border-outline/50 shadow-2xl overflow-hidden focus-within:border-accent-blue/50 focus-within:ring-1 focus-within:ring-accent-blue/50 transition-all">
         <textarea
            bind:value={prompt}
            on:keydown={handleKeydown}
            class="w-full bg-transparent border-0 p-4 text-base text-on-background placeholder:text-on-surface/50 focus:ring-0 resize-none min-h-[120px]"
            placeholder="Ex: Create a scenario where 5 neighbors in a small town have to decide how to allocate a limited water supply during a drought..."
            disabled={isLoading}
         ></textarea>
         
         <div class="flex justify-between items-center px-4 pb-3">
             <div class="flex gap-2">
                 <!-- Optional tools/attachments icons could go here -->
             </div>
             <button 
                on:click={handleSubmit}
                disabled={!prompt.trim() || isLoading}
                aria-label={isLoading ? "Generating scenario" : "Send prompt"}
                class="btn-icon p-2 rounded-full bg-on-primary/10 text-on-background/50 hover:bg-primary hover:text-on-primary transition-all disabled:opacity-30 disabled:cursor-not-allowed"
             >
                {#if isLoading}
                  <div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                {:else}
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-arrow-up"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
                {/if}
             </button>
         </div>
      </div>
      
      {#if error}
         <div class="absolute -bottom-12 left-0 right-0 text-center text-red-400 text-sm">
            {error}
         </div>
      {/if}
  </div>

  <!-- Suggestions / Chips -->
  {#if !isLoading && !prompt}
  <div class="mt-8 flex flex-wrap justify-center gap-3 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-100">
      <button on:click={() => prompt = "Disaster Strike: A flash flood hits a coastal village."} class="px-4 py-2 rounded-xl bg-surface-alt/50 border border-outline/30 text-sm text-on-surface hover:bg-surface-alt hover:border-outline/60 transition-colors text-left">
          🌊 Flash Flood
      </button>
      <button on:click={() => prompt = "Mystery: Guests at a dinner party discover a theft."} class="px-4 py-2 rounded-xl bg-surface-alt/50 border border-outline/30 text-sm text-on-surface hover:bg-surface-alt hover:border-outline/60 transition-colors text-left">
          🕵️ Dinner Party Mystery
      </button>
       <button on:click={() => prompt = "Negotiation: Three companies bidding for a contract."} class="px-4 py-2 rounded-xl bg-surface-alt/50 border border-outline/30 text-sm text-on-surface hover:bg-surface-alt hover:border-outline/60 transition-colors text-left">
          🤝 Contract Negotiation
      </button>
  </div>
  {/if}

</div>
