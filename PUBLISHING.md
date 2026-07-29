# Publish TokenOptiPy on GitHub

## Create the repository

Create an empty public repository named `TokenOptiPy` under the GitHub account `MEEDamrane`.

Do not initialize it with a README, license or `.gitignore`, because they already exist here.

## Push the prepared repository

```bash
git remote add origin https://github.com/MEEDamrane/TokenOptiPy.git
git push -u origin main --tags
```

## Recommended repository settings

- Description: `Local token-flow graphs and prompt hotspot analysis for LLM applications.`
- Topics: `llm`, `prompt-engineering`, `tokens`, `static-analysis`, `graph`, `python`, `open-source`
- Enable Issues and Discussions.
- Protect `main` after the initial push.
- Require the `tests` workflow before merging pull requests.

## Release

Create a GitHub release from tag `v0.2.0` and attach the source archives and SHA-256 file.
