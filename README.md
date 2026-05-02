# shuck-shells

`shuck-shells` is the source repo for the shell archive index consumed by `shuck run`.

It owns:

- release assets for shell archives
- shell source metadata in `shells.json`
- generated registry JSON documents under `registry/`
- CI workflows that build and publish shell release archives
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
python3 scripts/discover_upstream_versions.py --pretty --repo owner/name
bash -n scripts/build_shell_release.sh
bash -n scripts/build_bash_release.sh
bash -n scripts/build_dash_release.sh
bash -n scripts/build_mksh_release.sh
bash -n scripts/build_zsh_release.sh
```

Rebuild the checked-in index from live releases in the current repository:

```bash
python3 scripts/build_index.py --output-dir registry
```

That mode uses `GITHUB_REPOSITORY` by default, or `--repo owner/name` to override it.

## Shell catalog

`shells.json` is the planning seam for where release assets come from.

Each shell entry declares:

- a display name
- a `release_source.kind`
- for buildable shells, the builder script used by the release workflow
- upstream discovery metadata for automatic version detection

Today, all cataloged shells are `build` shells:

- `bash`
- `dash`
- `mksh`
- `zsh`

The catalog still preserves the source-kind seam, so later shells can come from a different source path without changing the registry model.

## Building shell archives

`shuck-shells` currently builds and publishes `bash`, `dash`, `mksh`, and `zsh` archives itself from upstream source tarballs.

- workflow: `.github/workflows/build-shell-release.yml`
- trigger: manual `workflow_dispatch`
- inputs:
  - `shell`
  - `version`

The workflow only builds shells whose `release_source.kind` is `build`. If a later shell is cataloged under another source kind, the workflow fails fast instead of pretending to support it.

Current buildable shells:

- `bash`
  - builder: `scripts/build_bash_release.sh`
  - source tarball: `https://ftp.gnu.org/pub/gnu/bash/bash-<version>.tar.gz`
- `dash`
  - builder: `scripts/build_dash_release.sh`
  - source tarball: `https://gondor.apana.org.au/~herbert/dash/files/dash-<version>.tar.gz`
- `mksh`
  - builder: `scripts/build_mksh_release.sh`
  - source tarball: `https://mbsd.evolvis.org/MirOS/dist/mir/mksh/mksh-<version>.tgz`
  - version format: upstream release names include the leading `R`, for example `R59c`
- `zsh`
  - builder: `scripts/build_zsh_release.sh`
  - source tarball: `https://downloads.sourceforge.net/project/zsh/zsh/<version>/zsh-<version>.tar.xz`

Published asset names follow the same convention for every shell:

- `<shell>-<version>-x86_64-linux-gnu.tar.gz`
- `<shell>-<version>-aarch64-linux-gnu.tar.gz`
- `<shell>-<version>-x86_64-linux-musl.tar.gz`
- `<shell>-<version>-aarch64-linux-musl.tar.gz`
- `<shell>-<version>-x86_64-darwin.tar.gz`
- `<shell>-<version>-aarch64-darwin.tar.gz`

The workflow currently builds on these GitHub-hosted runner labels:

- `ubuntu-22.04`
- `ubuntu-22.04-arm`
- `macos-15-intel`
- `macos-15`

The release tag format stays `<shell>-<version>`, so:

- a Bash build for `5.2.21` publishes or updates `bash-5.2.21`
- a dash build for `0.5.13.2` publishes or updates `dash-0.5.13.2`
- an mksh build for `R59c` publishes or updates `mksh-R59c`
- a Zsh build for `5.9` publishes or updates `zsh-5.9`

The Linux matrix intentionally splits glibc and musl:

- `*-linux-gnu` archives are built natively on Ubuntu 22.04 runners, so their runtime compatibility follows that glibc baseline.
- `*-linux-musl` archives are built inside Alpine and target musl-based systems.

## Automation

- `refresh-index.yml` regenerates the checked-in registry tree nightly and opens or updates a PR if it changes.
- `discover-upstream.yml` checks upstream release pages nightly and dispatches `build-shell-release.yml` for any missing latest shell releases.
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
