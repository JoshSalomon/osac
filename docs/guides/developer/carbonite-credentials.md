# Carbonite sandbox credentials (GitHub, Jira and Codex)

The Carbonite sandbox never holds real tokens. OpenShell keeps them in the
gateway as *providers*. The sandbox environment contains opaque placeholders
(for example `openshell:resolve:env:...`), and the OpenShell proxy swaps in the
real value on requests to the endpoints named in the provider's *profile*.
Do not pass tokens with `CARBONITE_CREATE_ARGS='--env ...'`: that would put
them in the sandbox specification.

A token reaches a request only when both checks pass: the sandbox network
policy allows the binary and destination, and the profile's endpoints cover
the host, port and path. This repository ships profiles for `gh` and `jira` in
`tools/carbonite/providers/`.

## One-time setup (per gateway workspace)

Profiles and providers live in the gateway, so they survive sandbox
rebuilds. Run these on the host, with the same gateway and workspace the
Makefile uses (`openshell` and `osac-kind` by default).

1. Import the GitHub profile, and the Jira profile after rendering your Jira
   host into it. The shipped Jira profile holds the reserved placeholder
   `jira.internal.example`; keep the rendered copy outside the repository:

   ```bash
   G="openshell --gateway openshell --workspace osac-kind"
   STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/osac-carbonite-kind"
   mkdir -p "$STATE_DIR/providers"

   $G profile import -f tools/carbonite/providers/osac-github.yaml

   CARBONITE_JIRA_HOST=<your-jira-host> tools/carbonite/render-policy.sh \
     tools/carbonite/providers/osac-jira.yaml \
     "$STATE_DIR/providers/osac-jira.yaml"
   $G profile import -f "$STATE_DIR/providers/osac-jira.yaml"
   ```

2. Create one provider per profile. A `--credential` key with no value reads
   the token from your environment, so it never appears on a command line.
   Use single quotes if you type a token (double quotes let the shell
   interpret it, and any quote characters would become part of the token):

   ```bash
   export GITHUB_TOKEN='<github token>'
   export JIRA_API_TOKEN='<jira api token>'

   $G provider create --name osac-github --type osac-github \
     --credential GITHUB_TOKEN
   $G provider create --name osac-jira --type osac-jira \
     --credential JIRA_API_TOKEN

   unset GITHUB_TOKEN JIRA_API_TOKEN
   ```

   Use an unscoped Jira Cloud API token (id.atlassian.com, Security, API
   tokens). Scoped tokens do not work with basic auth against the site URL.
   Jira tokens inherit your Jira permissions and cannot be narrowed; for
   GitHub, prefer a fine-grained token limited to the repositories you need.

3. Make new sandboxes pick the providers up by exporting this, for example
   from your shell profile:

   ```bash
   export CARBONITE_PROVIDERS="osac-github osac-jira"
   ```

To rotate a token later, export it and run
`$G provider update osac-jira --credential JIRA_API_TOKEN --wait`.

## Every sandbox creation (automatic)

- `CARBONITE_PROVIDERS` attaches each listed provider when `make enter-carb`
  or `make rebuild-carb` creates the sandbox. Attachments belong to one
  sandbox and are revoked when it is deleted, so this is what keeps them
  across rebuilds.
- If `jira-cli` is configured on the host, creation also copies its config
  (`$JIRA_CONFIG_FILE`, else `~/.config/.jira/.config.yml`) to
  `/sandbox/.config/.jira/.config.yml`, so `jira init` is not needed in the
  sandbox. Set `CARBONITE_JIRA_CONFIG` to use another file. The config holds
  the server and login, not the token. The copy is refused before the sandbox
  is created if the file looks like it contains a credential, and a failed
  copy only prints a warning.

For a sandbox that already exists, attach by hand, one provider per call, and
open a new shell inside it (credentials only reach new processes):

```bash
$G sandbox provider attach --wait osac-carbonite-kind osac-github
$G sandbox provider attach --wait osac-carbonite-kind osac-jira
```

## Codex

Codex ships in the image (`@openai/codex`, pinned by the `CODEX_VERSION` build
arg). Authenticate with an API key. Device-code sign-in is **not permitted** by
the OpenAI enterprise licence:

```bash
read -rs OPENAI_API_KEY; export OPENAI_API_KEY
printenv OPENAI_API_KEY | codex login --with-api-key
codex login status
unset OPENAI_API_KEY
```

Do not run a bare `codex login` (ChatGPT sign-in) or `codex login
--device-auth`. Credentials are written to `~/.codex/auth.json` inside the
sandbox, which is not one of the mounted volumes, so repeat the login after
`make rebuild-carb`. Wiring Codex to an OpenShell provider, as GitHub and Jira
are, would remove that step.

## Troubleshooting

- **`gh auth status` says not logged in, or Jira returns 401, right after a
  rebuild:** the providers were not attached. Check
  `$G sandbox provider list osac-carbonite-kind`.
- **Attach fails with "not in a state required for the operation":** read the
  gateway log (`journalctl --user -u openshell-gateway`). A message such as
  `rejecting uninspected credentialed endpoint` means a profile endpoint is
  covered by a sandbox policy rule with no `protocol`, so it is L4-only.
  Remove the endpoint from the profile or give the policy rule a `protocol`.
- **Jira `permission denied` on connect:** the policy does not allow the host
  or the binary. `$G logs osac-carbonite-kind` shows the denied connection.
- **Jira 401 with the provider attached:** check the stored token has no
  literal quote characters and is an unscoped token. Compare a request made
  with `curl -u "<email>:<token>"` on the host with one made from the sandbox.
