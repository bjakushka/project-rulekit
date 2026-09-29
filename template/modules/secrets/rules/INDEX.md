## Secrets: what must never be written into the project

- Access secrets (passwords, tokens, keys, full card or account numbers, full 
  routable IPs, complete connection strings) do not belong in this project at 
  all - not in tracked files, not in gitignored ones
- Keep them in a secrets manager and reference them by name when you must 
  mention them
- Private RFC1918 addresses and masked references to public IPs, serials, and
  similar values may appear openly in tracked notes
- Do not combine otherwise allowed details into a complete connection recipe.
  A tracked file must not contain enough information to initiate access without
  consulting the secrets manager
