# CV Tailor frontend

React + TypeScript + Vite + Zustand + Tailwind/shadcn. Talks to the FastAPI backend through the
Vite dev proxy (`/api` → `http://127.0.0.1:8000`).

```bash
npm install
npm run dev        # needs the backend: uvicorn backend.main:app (from the repo root)
npm test           # vitest
npm run build      # typecheck + production build
npm run gen:types  # regenerate src/api/schema.ts from the backend's Pydantic models
```

`src/api/schema.ts` is generated: after changing a Pydantic model, run `npm run gen:types`
instead of editing it.
