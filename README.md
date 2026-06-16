# stud

> VCS + package manager + CI/CD workflows + AI tooling — in one CLI.

## Modules

| Module | Description |
|--------|-------------|
| `stud.core` | Config, object store (zlib+sha256), ignore rules, event bus, file locking |
| `stud.vcs` | Git-like VCS — blobs, trees, commits, branches, merge, rebase, cherry-pick, remote push/pull |
| `stud.packages` | Semver, manifest (stud.json), lockfile, dependency resolver, registry client, publisher |
| `stud.workflows` | YAML-based CI/CD — jobs, steps, triggers (push/commit/schedule/manual), secrets |
| `stud.plugins` | Plugin SDK, dynamic loader, local registry, marketplace client |
| `stud.cloud` | Build targets — Python, Node, React, Angular, Flutter Web |
| `stud.security` | CVE scanner (OSV), HMAC signatures, entropy-based secret scanner, audit log |
| `stud.ai` | Provider-agnostic LLM client (Anthropic + OpenAI) — commit messages, code review, release notes, workflow gen |
| `stud.cli` | Full CLI with argparse, Rich UI, bash/zsh/fish completion, interactive wizard, REPL |

## Installation

```bash
pip install -e ".[rich]"
```

## Quick Start

```bash
stud init my-project
cd my-project
stud add .
stud commit -m "feat: initial commit"
stud branch feature
stud checkout feature
# ... make changes ...
stud add .
stud ai commit          # AI-generated commit message
stud merge feature
stud audit              # security audit
stud run ci             # run workflow
```

## Structure

```
stud/
├── core/         # config, object_store, hashing, ignore, events, lockmanager
├── vcs/          # objects, refs, index, diff, merge, rebase, cherry_pick, remote, service
├── packages/     # semver, manifest, lockfile, resolver, registry_client, publisher, service
│   └── sources/  # registry_source, local_source, git_source
├── workflows/    # schema, triggers, runner, scheduler, secrets, service
├── plugins/      # sdk, loader, manifest, registry, marketplace_client
├── cloud/        # deploy, service
│   └── targets/  # python, node, react, angular, flutter_web
├── security/     # vuln_scanner, signatures, secret_scanner, audit
├── ai/           # client, commit_messages, code_review, dependency_advisor, workflow_generator, release_notes
└── cli/          # main, ui, completion, wizards, repl
    └── commands/ # vcs, package, workflow, ai, security commands
```

## Requirements

- Python 3.10+
- `pyyaml` (required)
- `rich` (optional, for colored output)
