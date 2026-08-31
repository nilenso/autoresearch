# Worktree Inventory

This repository was split out of `nilenso/ai-playground` from the former `autoresearch/` subtree.

## Standalone autoresearch worktrees

Local worktrees recreated under `/Users/priyangapkini/nilenso/autoresearch-worktrees`:

| Worktree | Branch | Purpose |
|---|---|---|
| `/Users/priyangapkini/nilenso/autoresearch` | `main` | Standalone main branch with current Arm E findings. |
| `/Users/priyangapkini/nilenso/autoresearch-worktrees/feat-autoresearch` | `feat/autoresearch` | Original autoresearch feature branch from ai-playground. |
| `/Users/priyangapkini/nilenso/autoresearch-worktrees/feat-autoresearch-from-proposals` | `feat/autoresearch-from-proposals` | Proposal-driven autoresearch branch from ai-playground. |
| `/Users/priyangapkini/nilenso/autoresearch-worktrees/feat-agent-struggle-scorer` | `feat/agent-struggle-scorer` | Agent struggle scorer branch from ai-playground. |
| `/Users/priyangapkini/nilenso/autoresearch-worktrees/wip-concurrent-run-worktrees` | `wip/concurrent-run-worktrees` | Preserved uncommitted WIP from the old `feat/autoresearch-from-proposals` worktree. |

These branches are pushed to `git@github.com:nilenso/autoresearch.git`.

## External botmap experiment worktrees

The experiment arms also used separate `botmap` repositories/worktrees. They are not branches of this autoresearch repository; they are candidate product branches for the evaluated CLI. Their patches and run artifacts are stored under `experiments/` and in the Hugging Face dataset.

| Local path | Botmap branch | Related arm / candidate |
|---|---|---|
| `/Users/priyangapkini/workspace/ar-a/botmap` | `cand/count-flag-parity` | Arm A count flag parity candidate. |
| `/Users/priyangapkini/workspace/ar-b/botmap` | `cand/count-wrong-column-hint` | Paired wrong-column hint candidate. |
| `/Users/priyangapkini/workspace/ar-b-new/botmap` | detached/base | Arm B prompt GEPA base workspace. |
| `/Users/priyangapkini/workspace/ar-c/botmap` | detached/base | Arm C full-repo GEPA workspace. |
| `/Users/priyangapkini/workspace/ar-c-new/botmap` | detached/base | Corrected Arm C full-repo GEPA workspace. |
| `/Users/priyangapkini/workspace/ar-e/botmap` | `arm-e/combined-agent-friendly-hints` | Arm E combined accepted hints candidate. |
| `/Users/priyangapkini/workspace/ar-search/botmap` | `cand/categories-search` | Arm E `categories --search` candidate. |
| `/Users/priyangapkini/workspace/ar-search-semantic/botmap` | `cand/categories-search-semantic-skill` | Arm E semantic/regional vocabulary skill candidate. |
