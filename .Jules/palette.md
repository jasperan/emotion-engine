## 2024-05-23 - Accessibility First Steps
**Learning:** This repo is using custom Tailwind colors (like `bg-surface`, `text-on-background`). Any color changes need to respect these semantic tokens to maintain dark/light mode compatibility (if it exists) and visual consistency.
**Action:** When adding styles, stick to semantic names (`bg-surface`, `text-primary`) rather than raw colors like `bg-gray-900` or `text-blue-500`.

## 2024-05-23 - Interactive Elements
**Learning:** Many interactive elements are missing `aria-label` or proper keyboard support.
**Action:** Focus on adding `aria-label` to icon-only buttons and ensuring focus states are visible.

## 2024-05-24 - Labeling Icon-Only Buttons
**Learning:** Found multiple icon-only buttons (like Share in header) without `aria-label`. This makes them invisible or confusing to screen reader users.
**Action:** Always verify icon-only buttons have a descriptive `aria-label` and `aria-hidden="true"` on the SVG icon itself to prevent redundant announcements.

## 2025-02-23 - Accessible Remove Buttons
**Learning:** Destructive actions like "Remove Agent" represented by a single "X" character are common but inaccessible.
**Action:** Wrap the icon/character in `<span aria-hidden="true">` and provide a dynamic `aria-label` (e.g., "Remove agent {name}") on the button itself. Adding hover background and padding also improves hit target usability.
