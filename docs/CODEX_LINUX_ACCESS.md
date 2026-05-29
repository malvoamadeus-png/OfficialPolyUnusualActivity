# Codex Linux Access

This project uses the same Linux server access as the existing local Jibai
setup, but the Codex MCP server is configured in the current Windows user:

```text
C:\Users\A\.codex\config.toml
```

## Connection

- Host alias: `jibai-prod`
- MCP server name: `ssh-prod`
- Actual host: `47.76.243.147`
- User: `root`
- Windows key path: `C:\Users\A\.ssh\id_ed25519`
- WSL fallback key path: `~/.ssh/id_ed25519_prod`

The MCP server is registered as:

```toml
[mcp_servers.ssh-prod]
command = "npx"
args = ["-y", "ssh-mcp", "--", "--host=jibai-prod"]
```

New Codex sessions should discover `ssh-prod` automatically. Already-open
sessions may need a restart before the tool appears.

## Fallback SSH

If the MCP tool is not visible in a session, direct SSH works from WSL:

```bash
ssh -i ~/.ssh/id_ed25519_prod \
  -o BatchMode=yes \
  -o ConnectTimeout=20 \
  -o StrictHostKeyChecking=accept-new \
  root@47.76.243.147 "hostname && uptime"
```

Prefer read-only checks before changing server state. Never print secrets from
remote `.env` files.
