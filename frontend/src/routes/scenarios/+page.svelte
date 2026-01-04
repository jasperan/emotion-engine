<script lang="ts">
  import { onMount } from 'svelte';
  import { scenarios, type Scenario } from '$lib/api';
  import { setHeader, resetHeader } from '$lib/stores/header';
  import { goto } from '$app/navigation';

  let scenariosList: Scenario[] = [];
  let isLoading = true;
  let error: string | null = null;

  onMount(async () => {
    setHeader({ title: 'Library' }); // or Scenarios
    try {
      scenariosList = await scenarios.list();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load scenarios';
    } finally {
      isLoading = false;
    }
    return resetHeader;
  });

  function startRun(scenarioId: string) {
      // Just navigate to the run creation or direct run page?
      // Since we don't have a direct "start run" flow fully mapped in my head, I'll assume we can go to details or new run.
      // Let's go to scenario details usually, but the screenshot shows a list.
      // For now, let's just create a run and go to it?
      // Or just a button that does nothing for the visual?
      // Realistically, it should go to a scenario detail or prep page.
      goto(`/scenarios/${scenarioId}`);
  }
</script>

<div class="max-w-7xl mx-auto px-6 py-8">
  <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
    <div>
      <h1 class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-accent-blue to-accent-teal mb-2">
        Scenario Library
      </h1>
      <p class="text-on-surface/70">
        Choose a simulation scenario or create your own.
      </p>
    </div>
    <a 
      href="/scenarios/new" 
      class="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
      Create Scenario
    </a>
  </div>

  {#if isLoading}
    <div class="flex justify-center items-center h-64">
      <div class="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>
  {:else if error}
    <div class="p-6 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-center">
      <p>Error: {error}</p>
      <button class="mt-4 px-4 py-2 bg-surface text-on-surface hover:bg-surface-alt rounded-lg" on:click={() => window.location.reload()}>Retry</button>
    </div>
  {:else if scenariosList.length === 0}
    <div class="text-center py-20 bg-surface/30 rounded-2xl border border-outline/30 border-dashed">
      <div class="w-16 h-16 bg-surface-alt rounded-full flex items-center justify-center mx-auto mb-4 text-on-surface/50">
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
      </div>
      <h3 class="text-xl font-medium text-on-surface mb-2">No Scenarios Found</h3>
      <p class="text-on-surface/60 mb-6 max-w-md mx-auto">Get started by creating your first simulation scenario using our AI generator.</p>
      <a href="/scenarios/new" class="inline-flex items-center gap-2 text-primary hover:underline">
        Create New Scenario &rarr;
      </a>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {#each scenariosList as scenario}
        <div class="group relative bg-surface hover:bg-surface-alt/50 border border-outline/30 hover:border-accent-blue/30 rounded-xl p-6 transition-all duration-300 hover:shadow-xl hover:shadow-accent-blue/5">
          <div class="absolute inset-0 bg-gradient-to-br from-accent-blue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-xl pointer-events-none"></div>
          
          <div class="relative z-10">
            <div class="flex justify-between items-start mb-4">
              <div class="p-3 bg-surface-alt rounded-lg text-accent-blue">
                 <!-- Icon based on config or random -->
                 <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/></svg>
              </div>
              <span class="text-xs font-mono px-2 py-1 rounded bg-surface-alt/80 border border-outline/20 text-on-surface/60">
                {scenario.agent_templates?.length || 0} Agents
              </span>
            </div>

            <h3 class="text-xl font-semibold mb-2 text-on-surface group-hover:text-primary transition-colors">
              {scenario.name}
            </h3>
            <p class="text-on-surface/70 text-sm mb-6 line-clamp-3 min-h-[3rem]">
              {scenario.description || 'No description provided.'}
            </p>

            <div class="flex items-center gap-3">
              <button 
                on:click={() => startRun(scenario.id)}
                class="flex-1 px-4 py-2 bg-primary/10 hover:bg-primary text-primary hover:text-on-primary rounded-lg font-medium transition-colors text-sm text-center"
              >
                Run
              </button>
              <a 
                href="/scenarios/{scenario.id}/edit"
                class="p-2 text-on-surface/50 hover:text-on-surface hover:bg-surface-alt rounded-lg transition-colors"
                title="Edit"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
              </a>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
