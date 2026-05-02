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

Releases are discovered from:

- this repo's GitHub releases for shells built by `shuck-shells`
- configured external GitHub releases for shells sourced from other repos

- release tag: `<shell>-<version>`
- archive asset: `<shell>-<version>-<platform>.tar.gz`

Examples:

- `bash-5.2.21`
- `zsh-5.9`
- `bash-5.2.21-x86_64-linux-gnu.tar.gz`

Supported shells:

- `bash`
- `bashkit`
- `busybox`
- `zsh`
- `dash`
- `gbash`
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
bash -n scripts/build_busybox_release.sh
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
- for GitHub-release shells, the upstream repo plus tag and asset matching rules
- upstream discovery metadata for automatic version detection

Current release sources:

Build-from-source shells:
- `bash`
- `busybox`
- `dash`
- `mksh`
- `zsh`

GitHub-release shells:
- `bashkit` from `everruns/bashkit`
- `gbash` from `ewhauser/gbash`

The catalog drives both paths, so the registry can mix repo-built shells with externally released shells without changing the published JSON format.

## Building shell archives

`shuck-shells` currently builds and publishes `bash`, `busybox`, `dash`, `mksh`, and `zsh` archives itself from upstream source tarballs.

- workflow: `.github/workflows/build-shell-release.yml`
- trigger: manual `workflow_dispatch`
- inputs:
  - `shell`
  - `version`

The workflow only builds shells whose `release_source.kind` is `build`. If a later shell is cataloged under another source kind, the workflow fails fast instead of pretending to support it.

The workflow also performs a release preflight check before starting the matrix:

- if the `<shell>-<version>` release does not exist yet, it builds the shell's supported platform archives
- if the release exists but is missing one or more expected supported-platform assets, it rebuilds and republishes the version
- if the release already has the full expected asset set, it exits before running the build matrix

Current buildable shells:

- `bash`
  - builder: `scripts/build_bash_release.sh`
  - source tarball: `https://ftp.gnu.org/pub/gnu/bash/bash-<version>.tar.gz`
- `busybox`
  - builder: `scripts/build_busybox_release.sh`
  - source tarball: `https://busybox.net/downloads/busybox-<version>.tar.bz2`
  - runtime packaging: wraps the BusyBox binary so `bin/busybox` runs the bundled `sh` applet
  - supported platforms: Linux only (`*-linux-gnu`, `*-linux-musl`)
- `dash`
  - builder: `scripts/build_dash_release.sh`
  - source archive: `https://kernel.googlesource.com/pub/scm/utils/dash/dash/+archive/refs/tags/v<version>.tar.gz`
  - discovery source: `https://kernel.googlesource.com/pub/scm/utils/dash/dash/`
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
- a BusyBox build for `1.37.0` publishes or updates `busybox-1.37.0`
- a dash build for `0.5.13.2` publishes or updates `dash-0.5.13.2`
- an mksh build for `R59c` publishes or updates `mksh-R59c`
- a Zsh build for `5.9` publishes or updates `zsh-5.9`

The Linux matrix intentionally splits glibc and musl:

- `*-linux-gnu` archives are built natively on Ubuntu 22.04 runners, so their runtime compatibility follows that glibc baseline.
- `*-linux-musl` archives are built inside Alpine and target musl-based systems.

## External GitHub releases

Some shells are indexed directly from their own GitHub releases instead of being built in this repo.

Current GitHub-release shells:

- `bashkit`
  - repo: `everruns/bashkit`
  - tag format: `v<version>`
  - indexed assets: Darwin tarballs plus Linux GNU tarballs when present
- `gbash`
  - repo: `ewhauser/gbash`
  - tag format: `v<version>`
  - indexed assets: `gbash_<version>_{linux,darwin}_{amd64,arm64}.tar.gz`
  - ignored assets: `gbash-extras_*`, Windows archives, and other non-runtime side assets

These shells are pulled in by the registry refresh job. They are not built or republished by `shuck-shells`.

## Automation

- `refresh-index.yml` regenerates the checked-in registry tree nightly and opens or updates a PR if it changes.
- `discover-upstream.yml` checks upstream release pages nightly and dispatches `build-shell-release.yml` for any missing latest shell releases.
- `refresh-index.yml` also runs automatically when a new shell release is published.
- `refresh-index.yml` also fetches configured external GitHub-release shells during its nightly regeneration pass.
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
