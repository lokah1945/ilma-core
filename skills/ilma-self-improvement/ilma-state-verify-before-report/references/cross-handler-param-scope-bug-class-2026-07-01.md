# Cross-Handler Parameter Scope Bug Pattern (2026-07-01)

## The class of bug

You patch one function/method to reference a parameter that is in scope at
the **call site** (e.g. an outer function's parameter or a captured closure
var), but the modified function/method **itself** doesn't declare that
parameter. The result is a `ReferenceError` at runtime, even though
`node -c` syntax check passes — because the reference is **lexically legal**
in JavaScript (closure capture).

## Why static checks miss it

JavaScript closures can see outer-scope identifiers:

```js
async function acquire(model, signal, reqBody) {
  // ← reqBody is in scope here
  const priority = classifyPriority({ body: reqBody });  // works
  const [chosen, ...] = await this.acquireSlot(model, signal, priority);
  //  ↑ acquireSlot does NOT declare reqBody
  //    But if it references `reqBody.X` inside, that's a ReferenceError
  //    because the inner function's scope doesn't see outer's params
  //    UNLESS captured via explicit param passing.
}
```

`node -c` only checks syntax. Lexically legal. Runtime blows up.

## Why some callers fail and others succeed

Same inner function, multiple call sites, different arg-counts:

```js
// Caller 1 (chat completions):
const r = await acquire('model-A', signal, body);     // 3 args ✓
// Caller 2 (proxyPost — embeddings/images etc):
const r = await acquire('model-A', signal);            // 2 args — reqBody=undefined
// Caller 3 (catchAll):
const r = await acquire('model-A', signal, body);      // mixed
```

Even if `acquireSlot` was patched to read `reqBody.__reqId` — only the 3-arg
callers provide the binding; 2-arg callers cause `ReferenceError`.

## Detection recipe (after any patch adds an unqualified identifier)

```bash
# 1. Confirm the patched function has the param in ITS OWN signature:
grep -nP "^  async (\w+)?\s*\(.*\)" src/key_pool.js | grep acquireSlot

# 2. Find all callsites of the function:
grep -nE "acquire\s*\(" src/*.js

# 3. Compare argument counts at each callsite against the signature.
#    Any callsite with FEWER args than the signature = failure case.
```

## Mitigation when the bug fires

Add defensive defaulting **at the function body top**, not at call sites:

```js
const safeBody = (typeof reqBody === 'object' && reqBody) || {};
const rb = (typeof reqBody === 'object' && reqBody) || {};
```

This costs ~60 bytes per function and turns silent ReferenceError into
graceful degradation. Always pair it with the actual fix (pass-through via
signature).

## Fix recipe (correct version)

Either:

a) Add the param to the inner function's signature:
```js
async acquireSlot(model=null, signal=null, priority=DEFAULT_PRIORITY, reqBody=null) {
  // ...
  const rb = (typeof reqBody === 'object' && reqBody) || {};
  // ...use rb.__reqId...
}
```

b) OR pass it explicitly via capture at the outer scope:
```js
const rb = reqBody;  // bound at outer acquire()
const [chosen, ...] = await this.acquireSlot(model, signal, priority);
// inner acquireSlot closure sees `rb` via lexical scoping
```

## Why this is a CLASS, not isolated typo

Once you make this mistake in one place during a non-trivial patch-set,
**you've made it in 2-4 other functions in the same patch-set** because
the author (you) was thinking about the OUTER-scope contract, not the
INNER-function's signature, throughout the edits.

After fixing the FIRST instance, grep the whole patch for siblings:

```bash
git diff <patched-files> | grep -nE '^\+.*\b(outerParam)\.' | head -20
# Then for each occurrence, check the inner function's own signature.
```

## Original bug (PHASE 3 attempt, 2026-07-01)

```js
// In src/key_pool.js after patch:
async acquire(model, signal, reqBody) {            // ← reqBody PARAM DECLARED
  const priority = classifyPriority({ body: reqBody });
  // ...
  const [chosen, ...] = await this.acquireSlot(model, signal, priority);
  //                                  ↑
  //     acquireSlot signature was: (model=null, signal=null, priority=...)
  //     acquireSlot body now refers to: this._waiting.set(myTicket, {...requestId: reqBody.__reqId...})
  //     ↑ FAILS for 2-arg callers (proxyPost) because acquireSlot's own
  //       scope has no reqBody declared.
  return { key: chosen, ... };
}
```

Symptom in runtime log:
```
[ERROR] reqBody is not defined
```

The fix: defensive defaulting inside `acquireSlot` (`const rb = ...`).
A defensive blocking of `acquire()` callers would also work but breaks
the existing 2-arg API contracts.

## Related class: "I patched `acquire()` sig, but a sibling function still uses old sig"

Same family. When changing a function's signature:

```js
// Before:
async acquire(model, reqBody /* legacy 2-arg */) { ... }

// After (intended):
async acquire(model, signal, reqBody /* 3-arg */) { ... }
```

A sibling function that still calls `acquire('x', body)` will now
spread `body` into the `signal` arg (a Promise that's not undefined).
Catch this BEFORE commit by:

```bash
grep -nE "\.acquire\s*\(" src/*.js | awk -F'[()]' '{print $2}' \
  | xxd | head
# Compare comma-counts vs the new signature.
```

Or: write a tiny smoke runner that calls each callsite with a small
fixture and confirms a meaningful error.

## Universal test for any "I changed X's contract" patch

```js
// In test/sigs.js (run before declaring patch complete)
for (const callsite of CALLERS_OF_X) {
  try {
    X(...extractArgs(callsite));
    console.log('OK', callsite.file, callsite.line);
  } catch (e) {
    if (e.name === 'TypeError' || /is not (a function|defined)/.test(e.message)) {
      console.error('SIG MISMATCH', callsite, e.message);
    }
  }
}
```

If even one SIG MISMATCH appears, do NOT commit. Fix the inner function
defaulting first, then re-run.
