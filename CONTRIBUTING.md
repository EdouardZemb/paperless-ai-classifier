# Contributing & GitFlow

## Branching model (GitFlow)
- **main**: production / stable releases
- **develop**: integration branch for day‑to‑day work
- **feature/**: new features (branched from `develop`)
- **release/**: stabilization before release
- **hotfix/**: urgent fixes (branched from `main`)

## Workflow
1. Create a feature branch from `develop`
   ```bash
   git checkout develop
   git checkout -b feature/<short-name>
   ```
2. Commit with conventional messages (see below)
3. Merge back into `develop`
4. When ready to release: create `release/<version>` then merge into `main`

## Commit message conventions
- **feat:** new feature
- **fix:** bug fix
- **chore:** tooling / maintenance
- **docs:** documentation
- **refactor:** refactor
- **test:** tests

Example:
```
feat: add suggestions validation page
```
