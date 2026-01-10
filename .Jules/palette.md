## 2024-05-23 - Accessibility First Steps
**Learning:** This repo is using custom Tailwind colors (like `bg-surface`, `text-on-background`). Any color changes need to respect these semantic tokens to maintain dark/light mode compatibility (if it exists) and visual consistency.
**Action:** When adding styles, stick to semantic names (`bg-surface`, `text-primary`) rather than raw colors like `bg-gray-900` or `text-blue-500`.

## 2024-05-23 - Interactive Elements
**Learning:** Many interactive elements are missing `aria-label` or proper keyboard support.
**Action:** Focus on adding `aria-label` to icon-only buttons and ensuring focus states are visible.
