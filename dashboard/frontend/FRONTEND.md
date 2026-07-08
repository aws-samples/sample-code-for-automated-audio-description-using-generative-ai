# Dashboard Frontend

A small React 19 + TypeScript single-page app (built with Vite 8) that runs the DVI
dashboard. It's served as static files from S3 behind CloudFront; CloudFront proxies
`/api/*` to API Gateway, so the app makes same-origin calls with no CORS in normal use.

## Layout

```
src/
  main.tsx            # React entry point
  App.tsx             # Auth gate + page switching (no router)
  api.ts              # The single network layer — all fetch calls live here
  auth.ts             # Cognito (SRP) wrapper; config loaded at runtime
  types.ts            # Shared TypeScript interfaces for API payloads
  components/         # Page + feature components
    ui/               # shadcn/ui primitives (new-york style)
  lib/utils.ts        # cn() class-merge helper
  utils/              # small pure helpers (e.g. formatTime)
  index.css           # Tailwind v4 import + design tokens (@theme + :root)
```

## Key decisions

- **No router.** `App.tsx` holds an `activePage` state (`viewer` / `trigger` / `cost`)
  and toggles each page with `display: contents | none`. Pages stay mounted, so things
  like the Trigger page's live execution polling keep running when you switch tabs.
  Everything is gated behind an auth check that renders `LoginPage` until a Cognito
  session exists. Note: the internal page keys differ from the displayed tab labels in
  `NavBar.tsx` — `trigger` shows as **"Process"**, `viewer` as **"Viewer"**, and `cost`
  as **"Cost Estimation"**; `trigger` (Process) is the default landing page.
- **One API layer (`api.ts`).** Components never call `fetch` directly — they import
  typed functions. Each function calls `authHeaders()` (which throws if unauthenticated),
  checks `res.ok`, and unwraps the relevant field from the JSON envelope. New endpoints
  follow the same shape and add their response type to `types.ts`.
- **Auth (`auth.ts`).** Amazon Cognito via `amazon-cognito-identity-js` (SRP flow). The
  ID-token JWT is attached as the `Authorization` header on every API call. Cognito IDs
  are **not** hardcoded — they're loaded at runtime from `/auth-config.json`, which CDK
  generates at deploy time with the live pool/client IDs.
- **Styling: Tailwind CSS v4 + shadcn/ui.** App-specific styles use arbitrary-value
  utilities bound to CSS variables (e.g. `bg-[var(--surface-container-low)]`). The
  shadcn primitives in `components/ui` use bare token utilities (`bg-popover`,
  `bg-accent`, …). In Tailwind v4 those utilities only exist if the tokens are registered
  in an `@theme` block, so `index.css` keeps raw values in `:root` **and** exposes them
  via `@theme inline { --color-popover: var(--popover); … }`. Without that mapping the
  primitives render with no background (a transparent dropdown/popover) — keep it in sync
  when adding tokens.
- **State.** Local React state + hooks only; no global store. The Trigger page persists
  the active execution ARN to `localStorage` so a page refresh resumes status polling.
- **Upload.** The Process (Trigger) page includes a `VideoUpload` component that uploads
  an MP4 straight to the pipeline bucket's `input/` prefix via a presigned PUT URL
  (`POST /api/trigger/upload`), so users can add source videos without leaving the UI.

## Build & test

- `npm run build` → `tsc -b && vite build`, emits `dist/`, which CDK deploys to the
  hosting bucket. `vite.config.ts` sets `define: { global: "globalThis" }` (required by
  `amazon-cognito-identity-js` in the browser — don't remove it).
- `npx vitest --run` for tests (Vitest + Testing Library, `jsdom`). Pure logic such as
  cost math and time formatting is covered with `fast-check` property tests
  (`*.property.test.ts`).
