# shuck-shells

`shuck-shells` is the source repo for the shell archive index consumed by `shuck run`.

It owns:

- release assets for shell archives
- generated registry JSON documents under `registry/`
- CI workflows that build and publish Bash release archives
- automation to refresh that index from releases
- GitHub Pages publication for the generated JSON

## Release conventions

Releases are discovered from this repo's GitHub releases.

- release tag: `<shell>-<version>`
- archive asset: `<shell>-<version>-<platform>.tar.gz`

Examples:

- `bash-5.2.21`
- `zsh-5.9`
- `bash-5.2.21-x86_64-linux-gnu.tar.gz`

Supported shells:

- `bash`
- `zsh`
- `dash`
- `mksh`

Supported platforms:

- `x86_64-linux-gnu`
- `aarch64-linux-gnu`
- `x86_64-linux-musl`
- `aarch64-linux-musl`
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
    "x86_64-linux-gnu": {
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

## Building Bash archives

`shuck-shells` builds and publishes Bash archives itself from the official GNU source tarballs.

- workflow: `.github/workflows/build-bash-release.yml`
- trigger: manual `workflow_dispatch`
- source tarball: `https://ftp.gnu.org/pub/gnu/bash/bash-<version>.tar.gz`
- published asset names:
  - `bash-<version>-x86_64-linux-gnu.tar.gz`
  - `bash-<version>-aarch64-linux-gnu.tar.gz`
  - `bash-<version>-x86_64-linux-musl.tar.gz`
  - `bash-<version>-aarch64-linux-musl.tar.gz`
  - `bash-<version>-x86_64-darwin.tar.gz`
  - `bash-<version>-aarch64-darwin.tar.gz`

The workflow currently builds on these GitHub-hosted runner labels:

- `ubuntu-22.04`
- `ubuntu-22.04-arm`
- `macos-15-intel`
- `macos-15`

The release tag format stays `<shell>-<version>`, so a Bash build for `5.2.21` publishes or updates the release tag `bash-5.2.21`.

The Linux matrix intentionally splits glibc and musl:

- `*-linux-gnu` archives are built natively on Ubuntu 22.04 runners, so their runtime compatibility follows that glibc baseline.
- `*-linux-musl` archives are built inside Alpine and target musl-based systems.

## Automation

- `refresh-index.yml` regenerates the checked-in registry tree nightly and opens or updates a PR if it changes.
- `refresh-index.yml` also runs automatically when a new shell release is published.
- `validate.yml` validates the JSON schema, canonical ordering, and script tests on PRs and `main`.
- `publish-pages.yml` publishes the merged `registry/` tree to GitHub Pages.

The published endpoint for v1 is:

- `https://<owner>.github.io/shuck-shells/index.json`

## Required secrets

The automation uses one GitHub App installation with these repository secrets:

- `SHUCK_SHELLS_APP_ID`
- `SHUCK_SHELLS_APP_INSTALLATION_ID`
- `SHUCK_SHELLS_APP_PRIVATE_KEY`

The workflows mint a short-lived installation token at runtime from those values. This setup intentionally does not require PR approvals on `main`. The nightly workflow opens or updates the refresh PR, and the validation workflow enables auto-merge after the required checks pass.

The app only needs repository access to `shuck-shells` with:

- `Contents: Read & write`
- `Pull requests: Read & write`
