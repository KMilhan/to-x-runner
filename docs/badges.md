## Badge Artifact Strategy

Runtime-generated badge payloads should be pushed to the dedicated
`badge-artifacts` branch instead of committing them to `main`.

- `badge-artifacts` contains the `badges/` directory and any supporting
  documentation required by automation.
- GitHub Actions workflows force-push JSON/SVG badge outputs to that branch so
  badge URLs can target
  `https://raw.githubusercontent.com/KMilhan/unirun/badge-artifacts/...`.
- Contributors should avoid merging `badge-artifacts` into `main`; treat the
  branch as an append-only artifact store.
- To debug badge generation locally, run the corresponding workflow steps and
  push the results to `badge-artifacts` using the same directory layout.

Branch protection is disabled on `badge-artifacts` so workflows can update it
without manual approval. If the branch is accidentally deleted, recreate it
(using `git worktree add -b badge-artifacts`) and seed a fresh commit with
`badges/.gitkeep` plus a README explaining its purpose.
