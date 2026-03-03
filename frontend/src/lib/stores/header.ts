import { writable } from 'svelte/store';
import type { ComponentType } from 'svelte';

export interface HeaderState {
    title: string;
    description?: string;
    breadcrumb?: { label: string; href: string }[];
    actions?: { label: string; onclick: () => void; primary?: boolean }[];
}

export const headerStore = writable<HeaderState>({
    title: 'Emotion Engine'
});

export function setHeader(state: HeaderState) {
    headerStore.set(state);
}

export function resetHeader() {
    headerStore.set({ title: 'Emotion Engine' });
}
