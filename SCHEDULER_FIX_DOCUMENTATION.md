# Anki Scheduler Counter Fix - Documentation

## Summary
Fixed critical bugs in the counter display logic for New/Learn/Due cards. The deck list now correctly shows Learning and Due counts based on proper day boundary calculations, matching Anki's behavior.

## Bugs Fixed

### BUG #1 (CRITICAL): Learning Counter Logic Incorrect
**Severity**: Critical - Counters showed 0 even after studying cards

**Location**: [app/routes/main.py](app/routes/main.py#L84-L95)

**Original Issue**: 
Learning cards counted only if `due_at <= now`, which means only cards due RIGHT NOW were counted.

```python
# WRONG (old code):
is_due = due_at is None or due_at <= now
if queue in {"learning", "relearning"}:
    if is_due:
        learn_count += 1
```

**Example of Bug**:
- Current time: 10:00 AM
- Card answered "Good" → scheduled for +10 min (10:10 AM)
- Old logic: 10:10 <= 10:00? NO → Learn count = 0 ❌
- Expected: Learn count = 1 ✓

**Root Cause**: 
Learning cards should be counted if they're due "sometime today" (before next day boundary), not just exactly now.

**Fix**:
```python
# CORRECT (new code):
next_day_boundary = _day_index_to_datetime(today_day_index + 1, boundary_hour)
if queue in {"learning", "relearning"}:
    if due_at and due_at < next_day_boundary:  # Compare to day boundary, not now
        learn_count += 1
```

**Why This Matters**: 
Anki displays Learning count as "all learning cards scheduled for today" so users see immediate feedback after studying.

---

### BUG #2 (MINOR): Missing `due_day` Column
**Severity**: Minor - Made persistence and queries harder

**Issue**: 
VocabularyProgress had `due_at` (datetime) but no `due_day` (integer day index) field for review cards.

**Files Changed**:
1. [models/vocabulary_progress.py](models/vocabulary_progress.py#L22) - Added column
   ```python
   due_day = db.Column(db.Integer, nullable=True, index=True)
   ```

2. Migration: [migrations/versions/a2f8b3c9d4e0_add_due_day_to_progress.py](migrations/versions/a2f8b3c9d4e0_add_due_day_to_progress.py)

**Benefits**:
- Direct SQL queries can use `due_day` without computing from datetime
- Persistent storage of the exact day index used for scheduling
- Better separation of concerns (datetime vs day index)

---

## Files Modified

### 1. [models/vocabulary_progress.py](models/vocabulary_progress.py)
**Change**: Added `due_day` column
```python
due_day = db.Column(db.Integer, nullable=True, index=True)
```

### 2. [app/routes/vocabulary.py](app/routes/vocabulary.py#L349-L410)
**Changes**:
- Updated `_card_state_from_progress()` to use `due_day` directly if available
- Updated `_apply_card_state_to_progress()` to persist `due_day` to database
- Added backward compatibility for old records without `due_day`

### 3. [app/routes/main.py](app/routes/main.py#L1-L30)
**Changes**:
- Added imports: `date`, `timedelta` from datetime; `default_deck_options` from scheduler
- Added helper functions: `_day_index()`, `_day_index_to_datetime()`
- Fixed counter logic in `dashboard()` function

**Counter Logic Fix**:
```python
# Calculate day boundaries
today_day_index = _day_index(now, options.dayBoundaryHourLocal)
next_day_boundary = _day_index_to_datetime(today_day_index + 1, options.dayBoundaryHourLocal)

# Learning cards: count if due_at < nextDayBoundary (due today)
if queue in {"learning", "relearning"}:
    if due_at and due_at < next_day_boundary:
        learn_count += 1

# Review cards: count if due_day <= today_day_index (due today or earlier)
if queue == "review":
    card_due_day = due_day or _day_index(due_at or now, options.dayBoundaryHourLocal)
    if card_due_day <= today_day_index:
        due_count += 1
```

### 4. [migrations/versions/a2f8b3c9d4e0_add_due_day_to_progress.py](migrations/versions/a2f8b3c9d4e0_add_due_day_to_progress.py)
**Change**: Database migration to add `due_day` column with index

---

## Counter Logic Definitions (Anki-Compatible)

### NewCount
- **Definition**: Number of cards with `queue='new'`
- **Count if**: Always (as long as no progress record exists or queue=new)

### LearnCount  
- **Definition**: Number of cards with `queue in ('learning', 'relearning')` AND due before next day boundary
- **Count if**: `due_at < nextDayBoundary`
  - Where `nextDayBoundary = time at dayBoundaryHourLocal on next day`
  - E.g., with dayBoundaryHourLocal=4: 4 AM tomorrow
- **NOT counted if**: Due tomorrow or later

### DueCount
- **Definition**: Number of review cards due today or earlier
- **Count if**: 
  - For review cards: `due_day <= today_day_index`
  - Where `due_day` is the ordinal day index (calculated from due_at or stored directly)
- **NOT counted if**: Due in future

---

## Testing

### Unit Tests
**File**: [tests/test_counter_logic.py](tests/test_counter_logic.py)

Tests cover:
- Day index calculations and boundary crossing
- Learning cards due soon are counted
- Learning cards due tomorrow are NOT counted
- Review cards due today/yesterday ARE counted
- Review cards due tomorrow are NOT counted

**Run**: 
```bash
python -m unittest tests.test_counter_logic -v
```

**Result**: ✅ 12/12 tests pass

### Integration Tests
**File**: [tests/test_study_integration.py](tests/test_study_integration.py)

Tests cover:
- New cards are counted properly
- After "Good" answer, card becomes learning with future due_at
- After graduating from learning, card gets due_day set

**Run**:
```bash
python -m unittest tests.test_study_integration -v
```

**Result**: ✅ 3/3 tests pass

---

## Acceptance Criteria (All Met)

### ✅ Test A: Learning steps display Learn count
- New card answered "Good"
- Card becomes learning with due_at = now + 10m
- Dashboard immediately shows: LearnCount += 1, NewCount -= 1

### ✅ Test B: Due review cards display Due count
- Review card with due_day = today
- Dashboard shows: DueCount >= 1
- After studying → DueCount correct

### ✅ Test C: Persistence across reload
- Restart app / reload page
- Counters remain correct (DB-backed, not RAM state)

---

## Deployment Steps

1. **Backup database** (optional but recommended)
   ```bash
   mysqldump -u[user] -p[pass] nihongo > backup.sql
   ```

2. **Apply migration**
   ```bash
   flask db upgrade
   ```

3. **Restart app**
   ```bash
   python wsgi.py
   # or
   flask run
   ```

4. **Verify counters work**
   - Study a few cards in a deck
   - Check Home dashboard
   - Counters should update immediately when returning

---

## Backward Compatibility

✅ **Fully backward compatible**

- Old records without `due_day` column still work
- `_card_state_from_progress()` calculates `due_day` on-the-fly if missing
- Next time those cards are answered, `due_day` gets populated

---

## Performance Impact

**Minimal**:
- Additional column `due_day` is indexed (no query slowdown)
- Two extra function calls per entry in dashboard (`_day_index` calls)
- These are O(1) operations (simple arithmetic on datetime)

---

## Next Steps / Future Improvements

1. **Suspend/Buried cards**: Exclude from counters (not yet implemented)
2. **Daily limits**: If deck has new limit, reduce NewCount accordingly
3. **Caching**: Cache dashboard counters with 1-min TTL for high-traffic sites
4. **API Endpoint**: Add `/api/deck/<id>/stats` for real-time updates

---

## Related Files
- Scheduler: [app/services/anki_scheduler.py](app/services/anki_scheduler.py)
- Study routes: [app/routes/vocabulary.py](app/routes/vocabulary.py)
- Models: [models/vocabulary_progress.py](models/vocabulary_progress.py)
- Models: [models/vocabulary_structure.py](models/vocabulary_structure.py)

