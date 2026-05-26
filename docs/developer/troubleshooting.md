# Developer Troubleshooting

## Debugging

### Frontend

```typescript
// In browser DevTools:
// - React DevTools extension
// - Redux DevTools (React Query tab)
// - Console for network requests
console.log("Debug:", thing);
```

### Backend

```python
# In code
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Processing thing: {thing}")

# In terminal with --reload
# Server logs appear in terminal
```

## Performance Tips

1. **React Query:** Use proper query keys to avoid unnecessary fetches
2. **Memoization:** Use `useMemo` for expensive computations
3. **Invalidation:** Be specific with `invalidateQueries` (use queryKey prefix)
4. **Database:** Use async queries, avoid N+1 problems
5. **Images:** Optimize before uploading

## Security Checklist

- [ ] Validate all inputs (Pydantic handles backend)
- [ ] Check auth on all endpoints (`get_current_user` dependency)
- [ ] Prevent admin-only operations from regular users
- [ ] Sanitize/escape any user-generated content
- [ ] Use HTTPS in production (see [Deployment Setup](../deployment/setup.md))

## Common Tasks

### Add a new field to Chore

1. Add to `models.py` Chore class:
   ```python
   new_field: Mapped[str] = mapped_column(Text, default="")
   ```

2. Add to `schemas.py` ChoreOut:
   ```python
   new_field: str
   ```

3. Add to ChoreCreate/ChoreUpdate if user-settable:
   ```python
   new_field: Optional[str] = None
   ```

4. Database auto-creates column on next startup

### Add a new action type

1. Add constant to `chore_service.py`:
   ```python
   CHANGE_THING = "thing"
   ```

2. Call in service function:
   ```python
   await _log_action(chore, CHANGE_THING, "system", db)
   ```

3. Update `docs/API.md` to document new action type

### Create a new page

1. Create in `src/pages/MyPage.tsx`
2. Import in `src/App.jsx`
3. Add route in router setup
4. Add navigation link in `src/components/Sidebar.tsx`
5. Create tests in `src/__tests__/MyPage.test.jsx`

## Troubleshooting

### Frontend tests failing
- Run `npm test -- --run` to see full output
- Check test mocks are set up correctly
- Ensure React Query queryClient is in test wrapper

### Backend startup issues
- Check `requirements.txt` installed: `pip list`
- Verify Python 3.11+: `python --version`
- Check port 8000 not in use: `lsof -i :8000`

### Database errors
- Delete `backend/app.db` to reset database
- Check models.py has no syntax errors
- Verify schema migrations don't break existing data

### Performance issues
- Check React Query DevTools (browser extension)
- Profile with browser DevTools Perf tab
- Check backend logs for slow queries
- Verify indexes on frequently-queried columns

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [React Query Docs](https://tanstack.com/query/latest)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Vitest Docs](https://vitest.dev/)
