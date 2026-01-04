<script>
  import '../app.css';
</script>

<div class="flex h-screen bg-background text-on-background overflow-hidden selection:bg-primary selection:text-on-primary">
  <!-- Sidebar -->
  <aside class="w-64 flex flex-col border-r border-outline/30 bg-surface hidden md:flex">
    <!-- Header -->
    <div class="h-16 flex items-center px-4 border-b border-outline/30">
      <div class="font-bold text-lg tracking-tight flex items-center gap-2">
        <div class="w-6 h-6 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple"></div>
        <span>Emotion Engine</span>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto py-4 px-2 space-y-1">
      <a href="/" class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-message-square"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        Chat
      </a>
      <a href="/library" class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-on-surface hover:bg-surface-alt hover:text-on-background transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-library"><path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/></svg>
        Library
      </a>
      <a href="/settings" class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-on-surface hover:bg-surface-alt hover:text-on-background transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-settings"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
        Settings
      </a>
    </nav>

    <!-- Footer -->
    <div class="p-4 border-t border-outline/30">
       <button class="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm font-medium text-on-surface hover:bg-surface-alt transition-colors">
          <div class="w-6 h-6 rounded-full bg-accent-teal/20 text-accent-teal flex items-center justify-center text-xs">U</div>
          <span>User Profile</span>
       </button>
    </div>
  </aside>

  <!-- Main Content -->
  <main class="flex-1 flex flex-col relative overflow-hidden">
    <!-- Top Bar (Optional, can be used for context) -->
    <header class="h-16 border-b border-outline/30 flex items-center justify-between px-6 bg-background/80 backdrop-blur-sm z-10">
       <div class="flex items-center gap-4">
          <h1 class="font-medium text-on-background">New Chat</h1>
          <span class="px-2 py-0.5 rounded text-xs bg-primary/10 text-primary border border-primary/20">Gemini Pro 1.5</span>
       </div>
       <div class="flex items-center gap-2">
           <button class="p-2 text-on-surface hover:text-on-background hover:bg-surface-alt rounded-full transition-colors">
               <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-share"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" x2="12" y1="2" y2="15"/></svg>
           </button>
           <button class="p-2 text-on-surface hover:text-on-background hover:bg-surface-alt rounded-full transition-colors">
               <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-more-vertical"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
           </button>
       </div>
    </header>

    <div class="flex-1 overflow-auto">
        <slot />
    </div>
  </main>
</div>
