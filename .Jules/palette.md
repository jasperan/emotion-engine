## 2024-05-22 - [Complex Forms and Labels]
**Learning:** In complex forms where a group of controls (like a set of buttons) represents a single input (like "Character Types"), standard `<label for="...">` doesn't work. Instead, use `role="group"` with `aria-labelledby` pointing to the label element's ID. This preserves the semantic relationship for screen readers.
**Action:** Use `role="group"` and `aria-labelledby` for custom multi-control inputs instead of unassociated labels.

## 2024-05-22 - [Focus Management for "Fill" Actions]
**Learning:** When a user clicks a "chip" or "suggestion" button to fill a form field, they almost always intend to edit or submit that field immediately. Simply updating the value without moving focus forces the user to navigate back to the input manually.
**Action:** Always programmatically focus the target input field when using helper buttons that populate it.
