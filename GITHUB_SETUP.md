<!-- Purpose: provide a beginner-friendly workflow for publishing this project to GitHub. -->
<!-- Work: explain source-only staging, the first commit, remote setup, and pushing changes. -->

# Publish to GitHub

The project is prepared for a source-only repository. Share application code, documentation, dependency files, and automated tests. Original PDFs, model weights, indexes, caches, the virtual environment, local settings/tokens, and generated reports remain ignored. Their local copies are preserved.

## 1. Review local files

Run these commands from the project root:

```powershell
git status --short
git diff --cached --stat
git ls-files
```

Tracked paths should include `api/`, `frontend/`, `src/`, `tests/`, documentation, and configuration. `notes/README.md` is included; original course PDFs are not. Do not force-add `data/` or `venv/`. Anyone cloning the repository must install dependencies, download models, and provide their own notes.

## 2. Create an empty GitHub repository

Choose **New repository** on GitHub and enter a name such as `RAG-NM`. Select public or private visibility. Leave the remote empty: do not initialize another README, gitignore, or license because local files are already prepared. Copy the new repository's HTTPS URL.

Choosing a source-code license is a separate decision. No distribution license has been added during preparation.

## 3. Create the first local commit

The local repository uses the `main` branch and source files have been staged. If Git author identity is not configured, set your name and the email or noreply address from your GitHub settings. Replace the placeholders with your own values:

```powershell
git config user.name 'YOUR_NAME'
git config user.email 'YOUR_GITHUB_EMAIL_OR_NOREPLY_EMAIL'
git add .
git diff --cached --check
git commit -m 'Add local numerical analysis RAG study assistant'
```

These identity commands apply to this repository only because they do not use `--global`.

## 4. Connect the remote and push

Replace the example URL with your new empty repository's HTTPS URL:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/RAG-NM.git
git push -u origin main
```

If `origin` already exists, inspect `git remote -v` before changing it. Git Credential Manager may open a browser sign-in. Keep credentials out of source files and chat messages.

## 5. Verify the upload

Open the GitHub repository and check its files and README. In **Actions**, inspect the **Python tests** workflow. Local tests and the hosted workflow are separate runs, so verify the actual first hosted result. Pushing source does not deploy the running API or frontend.

## Later changes

```powershell
git status --short
git add .
git diff --cached --check
git commit -m 'Describe the change'
git push
```

## GitHub or Docker first?

Publish the current working application to GitHub first. Add Docker configuration and verify container behavior afterward, then commit and push those changes separately. Docker image registries and application hosting are separate from source-code publishing. Docker support is not included yet.
