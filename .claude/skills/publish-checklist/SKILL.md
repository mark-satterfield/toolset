---
name: publish-checklist
description: >-
  Use when publishing a plugin or releasing a new version — walks through the
  plugin publish checklist: version bump in plugin.json and .claude-plugin/plugin.json,
  marketplace.json update, commit, and tag
allowed-tools: [Read, Edit, Bash]
---

# Plugin Publish Checklist

Walk through these steps in order. Do not skip steps. Confirm each before proceeding.

## Pre-flight

1. Identify which plugin is being published (check `plugins/` for the target)
2. Determine the new version number (ask if not specified)

## Version Bump

3. Read `plugins/<name>/plugin.json` — update `version` field
4. Read `plugins/<name>/.claude-plugin/plugin.json` — update `version` field to match
5. Verify both version fields are identical

## Manifest Update

6. Read `.claude-plugin/marketplace.json`
7. Locate the entry for this plugin
8. Update the `version` field in the marketplace entry to match

## Commit and Tag

9. Stage changed files: `git add plugins/<name>/plugin.json plugins/<name>/.claude-plugin/plugin.json .claude-plugin/marketplace.json`
10. Commit: `git commit -m "chore(<name>): bump version to <version>"`
11. Tag: `git tag <name>-v<version>`
12. Confirm: report final commit hash and tag name
