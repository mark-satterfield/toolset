#!/usr/bin/env python3
"""Scaffold PRD directory structure from frontend_analyzer.py output.

Reads analysis JSON and creates the prd/ directory with README.md,
per-page stubs, and appendix files pre-populated with extracted data.

Stdlib only — no third-party dependencies.

Usage:
    python3 frontend_analyzer.py /path/to/project -o analysis.json
    python3 prd_scaffolder.py analysis.json
    python3 prd_scaffolder.py analysis.json --output-dir ./prd --project-name "My App"
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from pathlib import Path
from typing import Any, Dict, List


def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.strip().lower()
    text = re.sub(r"[/:{}*?\"<>|]", "-", text)
    text = re.sub(r"[^a-z0-9\-]", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def route_to_page_name(route: str) -> str:
    """Convert a route path to a human-readable page name."""
    if route == "/" or route == "":
        return "Home"
    parts = route.strip("/").split("/")
    # Remove dynamic segments for naming
    clean = [p for p in parts if not p.startswith(":") and not p.startswith("*")]
    if not clean:
        clean = [p.lstrip(":*") for p in parts]
    return " ".join(w.capitalize() for w in "-".join(clean).replace("_", "-").split("-"))


def generate_readme(project_name: str, routes: List[Dict], summary: Dict, date: str) -> str:
    """Generate the PRD README.md."""
    lines = [
        f"# {project_name} — Product Requirements Document",
        "",
        f"> Generated: {date}",
        "",
        "## System Overview",
        "",
        f"<!-- TODO: Describe what {project_name} does, its business context, and primary users -->",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Pages | {summary.get('pages', 0)} |",
        f"| API Endpoints | {summary.get('api_endpoints', 0)} |",
        f"| Integrated APIs | {summary.get('api_integrated', 0)} |",
        f"| Mock APIs | {summary.get('api_mock', 0)} |",
        f"| Enums/Constants | {summary.get('enums', 0)} |",
        f"| i18n | {'Yes' if summary.get('has_i18n') else 'No'} |",
        f"| State Management | {'Yes' if summary.get('has_state_management') else 'No'} |",
        "",
        "## Module Overview",
        "",
        "| Module | Pages | Core Functionality |",
        "|--------|-------|--------------------|",
        "| <!-- TODO: Group pages into modules --> | | |",
        "",
        "## Page Inventory",
        "",
        "| # | Page Name | Route | Module | Doc Link |",
        "|---|-----------|-------|--------|----------|",
    ]

    for i, route in enumerate(routes, 1):
        path = route.get("path", "/")
        name = route_to_page_name(path)
        slug = slugify(name) or f"page-{i}"
        filename = f"{i:02d}-{slug}.md"
        lines.append(f"| {i} | {name} | `{path}` | <!-- TODO --> | [→](./pages/{filename}) |")

    lines.extend([
        "",
        "## Global Notes",
        "",
        "### Permission Model",
        "<!-- TODO: Summarize auth/role system if present -->",
        "",
        "### Common Interaction Patterns",
        "<!-- TODO: Global rules — delete confirmations, default sort, etc. -->",
        "",
    ])

    return "\n".join(lines)


def generate_page_stub(route: Dict, index: int, date: str) -> str:
    """Generate a per-page PRD stub."""
    path = route.get("path", "/")
    name = route_to_page_name(path)
    source = route.get("source", "unknown")

    return f"""# {name}

> **Route:** `{path}`
> **Module:** <!-- TODO -->
> **Source:** `{source}`
> **Generated:** {date}

## Overview
<!-- TODO: 2-3 sentences — core function and use case -->

## Layout
<!-- TODO: Region breakdown — search area, table, detail panel, action bar, etc. -->

## Fields

### Search / Filters
| Field | Type | Required | Options / Enum | Default | Notes |
|-------|------|----------|---------------|---------|-------|
| <!-- TODO --> | | | | | |

### Data Table
| Column | Format | Sortable | Filterable | Notes |
|--------|--------|----------|-----------|-------|
| <!-- TODO --> | | | | |

### Actions
| Button | Visibility Condition | Behavior |
|--------|---------------------|----------|
| <!-- TODO --> | | |

## Interactions

### Page Load
<!-- TODO: What happens on mount — default queries, preloaded data -->

### Search
- **Trigger:** <!-- TODO -->
- **Behavior:** <!-- TODO -->
- **Special rules:** <!-- TODO -->

### Create / Edit
- **Trigger:** <!-- TODO -->
- **Modal/drawer content:** <!-- TODO -->
- **Validation:** <!-- TODO -->
- **On success:** <!-- TODO -->

### Delete
- **Trigger:** <!-- TODO -->
- **Confirmation:** <!-- TODO -->
- **On success:** <!-- TODO -->

## API Dependencies

| API | Method | Path | Trigger | Integrated | Notes |
|-----|--------|------|---------|-----------|-------|
| <!-- TODO --> | | | | | |

## Page Relationships
- **From:** <!-- TODO: Source pages + params -->
- **To:** <!-- TODO: Target pages + params -->
- **Data coupling:** <!-- TODO: Cross-page refresh triggers -->

## Business Rules
<!-- TODO: Anything that doesn't fit above -->
"""


def generate_enum_dictionary(enums: List[Dict]) -> str:
    """Generate the enum dictionary appendix."""
    lines = [
        "# Enum & Constant Dictionary",
        "",
        "All enums, status codes, and type mappings extracted from the codebase.",
        "",
    ]

    if not enums:
        lines.append("*No enums detected. Manual review recommended.*")
        return "\n".join(lines)

    for e in enums:
        lines.append(f"## {e['name']}")
        lines.append(f"**Type:** {e.get('type', 'unknown')} | **Source:** `{e.get('source', 'unknown').split('/')[-1]}`")
        lines.append("")
        if e.get("values"):
            lines.append("| Key | Value |")
            lines.append("|-----|-------|")
            for k, v in e["values"].items():
                lines.append(f"| `{k}` | {v} |")
        lines.append("")

    return "\n".join(lines)


def generate_api_inventory(apis: List[Dict]) -> str:
    """Generate the API inventory appendix."""
    lines = [
        "# API Inventory",
        "",
        "All API endpoints detected in the codebase.",
        "",
    ]

    if not apis:
        lines.append("*No API calls detected. Manual review recommended.*")
        return "\n".join(lines)

    integrated = [a for a in apis if a.get("integrated")]
    mocked = [a for a in apis if a.get("mock_detected") and not a.get("integrated")]
    unknown = [a for a in apis if not a.get("integrated") and not a.get("mock_detected")]

    for label, group in [("Integrated APIs", integrated), ("Mock / Stub APIs", mocked), ("Unknown Status", unknown)]:
        if group:
            lines.append(f"## {label}")
            lines.append("")
            lines.append("| Method | Path | Source | Notes |")
            lines.append("|--------|------|--------|-------|")
            for a in group:
                src = a.get("source", "").split("/")[-1]
                lines.append(f"| {a.get('method', '?')} | `{a.get('path', '?')}` | {src} | |")
            lines.append("")

    return "\n".join(lines)


def generate_page_relationships(routes: List[Dict]) -> str:
    """Generate page relationships appendix stub."""
    lines = [
        "# Page Relationships",
        "",
        "Navigation flow and data coupling between pages.",
        "",
        "## Navigation Map",
        "",
        "<!-- TODO: Fill in after page-by-page analysis -->",
        "",
        "```",
        "Home",
    ]

    for r in routes[:20]:  # Cap at 20 for readability
        name = route_to_page_name(r.get("path", "/"))
        lines.append(f"  ├── {name}")

    if len(routes) > 20:
        lines.append(f"  └── ... ({len(routes) - 20} more)")

    lines.extend([
        "```",
        "",
        "## Cross-Page Data Dependencies",
        "",
        "| Source Page | Target Page | Trigger | Data Passed |",
        "|-----------|------------|---------|------------|",
        "| <!-- TODO --> | | | |",
        "",
    ])

    return "\n".join(lines)


def generate_infra_stack_stub(stack: Dict, index: int, date: str) -> str:
    """Generate a per-CDK-stack PRD stub."""
    name = stack.get("name", f"Stack {index}")
    source = stack.get("source", "unknown")
    kind = stack.get("type", "stack")
    return f"""# {name} ({kind.capitalize()})

> **Type:** CDK {kind.capitalize()}
> **Source:** `{source}`
> **Generated:** {date}

## Purpose
<!-- TODO: What does this {kind} create and why does it exist? -->

## AWS Resources Created
<!-- TODO: List each construct: DynamoDB tables, Lambda functions, S3 buckets, API Gateway, SQS queues, etc. -->

| Resource | Type | Key Config |
|----------|------|-----------|
| <!-- TODO --> | | |

## Props / Configuration
<!-- TODO: What inputs does this {kind} accept? What are the required vs optional props? -->

## Cross-Stack Dependencies

### SSM Parameters Consumed
<!-- TODO: Which SSM paths does this {kind} read? Which stack produces them? -->

### SSM Parameters Exported
<!-- TODO: Which SSM paths does this {kind} write for downstream stacks? -->

## Deployment Wave
<!-- TODO: infra / layers / services / frontends -->

## Deploy Command
<!-- TODO: `task deploy-<name>` or `cdk deploy <StackName>` -->

## Business Rules / Constraints
<!-- TODO: Memory limits, timeout constraints, PITR requirements, billing mode decisions, etc. -->
"""


def generate_mobile_screen_stub(screen: Dict, index: int, date: str) -> str:
    """Generate a per-screen mobile PRD stub."""
    path = screen.get("path", "/")
    name = route_to_page_name(path)
    source = screen.get("source", "unknown")
    return f"""# {name} (Mobile Screen)

> **Route:** `{path}`
> **Source:** `{source}`
> **Generated:** {date}

## Overview
<!-- TODO: What does this screen show? Who uses it and when? -->

## Layout
<!-- TODO: Sections, tab bar presence, header config, scroll behavior -->

## Fields / Elements

| Element | Type | Behavior |
|---------|------|----------|
| <!-- TODO --> | | |

## Interactions

### Screen Load
<!-- TODO: What data is fetched on mount? Loading state? -->

### User Actions
<!-- TODO: Buttons, gestures, navigation triggers -->

## Navigation
- **From:** <!-- TODO: Which screens navigate here? -->
- **To:** <!-- TODO: Where can users go from here? -->
- **Params received:** <!-- TODO: What params does this screen expect? -->

## API Dependencies
| API | Method | Path | Trigger |
|-----|--------|------|---------|
| <!-- TODO --> | | | |

## Business Rules
<!-- TODO -->
"""


def generate_mcp_stub(tool: Dict, index: int, date: str) -> str:
    """Generate a per-MCP-tool PRD stub."""
    name = tool.get("name", f"tool-{index}")
    source = tool.get("source", "unknown")
    return f"""# MCP Tool: {name}

> **Source:** `{source}`
> **Generated:** {date}

## Purpose
<!-- TODO: What does this tool do? What agent uses it? -->

## Input Schema
<!-- TODO: Parameters this tool accepts -->

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| <!-- TODO --> | | | |

## Output
<!-- TODO: What does this tool return? -->

## Error Conditions
<!-- TODO: What errors can this tool return and why? -->

## Usage Context
<!-- TODO: Which agent invokes this tool? Under what conditions? -->
"""


def generate_infrastructure_inventory(infra: Dict, date: str) -> str:
    """Generate the infrastructure appendix."""
    lines = [
        "# Infrastructure Inventory",
        "",
        f"> Generated: {date}",
        "",
        "All AWS constructs and cross-stack wiring detected in the codebase.",
        "",
    ]

    stacks = infra.get("cdk_stacks", [])
    if stacks:
        lines.append("## CDK Stacks and Constructs")
        lines.append("")
        lines.append("| Name | Type | Source |")
        lines.append("|------|------|--------|")
        for s in stacks:
            src = s.get("source", "").split("/")[-1]
            lines.append(f"| {s['name']} | {s.get('type', 'stack')} | `{src}` |")
        lines.append("")

    aws_services = infra.get("aws_services", {})
    if aws_services:
        lines.append("## AWS Services Used")
        lines.append("")
        for svc in sorted(aws_services.keys()):
            lines.append(f"- **{svc}**")
        lines.append("")

    handlers = infra.get("lambda_handlers", [])
    if handlers:
        lines.append("## Lambda Handler Inventory")
        lines.append("")
        lines.append("| Handler File | Language |")
        lines.append("|-------------|---------|")
        for h in handlers:
            src = h.get("source", "").split("/")[-1]
            lines.append(f"| `{src}` | {h.get('language', '?')} |")
        lines.append("")

    ssm = infra.get("ssm_parameters", [])
    if ssm:
        lines.append("## SSM Cross-Stack Parameter Paths")
        lines.append("")
        lines.append("| Parameter Path | Source File |")
        lines.append("|---------------|------------|")
        for p in ssm:
            src = p.get("source", "").split("/")[-1]
            lines.append(f"| `{p['path']}` | `{src}` |")
        lines.append("")

    if not stacks and not aws_services and not handlers:
        lines.append("*No CDK infrastructure detected. Manual review recommended.*")

    return "\n".join(lines)


def generate_cicd_inventory(cicd: Dict, date: str) -> str:
    """Generate the CI/CD appendix."""
    lines = [
        "# CI/CD Inventory",
        "",
        f"> Generated: {date}",
        "",
        "All GitHub Actions workflows and Taskfile targets detected in the codebase.",
        "",
    ]

    gha = cicd.get("github_actions", {})
    workflows = gha.get("workflows", [])
    if workflows:
        lines.append("## GitHub Actions Workflows")
        lines.append("")
        for wf in workflows:
            lines.append(f"### {wf['name']}")
            lines.append(f"**File:** `{wf.get('file', '')}`")
            if wf.get("triggers"):
                lines.append(f"**Triggers:** {', '.join(wf['triggers'])}")
            if wf.get("jobs"):
                lines.append(f"**Jobs:** {', '.join(wf['jobs'])}")
            if wf.get("secrets"):
                lines.append(f"**Secrets required:** {', '.join(f'`{s}`' for s in wf['secrets'])}")
            if wf.get("environments"):
                lines.append(f"**Environments:** {', '.join(wf['environments'])}")
            lines.append("")

    taskfile = cicd.get("taskfile", {})
    targets = taskfile.get("targets", [])
    if targets:
        lines.append("## Taskfile Targets")
        lines.append("")
        lines.append("| Target | Description |")
        lines.append("|--------|-------------|")
        for t in targets:
            lines.append(f"| `{t['name']}` | {t.get('desc', '')} |")
        lines.append("")

    if not workflows and not targets:
        lines.append("*No CI/CD configuration detected. Manual review recommended.*")

    return "\n".join(lines)


def scaffold(analysis: Dict[str, Any], output_dir: Path, project_name: Optional[str] = None):
    """Create the full PRD directory structure."""
    date = datetime.now().strftime("%Y-%m-%d")
    name = project_name or analysis.get("project", {}).get("name", "Project")
    routes = analysis.get("routes", {}).get("pages", [])
    apis = analysis.get("apis", {}).get("endpoints", [])
    enums = analysis.get("enums", {}).get("definitions", [])
    summary = analysis.get("summary", {})
    infra = analysis.get("infrastructure", {})
    cicd = analysis.get("cicd", {})
    mobile = analysis.get("mobile", {})
    agentic = analysis.get("agentic", {})

    # Create core directories
    pages_dir = output_dir / "pages"
    appendix_dir = output_dir / "appendix"
    pages_dir.mkdir(parents=True, exist_ok=True)
    appendix_dir.mkdir(parents=True, exist_ok=True)

    # README.md
    readme = generate_readme(name, routes, summary, date)
    (output_dir / "README.md").write_text(readme)
    print(f"  Created: README.md")

    # Per-page stubs (frontend)
    for i, route in enumerate(routes, 1):
        page_name = route_to_page_name(route.get("path", "/"))
        slug = slugify(page_name) or f"page-{i}"
        filename = f"{i:02d}-{slug}.md"
        content = generate_page_stub(route, i, date)
        (pages_dir / filename).write_text(content)
        print(f"  Created: pages/{filename}")

    # Infrastructure stubs (CDK stacks)
    cdk_stacks = infra.get("cdk_stacks", [])
    if cdk_stacks:
        infra_dir = output_dir / "infrastructure"
        infra_dir.mkdir(exist_ok=True)
        for i, stack in enumerate(cdk_stacks, 1):
            slug = slugify(stack.get("name", f"stack-{i}")) or f"stack-{i}"
            filename = f"{i:02d}-{slug}.md"
            content = generate_infra_stack_stub(stack, i, date)
            (infra_dir / filename).write_text(content)
            print(f"  Created: infrastructure/{filename}")

    # Mobile screen stubs
    mobile_screens = mobile.get("screens", [])
    if mobile_screens:
        mobile_dir = output_dir / "mobile"
        mobile_dir.mkdir(exist_ok=True)
        for i, screen in enumerate(mobile_screens, 1):
            page_name = route_to_page_name(screen.get("path", "/"))
            slug = slugify(page_name) or f"screen-{i}"
            filename = f"{i:02d}-{slug}.md"
            content = generate_mobile_screen_stub(screen, i, date)
            (mobile_dir / filename).write_text(content)
            print(f"  Created: mobile/{filename}")

    # Agentic / MCP stubs
    mcp_tools = agentic.get("mcp_tools", [])
    if mcp_tools:
        agentic_dir = output_dir / "agentic"
        agentic_dir.mkdir(exist_ok=True)
        for i, tool in enumerate(mcp_tools, 1):
            slug = slugify(tool.get("name", f"tool-{i}")) or f"tool-{i}"
            filename = f"{i:02d}-{slug}.md"
            content = generate_mcp_stub(tool, i, date)
            (agentic_dir / filename).write_text(content)
            print(f"  Created: agentic/{filename}")

    # Appendix — standard
    (appendix_dir / "enum-dictionary.md").write_text(generate_enum_dictionary(enums))
    print(f"  Created: appendix/enum-dictionary.md")

    (appendix_dir / "api-inventory.md").write_text(generate_api_inventory(apis))
    print(f"  Created: appendix/api-inventory.md")

    (appendix_dir / "page-relationships.md").write_text(generate_page_relationships(routes))
    print(f"  Created: appendix/page-relationships.md")

    # Appendix — infrastructure (always generate if CDK detected)
    if infra.get("detected") or cdk_stacks:
        (appendix_dir / "infrastructure-inventory.md").write_text(
            generate_infrastructure_inventory(infra, date)
        )
        print(f"  Created: appendix/infrastructure-inventory.md")

    # Appendix — CI/CD (always generate if any CI/CD detected)
    has_cicd = (cicd.get("github_actions", {}).get("detected") or
                cicd.get("taskfile", {}).get("detected"))
    if has_cicd:
        (appendix_dir / "cicd-inventory.md").write_text(
            generate_cicd_inventory(cicd, date)
        )
        print(f"  Created: appendix/cicd-inventory.md")

    print(f"\nPRD scaffold complete: {output_dir}")
    print(f"   {len(routes)} page stubs, {len(apis)} API endpoints, {len(enums)} enums")
    if cdk_stacks:
        print(f"   {len(cdk_stacks)} infrastructure stubs")
    if mobile_screens:
        print(f"   {len(mobile_screens)} mobile screen stubs")
    if mcp_tools:
        print(f"   {len(mcp_tools)} agentic/MCP stubs")
    print(f"\n   Next: Review each stub and fill in the TODO sections.")


def validate_analysis(analysis: Dict[str, Any]) -> List[str]:
    """Validate analysis JSON has the required structure. Returns list of errors."""
    errors = []

    if not isinstance(analysis, dict):
        return ["Analysis must be a JSON object"]

    if "error" in analysis:
        errors.append(f"Analysis contains error: {analysis['error']}")

    required_keys = ["project", "routes", "apis"]
    for key in required_keys:
        if key not in analysis:
            errors.append(f"Missing required key: '{key}'")

    if "project" in analysis:
        proj = analysis["project"]
        if not isinstance(proj, dict):
            errors.append("'project' must be an object")
        elif "framework" not in proj:
            errors.append("'project.framework' is missing")

    if "routes" in analysis:
        routes = analysis["routes"]
        if not isinstance(routes, dict):
            errors.append("'routes' must be an object")
        elif "pages" not in routes and "frontend_pages" not in routes and "backend_endpoints" not in routes:
            errors.append("'routes' must contain 'pages', 'frontend_pages', or 'backend_endpoints'")

    if "apis" in analysis:
        apis = analysis["apis"]
        if not isinstance(apis, dict):
            errors.append("'apis' must be an object")
        elif "endpoints" not in apis:
            errors.append("'apis.endpoints' is missing")

    return errors


def print_summary(output_dir: Path, analysis: Dict[str, Any]):
    """Print a structured summary of what was generated."""
    routes = analysis.get("routes", {}).get("pages", [])
    apis = analysis.get("apis", {}).get("endpoints", [])
    enums = analysis.get("enums", {}).get("definitions", [])
    models = analysis.get("models", {}).get("definitions", [])
    summary = analysis.get("summary", {})
    stack = summary.get("stack_type", "unknown")

    print(f"\nPRD scaffold complete: {output_dir}/")
    print(f"  Stack type:     {stack}")
    print(f"  Page stubs:     {len(routes)}")
    print(f"  API endpoints:  {len(apis)}")
    print(f"  Enums:          {len(enums)}")
    if models:
        print(f"  Models:         {len(models)}")
    if summary.get("has_cdk"):
        print(f"  CDK stacks:     {summary.get('cdk_stacks', 0)}")
        print(f"  Lambda handlers:{summary.get('lambda_handlers', 0)}")
    if summary.get("github_workflows"):
        print(f"  GH workflows:   {summary['github_workflows']}")
    if summary.get("taskfile_targets"):
        print(f"  Taskfile tasks: {summary['taskfile_targets']}")
    if summary.get("mobile_screens"):
        print(f"  Mobile screens: {summary['mobile_screens']}")
    if summary.get("mcp_tools"):
        print(f"  MCP tools:      {summary['mcp_tools']}")
    print(f"\n  Next: Review each stub and fill in the TODO sections.")


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold PRD directory from codebase analysis"
    )
    parser.add_argument("analysis", help="Path to analysis JSON from codebase_analyzer.py")
    parser.add_argument("-o", "--output-dir", default="prd", help="Output directory (default: prd/)")
    parser.add_argument("-n", "--project-name", help="Override project name")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate analysis JSON without generating files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be created without writing files")
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        print(f"Error: Analysis file not found: {analysis_path}")
        raise SystemExit(2)

    try:
        with open(analysis_path) as f:
            analysis = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {analysis_path}: {e}")
        raise SystemExit(2)

    # Validate
    errors = validate_analysis(analysis)
    if errors:
        print(f"Validation errors in {analysis_path}:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit(1)

    if args.validate_only:
        print(f"Analysis file is valid: {analysis_path}")
        routes = analysis.get("routes", {}).get("pages", [])
        print(f"  {len(routes)} routes, "
              f"{len(analysis.get('apis', {}).get('endpoints', []))} APIs, "
              f"{len(analysis.get('enums', {}).get('definitions', []))} enums")
        return

    output_dir = Path(args.output_dir)

    if args.dry_run:
        routes = analysis.get("routes", {}).get("pages", [])
        infra = analysis.get("infrastructure", {})
        cicd = analysis.get("cicd", {})
        mobile = analysis.get("mobile", {})
        agentic = analysis.get("agentic", {})
        print(f"Dry run — would create in {output_dir}/:\n")
        print(f"  {output_dir}/README.md")
        for i, route in enumerate(routes, 1):
            page_name = route_to_page_name(route.get("path", "/"))
            slug = slugify(page_name) or f"page-{i}"
            print(f"  {output_dir}/pages/{i:02d}-{slug}.md")
        for i, stack in enumerate(infra.get("cdk_stacks", []), 1):
            slug = slugify(stack.get("name", f"stack-{i}")) or f"stack-{i}"
            print(f"  {output_dir}/infrastructure/{i:02d}-{slug}.md")
        for i, screen in enumerate(mobile.get("screens", []), 1):
            page_name = route_to_page_name(screen.get("path", "/"))
            slug = slugify(page_name) or f"screen-{i}"
            print(f"  {output_dir}/mobile/{i:02d}-{slug}.md")
        for i, tool in enumerate(agentic.get("mcp_tools", []), 1):
            slug = slugify(tool.get("name", f"tool-{i}")) or f"tool-{i}"
            print(f"  {output_dir}/agentic/{i:02d}-{slug}.md")
        print(f"  {output_dir}/appendix/enum-dictionary.md")
        print(f"  {output_dir}/appendix/api-inventory.md")
        print(f"  {output_dir}/appendix/page-relationships.md")
        if infra.get("detected") or infra.get("cdk_stacks"):
            print(f"  {output_dir}/appendix/infrastructure-inventory.md")
        has_cicd = (cicd.get("github_actions", {}).get("detected") or
                    cicd.get("taskfile", {}).get("detected"))
        if has_cicd:
            print(f"  {output_dir}/appendix/cicd-inventory.md")
        return

    print(f"Scaffolding PRD in {output_dir}/...\n")
    scaffold(analysis, output_dir, args.project_name)
    print_summary(output_dir, analysis)


if __name__ == "__main__":
    main()
