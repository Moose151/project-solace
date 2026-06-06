# GitHub setup checklist

Before pushing Project Solace to GitHub, check that these files are not committed:

```text
.env
instance/solace.db
backups/
.venv/
```

The included `.gitignore` already excludes them.

Recommended first commit:

```bash
git init
git status
git add .
git commit -m "Initial Project Solace app"
```

Check what will be pushed:

```bash
git status
git ls-files
```

Then add your remote and push:

```bash
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/project-solace.git
git push -u origin main
```
