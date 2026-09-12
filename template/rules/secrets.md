## Secrets: what must never be written into the project

- Access secrets (passwords, tokens, keys, full card or account numbers, full 
  routable IPs, complete connection strings) do not belong in this project at 
  all - not in tracked files, not in gitignored ones
- Keep them in a secrets manager and reference them by name when you must 
  mention them
- Masked references are fine in tracked notes when they help connect context: 
  first and last octets, serial tails, token tails
