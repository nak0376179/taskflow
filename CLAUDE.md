# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Commands

```bash
npm run dev        # Dev server (Turbopack; outputs to .next/dev)
npm run build      # Production build — also runs TypeScript checking
npm run lint       # ESLint (flat config, lints whole project)
npx eslint src/components/todo-app.tsx   # Lint a single file
npx tsc --noEmit   # Type-check only
```

There is no test framework configured.

Add new UI components with the shadcn CLI (config in `components.json`, style `base-nova`):

```bash
npx shadcn add <component>
```

## Next.js 16 — differs from training data

This project uses **Next.js 16.2.11**, which has breaking changes relative to Next.js 14/15. Authoritative docs are bundled at `node_modules/next/dist/docs/` (requires `npm install` first) — consult them before writing framework-touching code, especially `01-app/02-guides/upgrading/version-16.md`. Key changes:

- **Async-only request APIs**: `params`, `searchParams`, `cookies()`, `headers()`, and `draftMode()` must be `await`ed — synchronous access was removed. Use the generated `PageProps`/`LayoutProps`/`RouteContext` type helpers (`npx next typegen`).
- **`middleware.ts` is deprecated** — the file and exported function are now named `proxy` (`proxy.ts`), and it runs on the Node.js runtime, not edge.
- **`next lint` is removed** — run `eslint` directly (the `lint` script does this), and `next build` no longer lints.
- **Turbopack is the default** for both `dev` and `build`; dev output lives in `.next/dev`, so dev and build can run concurrently.
- **Caching**: `revalidateTag(tag, profile)` now requires a `cacheLife` profile second argument; `updateTag()` (Server Actions, read-your-writes) and `refresh()` are new; `cacheLife`/`cacheTag` lost their `unstable_` prefix; PPR/`dynamicIO`/`useCache` are replaced by the top-level `cacheComponents` config option.
- ESLint uses **flat config** (`eslint.config.mjs` with `defineConfig` + `eslint-config-next` presets).

## Architecture

Small single-page todo app (App Router, `src/` layout, path alias `@/*` → `src/*`):

- `src/app/page.tsx` — server component that just renders `<TodoApp />`; `src/app/layout.tsx` sets up Geist fonts via CSS variables.
- `src/components/todo-app.tsx` — the whole app: a `"use client"` component owning all state (todos, input, filter). Persists to `localStorage` under key `taskflow.todos`, loading once after hydration in an effect (guarded by a `loaded` flag so the initial empty state doesn't overwrite storage).
- `src/components/ui/*` — shadcn-generated components. **Built on `@base-ui/react` primitives, not Radix.** Styling uses `class-variance-authority` variants merged through `cn()` (`src/lib/utils.ts`), with `data-slot` attributes on each part.
- **Tailwind CSS v4** — no `tailwind.config`; all theme configuration is CSS-based in `src/app/globals.css` (`@theme inline` mapping oklch CSS variables, `@custom-variant dark`). Dark mode is class-based (`.dark`).

## Conventions

- User-facing UI text is Japanese; code, comments, and identifiers are English.
- Follow the existing shadcn component patterns when adding UI: cva variants + `cn()` + Base UI primitives, semantic color tokens (`bg-primary`, `text-muted-foreground`, etc.) rather than raw palette classes.
