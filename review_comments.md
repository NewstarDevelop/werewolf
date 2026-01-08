# Review of Werewolf AI Project

## Summary
The project demonstrates high-quality engineering standards with a modern stack (Vite, React 18, TypeScript, Tailwind). The architecture is sound, utilizing **React Query** for server state and **WebSockets** for real-time updates. The codebase shows evidence of careful thought regarding race conditions (state versioning) and performance (virtualization).

However, there are opportunities to improve accessibility (particularly for live updates), decouple logic in large hooks, and adopt more CSS-native responsive patterns.

## 1. Frontend Code Quality

### Strengths
- **Type Safety**: Strict TypeScript usage across the board. `api.ts` provides comprehensive type definitions for the backend contract.
- **State Management**: Excellent use of `TanStack Query` for async state management, including smart polling strategies and retry logic.
- **Validation**: Usage of `Zod` for runtime input validation in `GameActions.tsx` is a best practice.

### Issues
- **[High] "God Hook" Pattern (`useGame.ts`)**: The `useGame` hook is doing too much: data fetching, WebSocket management, auto-stepping logic, and action dispatching.
  - *Recommendation*: Split into smaller hooks: `useGameState` (data), `useGameActions` (mutations), and `useGameEngine` (auto-step/automation logic).
- **[Medium] Component Logic in Page**: `GamePage.tsx` contains significant data transformation logic (mapping players, formatting messages).
  - *Recommendation*: Move `players` and `messages` memoization into a `useGameViewModel` hook or standard selectors.

## 2. Accessibility & Responsive Design

### Strengths
- **Rich ARIA Labels**: `PlayerCard.tsx` constructs excellent descriptive `aria-label` strings, making the complex game state accessible.
- **Keyboard Navigation**: Interactive elements use standard button tags.

### Issues
- **[High] Missing Live Regions in Chat**: `ChatLog.tsx` lacks `aria-live="polite"` or `role="log"`. Screen reader users will not be announced when new chat messages or system events arrive.
  - *Recommendation*: Add a visually hidden `div` with `role="log" aria-live="polite"` that updates with the latest message text.
- **[Medium] JS-Driven Responsiveness**: `GamePage.tsx` uses `useIsMobile()` to conditionally render `flex-col` vs `flex-row`. This causes React to re-render the entire tree on breakpoint changes.
  - *Recommendation*: Use CSS Flexbox with Tailwind classes (e.g., `flex-col md:flex-row`) for layout shifts. It's more performant and robust.
- **[Low] Semantic HTML**: The main layout relies heavily on `div` soup.
  - *Recommendation*: Use `<main>`, `<aside>`, and `<header>` regions in `GamePage.tsx` to help assistive technology navigate the landmarks.

## 3. Component Design Consistency

### Strengths
- **Visual Consistency**: Consistent use of Tailwind colors and "glassmorphism" styles.
- **Iconography**: `Lucide` icons are used consistently throughout.

### Issues
- **[Medium] Imperative Styling Logic**: `PlayerCard.tsx` uses complex `if/else` chains (`getBorderClass`) to determine styles.
  - *Recommendation*: Refactor this into `class-variance-authority` (CVA) variants. This matches the Shadcn/UI pattern used elsewhere and makes priority logic (e.g., "speaking" overrides "selected") declarative.

## 4. Code Maintainability

### Strengths
- **Directory Structure**: Logical separation of `components`, `hooks`, `pages`, and `services`.
- **API Abstraction**: `api.ts` provides a clean interface for the backend, isolating components from `fetch` details.

### Issues
- **[Low] Hardcoded Business Logic in Components**: Some game rules (like specific role colors or icons) are hardcoded in `PlayerCard`.
  - *Recommendation*: Move role configurations (colors, icons, names) to a centralized config object or constant file (`frontend/src/config/roles.ts`).

## 5. Performance Optimization

### Strengths
- **Virtualization**: `ChatLog.tsx` correctly uses `react-window` to handle potentially long chat histories.
- **Memoization**: Good use of `useMemo` for expensive derived state and `memo` for list items (`PlayerCard`).
- **Network Optimization**: The `useGameWebSocket` hook implements version checking (`state_version`) to prevent stale data from overwriting newer states, solving a common race condition in real-time apps.

### Issues
- **[Medium] Re-render Scope**: Because `useGame` returns a single large object, any change (even a minor loading state) triggers a re-render of `GamePage`.
  - *Recommendation*: As part of splitting `useGame`, ensure components only subscribe to the slices of state they need.

## Severity Summary
| Level | Count | Key Areas |
| :--- | :---: | :--- |
| **Critical** | 0 | - |
| **High** | 2 | Hook Complexity, Chat Accessibility |
| **Medium** | 4 | JS-Layout, Styling Logic, Logic Separation, Re-renders |
| **Low** | 2 | Semantic HTML, Config Hardcoding |