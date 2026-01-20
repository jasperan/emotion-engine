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

## 2025-02-24 - Skip Links for Keyboard Navigation
**Learning:** Sidebar layouts create a significant barrier for keyboard users, requiring them to tab through every navigation item on every page load.
**Action:** Implement a "Skip to Content" link at the very top of the DOM that becomes visible on focus and jumps directly to the main content area (`id="main-content"`). Ensure the target has `tabindex="-1"` to reliably receive focus.

## 2025-02-27 - Semantic Tables and Links
**Learning:** Tables with repetitive links like "View" or "Edit" are a major accessibility barrier. A screen reader user navigating by links hears "View, View, View" without context.
**Action:** Always include unique context in the `aria-label` for repetitive links (e.g., "View run 12345"). Also ensure visual progress bars have `role="progressbar"` and appropriate aria attributes so they aren't invisible to assistive tech.

## 2025-05-25 - Accessible Toggle Switches
**Learning:** Static `div`s used as toggle switches are inaccessible and cannot be animated smoothly using `left`/`right` properties.
**Action:** Replace with `<button role="switch">`, use `aria-checked`, and animate the knob using `translate-x` for smooth, GPU-accelerated transitions.

## 2025-05-26 - Accessible Range Sliders
**Learning:** `input type="range"` elements often lack context, presenting just a number to users who may not know the scale (e.g., 1-10) or its meaning (e.g., "Reserved" vs "Open").
**Action:** Always provide visual labels for the minimum and maximum values of the scale. Use `aria-valuetext` to convey the current state descriptively (e.g., "5 out of 10 (Reserved to Open)") to screen reader users, and ensure the input has visible focus styles.
