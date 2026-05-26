# Developer Reference

## Observability

### Metrics Endpoint

The backend exposes a Prometheus-compatible metrics endpoint:

**`GET /metrics`** — Returns metrics in Prometheus text format. Public, no authentication required.

Available metrics:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `chores_total` | Gauge | `state`, `disabled` | Total chores grouped by state and disabled flag |
| `chores_due_now_total` | Gauge | — | Chores where `state='due'` |
| `chores_due_soon_total` | Gauge | — | Chores where `next_due <= today + due_soon_days` |
| `chores_due_now_by_person` | Gauge | `person` | Due chores grouped by current assignee |
| `people_total` | Gauge | — | Total user count |
| `points_awarded_total` | Gauge | — | Sum of all PointsLog entries |
| `chore_completions_by_person` | Gauge | `person`, `window` | Completions in 7d and 30d windows |

Process metrics (CPU, memory, file descriptors) are provided automatically by `prometheus_client`.

HTTP request metrics (request count, duration histogram by path) are provided by `starlette-prometheus` middleware.

## API Development

### Adding a New Endpoint

1. **Define Schema** (in `schemas.py`):
   ```python
   class NewThingOut(BaseModel):
       id: int
       name: str
       model_config = {"from_attributes": True}
   ```

2. **Add Router Handler** (in `routers/`):
   ```python
   @router.get("", response_model=list[NewThingOut], summary="List all things")
   async def list_things(
       current_user: str = Depends(get_current_user),
       db: AsyncSession = Depends(get_db),
   ):
       """Get all things. Optionally filtered by query params."""
       # Implementation
   ```

3. **Add Service Logic** (if complex, in `services/`):
   ```python
   async def process_thing(thing: Thing, db: AsyncSession) -> Thing:
       # Business logic here
       await _log_action(thing, "processed", "user", db)
       db.add(thing)
       await db.commit()
       return thing
   ```

4. **Add to Main App** (already done if using include_router):
   - Routers are auto-included in `main.py`

5. **Document** (in `docs/API.md`):
   - Add endpoint documentation with example request/response

6. **Test** (in Swagger UI):
   - Verify endpoint works before committing

### Logging Actions

All user-visible actions should be logged:

```python
await _log_action(
    chore=chore_obj,
    action="completed",           # Action type
    person="username",            # Username or "system"
    db=db,
    reassigned_to=None,          # Optional, for reassignment
)
```

## React Component Development

### Component Structure

```typescript
// src/components/MyComponent.tsx
import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getThings, updateThing } from "../api/client";
import "./MyComponent.css";

interface Thing {
  id: number;
  name: string;
}

export default function MyComponent() {
  const { data: things = [], isLoading } = useQuery({
    queryKey: ["things"],
    queryFn: getThings,
  });

  const mutation = useMutation({
    mutationFn: updateThing,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["things"] });
    },
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      {things.map(thing => (
        <div key={thing.id}>{thing.name}</div>
      ))}
    </div>
  );
}
```

### Component Testing

```typescript
// src/__tests__/MyComponent.test.jsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MyComponent from "../components/MyComponent";
import * as client from "../api/client";

vi.mock("../api/client");

function wrap(ui) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("MyComponent", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    client.getThings.mockResolvedValue([]);
  });

  it("renders empty state", async () => {
    wrap(<MyComponent />);
    await waitFor(() => expect(screen.getByText("Loading...")).not.toBeInTheDocument());
  });
});
```

### Styling & Theming

- Use CSS files (e.g., `MyComponent.css`)
- **Always use CSS variables for colors:** `var(--bg)`, `var(--accent)`, etc.
- **Never hardcode hex values** – breaks theme switching
- Mobile-first responsive design
- Theme colors defined in `App.css` via 9-color system

#### 9-Color Theme System

All application theming uses a unified 9-color palette:

| Variable | Purpose |
|----------|---------|
| `--bg` | Page background |
| `--surface` | Card/panel background (layer 1) |
| `--surface2` | Elevated surface (layer 2), inputs, tags |
| `--accent` | Highlights, links, focus rings |
| `--primary` | Primary buttons and controls |
| `--secondary` | Secondary buttons |
| `--success` | Positive states |
| `--warning` | Caution states |
| `--error` | Destructive actions / validation errors |

**Rules:**
- Use `--primary` for buttons (not `--accent`)
- Use `--accent` for links and highlights (not `--primary`)
- Use `--error` for destructive actions (no `--danger`)
- For semi-transparent overlays: `rgba(var(--error-rgb), <alpha>)`

See `.claude/skills/theme-guide/SKILL.md` for complete reference.
