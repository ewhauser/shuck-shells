# shuck-shells

`shuck-shells` is the source repo for the shell archive index consumed by `shuck run`.

It owns:

- release assets for shell archives
- generated registry JSON documents under `registry/`
- automation to refresh that index from releases
- GitHub Pages publication for the generated JSON

## Release conventions

Releases are discovered from this repo's GitHub releases.

- release tag: `<shell>-<version>`
- archive asset: `<shell>-<version>-<platform>.tar.gz`

Examples:

- `bash-5.2.21`
- `zsh-5.9`
- `bash-5.2.21-x86_64-linux.tar.gz`

Supported shells:

- `bash`
- `zsh`
- `dash`
- `mksh`

Supported platforms:

- `x86_64-linux`
- `aarch64-linux`
- `x86_64-darwin`
- `aarch64-darwin`

## Published format

The registry uses a Terraform-style hierarchy:

- root discovery document: `registry/index.json`
- per-shell versions document: `registry/shells/<shell>/index.json`
- per-version manifest: `registry/shells/<shell>/<version>.json`

Root discovery document:

```json
{
  "version": 2,
  "kind": "shuck.shells.index",
  "shells": {
    "bash": {
      "versions_url": "shells/bash/index.json"
    }
  }
}
```

Per-shell versions document:

```json
{
  "version": 2,
  "kind": "shuck.shells.versions",
  "shell": "bash",
  "versions": {
    "5.2.21": {
      "manifest_url": "5.2.21.json"
    }
  }
}
```

Per-version manifest:

```json
{
  "version": 2,
  "kind": "shuck.shells.release",
  "shell": "bash",
  "release": "5.2.21",
  "platforms": {
    "x86_64-linux": {
      "url": "https://...",
      "sha256": "..."
    }
  }
}
```

## Local development

Validate the checked-in index and the generator logic:

```bash
python3 scripts/validate_index.py registry
python3 -m unittest discover -s tests
```

Rebuild the checked-in index from live releases in the current repository:

```bash
python3 scripts/build_index.py --output-dir registry
```

That mode uses `GITHUB_REPOSITORY` by default, or `--repo owner/name` to override it.

## Automation

- `refresh-index.yml` regenerates the checked-in registry tree nightly and opens or updates a PR if it changes.
- `validate.yml` validates the JSON schema, canonical ordering, and script tests on PRs and `main`.
- `publish-pages.yml` publishes the merged `registry/` tree to GitHub Pages.

The published endpoint for v1 is:

- `https://<owner>.github.io/shuck-shells/index.json`

## Required secrets

The automation uses one GitHub App installation with these repository secrets:

- `SHUCK_SHELLS_APP_ID`
- `SHUCK_SHELLS_APP_INSTALLATION_ID`
- `SHUCK_SHELLS_APP_PRIVATE_KEY`

The local setup script can read the private key either from `SHUCK_SHELLS_APP_PRIVATE_KEY` directly or from a file path via `SHUCK_SHELLS_APP_PRIVATE_KEY_FILE`.

The workflows mint a short-lived installation token at runtime from those values. This setup intentionally does not require PR approvals on `main`. The nightly workflow opens or updates the refresh PR, and the validation workflow enables auto-merge after the required checks pass.

The app only needs repository access to `shuck-shells` with:

- `Contents: Read & write`
- `Pull requests: Read & write`
