# shuck-shells

`shuck-shells` publishes prebuilt shell archives and the index that `shuck run` uses to find them.

If you are looking for shells to download, this is the right place. If you want to contribute a new shell, fix a builder, or work on the automation, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Where the binaries live

Every release archive is attached to a GitHub release in this repo (or, for externally sourced shells, in the upstream repo). The registry JSON points at those URLs and ships their SHA-256 checksums.

- registry root: <https://ewhauser.github.io/shuck-shells/index.json>
- release page: <https://github.com/ewhauser/shuck-shells/releases>

## Supported shells

| Shell     | Source                                        |
| --------- | --------------------------------------------- |
| `bash`    | built here from GNU upstream                  |
| `busybox` | built here from busybox.net upstream (Linux)  |
| `dash`    | built here from kernel.org upstream           |
| `mksh`    | built here from MirBSD upstream               |
| `zsh`     | built here from sourceforge upstream          |
| `bashkit` | indexed from `everruns/bashkit` releases      |
| `gbash`   | indexed from `ewhauser/gbash` releases        |

## Supported platforms

- `x86_64-linux-gnu`
- `aarch64-linux-gnu`
- `x86_64-linux-musl`
- `aarch64-linux-musl`
- `x86_64-darwin`
- `aarch64-darwin`

`busybox` is Linux only. `*-linux-gnu` archives are built on Ubuntu 22.04 (glibc baseline); `*-linux-musl` archives are built inside Alpine.

## Release and asset naming

- release tag: `<shell>-<version>`
- archive asset: `<shell>-<version>-<platform>.tar.gz`

Examples:

- `bash-5.2.21` → `bash-5.2.21-x86_64-linux-gnu.tar.gz`
- `zsh-5.9` → `zsh-5.9-aarch64-darwin.tar.gz`
- `mksh-R59c` → `mksh-R59c-x86_64-linux-musl.tar.gz`

## Registry format

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
