# Compatibility

Auto Agent defines an interoperable routing policy, not a cross-vendor control plane. A host may implement some, all, or none of the recommended controls.

| Host or integration | Routing recommendation | Apply settings | Tool / agent controls | Required fallback |
| --- | --- | --- | --- | --- |
| ChatGPT / Codex consumer UI | Yes | Usually no | Host-defined | `recommend_only` |
| OpenAI API orchestrator | Yes | When trusted runtime metadata confirms controls | When host authorizes them | `recommend_only` for unknown or mismatched metadata |
| Claude consumer UI | Yes | Usually no | Host-defined | `recommend_only` |
| Anthropic API orchestrator | Yes | When trusted runtime metadata confirms controls | When host authorizes them | `recommend_only` for unknown or mismatched metadata |
| Gemini consumer UI | Yes | Usually no | Host-defined | `recommend_only` |
| Gemini API orchestrator | Yes | When trusted runtime metadata confirms controls | When host authorizes them | `recommend_only` for unknown or mismatched metadata |
| Other compatible host | Yes | Only after adapter review and verification | Only after host authorization | `recommend_only` |

Supported adapter metadata and its expiry rules are documented in [references/platform-adapters.md](references/platform-adapters.md). Missing, expired, mismatched, or unavailable adapters are not errors; they are a deliberate no-change condition.

## Version support

- Runtime validator: CPython 3.11, 3.12, and 3.13.
- Development checks: GitHub-hosted Ubuntu runners with Python, Ruby, hash-locked analyzers, and a checksum-verified Actionlint binary. These tools are not runtime requirements.
- Package format: hosts that recognize `SKILL.md`; `agents/openai.yaml` is optional metadata for hosts that support it.

No compatibility statement promises a specific vendor model, pricing tier, latency, tool, browsing capability, or UI control.
