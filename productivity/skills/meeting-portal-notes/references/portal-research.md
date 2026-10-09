# Adaptive Portal research

The helper finds the Portal from the owner settings: `portal_mcp_config` names the MCP config file and `portal_server` the server in it (default `insights-portal`). The token is `INSIGHTS_PORTAL_ASSISTANT_TOKEN`, else the config's Authorization header with any `${VAR}` read from the environment. It never prints the endpoint or the token, uses HTTPS (plain HTTP only to localhost), blocks redirects, permits only named read tools and saves dated responses.

Write tool arguments into a JSON file, then run:

```sh
python3 <skill>/scripts/portal_read.py search --args query.json --output search-receipt.json
```

Useful argument shapes:

- `search`: `{"query":"company or project keyword","limit":20}`
- `get`: `{"entity_type":"contact","id_or_query":"email or ID","detail":"full"}` Also supports company, project, task, note and meeting. Natural keys can be ambiguous; inspect search results rather than choosing an arbitrary match.
- `list_entities`: `{"entity_type":"task","filters":{"project_id":"ID","include_completed":false},"limit":100,"offset":0}`
- `list_entities`: `{"entity_type":"note","filters":{"entity_type":"project","entity_id":"ID"},"limit":100,"offset":0}`
- `get` a task/note/project by ID for details, not just search excerpts.

Inspect the response envelope and paginate with `next_offset` where supplied. An empty or failed lookup means unavailable evidence, not that a person/task cannot exist. Record what you searched and why you stopped. Avoid sweeping unrelated private material into a meeting artifact.

Start from the participants and concrete work named in the transcript. Follow company/project links from hydrated contacts and projects. Check candidate tasks against the exact action and check last-updated/source metadata. Existing notes may provide background, but previous model notes of the same meeting are not independent evidence of what happened. Current task completion can change today's catalog recommendation without rewriting the historical commitment.
