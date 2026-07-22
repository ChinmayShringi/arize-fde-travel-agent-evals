# Prompt Caching: Implementation + Measured Result

Env-gated Anthropic prompt caching in `agent/loop.py`, gated by `PROMPT_CACHE=1`
(default off). Measured with two fresh same-day full-golden-dataset runs.

## Implementation (agent/loop.py)

- Gate: `PROMPT_CACHE=1`. Default/unset path is byte-identical to the shipped
  agent: `system=SYSTEM_PROMPT` (plain str), `tools=TOOLS` (bare list).
- When on (per anthropic SDK 0.116.0 types, read from `.venv/.../anthropic/types/`):
  - `system` becomes a one-element list of `TextBlockParam` with
    `cache_control={"type": "ephemeral"}` on the last (only) block
    (`text_block_param.py` exposes `cache_control`).
  - the last tool gets `cache_control={"type": "ephemeral"}`
    (`tool_param.py` exposes `cache_control`). The shared `TOOLS` list is never
    mutated (a new list of new dicts is built).
- Usage fields confirmed on `anthropic/types/usage.py`:
  `cache_read_input_tokens`, `cache_creation_input_tokens`.
- Additive root-span attributes, cache-only, summed across every turn:
  `llm.cache_read_tokens`, `llm.cache_creation_tokens`.

## Self-test (offline, monkeypatched messages.create)

    DEFAULT-OFF byte-identical to HEAD kwargs: True
      system type: str | repr==HEAD: True
      tools identical to TOOLS: True
    ON system cache_control on last text block: True
    ON tools cache_control on last tool only: True
    Shared TOOLS list NOT mutated: True
    Usage exposes cache_read_input_tokens/cache_creation_input_tokens: True
    ALL SELF-TESTS PASS: True

## Two measured runs (full golden dataset, 31 conversations / 33 turns / 57 LLM calls)

| run | PROMPT_CACHE | turns | errors | eval behavior |
|-----|--------------|-------|--------|---------------|
| control-v0-cachetest | unset | 33 | 0 | identical |
| control-v0-cached    | 1     | 33 | 0 | identical |

`cache_control` was ACCEPTED by the API at SDK 0.116.0 (both runs completed, 0
errors, eval rates identical). It was NOT rejected.

### Billed-token comparison (from spans.jsonl `llm.token_count.*`)

Anthropic 5m prompt-cache pricing multipliers (documented, not carried in SDK
types): cache write = 1.25x base input, cache read = 0.10x base input.
billed_input = uncached_input + 0.10*cache_read + 1.25*cache_write.

| metric | control (off) | cached (on) |
|--------|--------------:|------------:|
| LLM calls | 57 | 57 |
| prompt (input, total) | 66648 | 66834 |
| uncached input | 66648 | 66834 |
| cache_read tokens | 0 | 0 |
| cache_write tokens | 0 | 0 |
| output tokens | 8496 | 8656 |
| billed input (token-eq) | 66648.0 | 66834.0 |

Measured billed-input savings: -0.28% (i.e. ~0). The small delta is haiku
run-to-run nondeterminism (different tool-call paths), not a caching effect:
both runs recorded 0 cache reads and 0 cache writes.

## Root cause of 0% savings (measured, not assumed)

The cacheable prefix (system + tools) is 1031 tokens (measured via
`messages.count_tokens` on `claude-haiku-4-5`). Anthropic's minimum cacheable
prompt length for Haiku models is 2048 tokens. 1031 < 2048, so the API accepts
the `cache_control` breakpoints but creates no cache entry -> zero cache
reads/writes on every turn -> zero real savings.

    MODEL: claude-haiku-4-5
    system+tools+1char-msg input tokens: 1031
    prefix below minimum -> 1031 < 2048 = True

## Conclusion

The caching plumbing is correct and API-accepted, but on the SHIPPED agent
(haiku-4-5, ~1031-token system+tools prefix) prompt caching yields 0% savings
because the prefix is below the model's minimum cacheable length. Caching only
starts paying off once the cached prefix exceeds 2048 tokens (e.g. a much larger
system prompt / tool set, more tools, or few-shot examples pinned into the
prefix), or on a model with a 1024-token minimum (Sonnet/Opus). The `PROMPT_CACHE`
gate and per-turn cache-token span attributes are in place to measure that the
moment the prefix crosses the threshold.
