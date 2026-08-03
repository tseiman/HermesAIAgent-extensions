# codexusage — Hermes plugin

Shows your OpenAI/Codex plan usage (5h + weekly rate limit, credits, limit status)
as a `/codexusage` slash command inside [Hermes Agent](https://github.com/NousResearch/hermes-agent),
with a compact ASCII progress bar.

## Why

Hermes runs continuously and keeps its OpenAI/Codex OAuth token fresh in
`~/.hermes/auth.json`, even when you don't have the `codex` CLI open. This
plugin reuses that token instead of requiring a separate `codex login` /
`codex status` session, so usage is checkable at any time from within Hermes.

## Example output

```
/codexusage

Plan: plus   |   Limit reached: no   |   Requests allowed: yes

7d-Limit   [##########--------------]  43.0%   Reset in 4d 4h 26m

Credits: 1043.9529000000
```

`/codexusage json` prints the raw API response instead.

## Installation

```bash
mkdir -p ~/.hermes/plugins/codexusage
cp codexusage_plugin.yaml ~/.hermes/plugins/codexusage/plugin.yaml
cp codexusage_init.py     ~/.hermes/plugins/codexusage/__init__.py
hermes plugins enable codexusage
# restart hermes, then run: /codexusage
```

No extra dependencies — pure Python standard library (`urllib`, `json`, `base64`).

## How it works

1. Reads the OpenAI/Codex `access_token` from `~/.hermes/auth.json`
   (`providers.openai-codex.tokens.access_token`, falling back to `credential_pool`).
2. Decodes the JWT payload locally to read the `chatgpt_account_id` claim
   (`https://api.openai.com/auth.chatgpt_account_id`) — no signature verification, just claim extraction.
3. Calls `GET https://chatgpt.com/backend-api/wham/usage` with that token/account id.
4. Formats `rate_limit.primary_window` / `secondary_window`, `plan_type`,
   `limit_reached`, and `credits.balance` into a short report.

## Limitations

- **Unofficial API.** `/backend-api/wham/usage` is not a documented/public
  OpenAI endpoint — it's the same one the ChatGPT/Codex UI uses internally.
  It can change or break without notice.
- **No token refresh.** The plugin only reads the current token; it doesn't
  refresh an expired one. Relies on Hermes (or `codex login`) keeping
  `auth.json` up to date. Expired token → `chatgpt_account_id` extraction
  or the HTTP call fails with a clear error message.
- **Window labeling is a heuristic.** 5h vs. weekly vs. other windows are
  inferred from `limit_window_seconds`, not an explicit field name.
- Tested against the `openai-codex` / `chatgpt` auth mode only (not API-key mode).

## License

MIT (adjust as needed).
