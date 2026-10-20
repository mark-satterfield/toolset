---
name: "senior-fullstack"
description: Fullstack development on a serverless AWS stack (Next.js web and React Native mobile on the project's design system, calling Python Lambda services on aws-lambda-powertools behind API Gateway REST API v1, with Cognito sign-in), with code quality analysis scoring security and complexity. Use when the user asks to "scaffold a new project", "create a Next.js app", "analyze code quality", "audit my codebase", "what stack should I use", "generate project boilerplate", or mentions fullstack development, project setup, or tech stack comparison.
---

# Senior Fullstack

Fullstack development skill with project scaffolding and code quality analysis tools.

## The stack

The project's stack is decided in its solution strategy and architecture constraints (arc42 sections 4 and 2) and named in its project instructions; read them before you choose anything. A stack choice is not re-made per feature. This skill covers a serverless AWS stack of this shape:

| Layer | Serverless AWS stack |
|-------|------------|
| Web front end | Next.js, TypeScript, on the project's design system (for example the `cds` skills), behind CloudFront and AWS WAF |
| Mobile front end | React Native, on the same design system |
| API | API Gateway REST API v1, spec-first in OpenAPI; the web client uses its own generated client. Live push uses the API Gateway WebSocket API |
| Backend | Python Lambdas on `aws-lambda-powertools`, through the project's Lambda chassis library where it has one (see `senior-backend`). Frameworks the constraints ban are not used, and Next.js API routes are not the backend |
| Data | DynamoDB, Aurora PostgreSQL Serverless v2 through the RDS Data API, versioned S3, each owned by one service |
| Auth | Amazon Cognito |
| Infrastructure | CDK in Python, through the project's shared CDK library where it has one; names from the naming command (`resource-naming`) |
| Payments | The payment provider the project's architecture names (see `stripe-integration-expert` for Stripe) |

Load `web-frontend-coding` and `typescript-coding` for front-end code and `python-coding` for service code.

---

## Table of Contents

- [Trigger Phrases](#trigger-phrases)
- [Tools](#tools)
- [Workflows](#workflows)
- [Reference Guides](#reference-guides)

---

## Trigger Phrases

Use this skill when you hear:
- "scaffold a new project"
- "create a Next.js app"
- "analyze code quality"
- "check for security issues in codebase"
- "what stack should I use"
- "set up a fullstack project"
- "generate project boilerplate"

---

## Tools

### Project Scaffolder

Generates generic fullstack project structures with boilerplate code. A new repository of the project is created by the `polyrepo-steward` from the project's repository templates, not by this scaffolder; use the scaffolder only for a throwaway prototype outside the project's repositories.

**Templates:**
- `nextjs` - Next.js 14+ with App Router, TypeScript, Tailwind CSS (the only template whose front end matches the stack above; a project with a design system styles with it, not ad hoc Tailwind)
- `fastapi-react`, `mern`, `django-react` - generic stacks outside the stack above; never use them where the project's constraints ban their frameworks or stores

**Usage:**

```bash
# List available templates
python scripts/project_scaffolder.py --list-templates

# Create Next.js project
python scripts/project_scaffolder.py nextjs my-app

# Specify output directory
python scripts/project_scaffolder.py nextjs my-app --output ./projects

# JSON output
python scripts/project_scaffolder.py nextjs my-app --json
```

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `template` | Template name (see Templates above) |
| `project_name` | Name for the new project directory |
| `--output, -o` | Output directory (default: current directory) |
| `--list-templates, -l` | List all available templates |
| `--json` | Output in JSON format |

**Output includes:**
- Project structure with all necessary files
- Package configurations (package.json)
- TypeScript configuration
- Docker and docker-compose setup
- Environment file templates
- Next steps for running the project

---

### Code Quality Analyzer

Analyzes fullstack codebases for quality issues.

**Analysis Categories:**
- Security vulnerabilities (hardcoded secrets, injection risks)
- Code complexity metrics (cyclomatic complexity, nesting depth)
- Dependency health (outdated packages, known CVEs)
- Test coverage estimation
- Documentation quality

**Usage:**

```bash
# Analyze current directory
python scripts/code_quality_analyzer.py .

# Analyze specific project
python scripts/code_quality_analyzer.py /path/to/project

# Verbose output with detailed findings
python scripts/code_quality_analyzer.py . --verbose

# JSON output
python scripts/code_quality_analyzer.py . --json

# Save report to file
python scripts/code_quality_analyzer.py . --output report.json
```

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `project_path` | Path to project directory (default: current directory) |
| `--verbose, -v` | Show detailed findings |
| `--json` | Output in JSON format |
| `--output, -o` | Write report to file |

**Output includes:**
- Overall score (0-100) with letter grade
- Security issues by severity (critical, high, medium, low)
- High complexity files
- Vulnerable dependencies with CVE references
- Test coverage estimate
- Documentation completeness
- Prioritized recommendations

**Sample Output:**

```
============================================================
CODE QUALITY ANALYSIS REPORT
============================================================

Overall Score: 75/100 (Grade: C)
Files Analyzed: 45
Total Lines: 12,500

--- SECURITY ---
  Critical: 1
  High: 2
  Medium: 5

--- COMPLEXITY ---
  Average Complexity: 8.5
  High Complexity Files: 3

--- RECOMMENDATIONS ---
1. [P0] SECURITY
   Issue: Potential hardcoded secret detected
   Action: Remove or secure sensitive data at line 42
```

---

## Workflows

### Workflow 1: Start New Prototype

A new repository of the project comes from the `polyrepo-steward`; this workflow is for a throwaway prototype outside the project's repositories.

1. Use the project's stack (see The stack at the top)
2. Scaffold project structure
3. Verify scaffold: confirm `package.json` (or `requirements.txt`) exists
4. Run initial quality check — address any P0 issues before proceeding
5. Set up development environment

```bash
# 1. Scaffold project
python scripts/project_scaffolder.py nextjs my-saas-app

# 2. Verify scaffold succeeded
ls my-saas-app/package.json

# 3. Navigate and install
cd my-saas-app
npm install

# 4. Configure environment
cp .env.example .env.local

# 5. Run quality check
python ../scripts/code_quality_analyzer.py .

# 6. Start development
npm run dev
```

### Workflow 2: Audit Existing Codebase

1. Run code quality analysis
2. Review security findings — fix all P0 (critical) issues immediately
3. Re-run analyzer to confirm P0 issues are resolved
4. Create tickets for P1/P2 issues

```bash
# 1. Full analysis
python scripts/code_quality_analyzer.py /path/to/project --verbose

# 2. Generate detailed report
python scripts/code_quality_analyzer.py /path/to/project --json --output audit.json

# 3. After fixing P0 issues, re-run to verify
python scripts/code_quality_analyzer.py /path/to/project --verbose
```

### Workflow 3: Stack Selection

The project's stack is fixed by its architecture (see The stack at the top). For a new capability on the stack above:

1. **Web or mobile UI** → Next.js or React Native on the project's design system
2. **API** → an OpenAPI specification first, then API Gateway REST API v1 with Python Lambda handlers
3. **Real-time features** → the API Gateway WebSocket API
4. **Work between services** → events, to the project's event standard, which the project instructions name (load it before you design, specify, review or implement anything that produces, routes or receives an event)

`references/tech_stack_guide.md` compares general frameworks; it is background for reading other systems, not a menu for the project.

---

## Reference Guides

The references hold general fullstack knowledge; where they recommend a framework, database, auth product or host outside the project's stack, follow the project's stack instead.

### Architecture Patterns (`references/architecture_patterns.md`)

- Frontend component architecture (Atomic Design, Container/Presentational)
- Backend patterns (Clean Architecture, Repository Pattern)
- API design (REST conventions, and GraphQL where the project uses it)
- Database patterns (transactions, access through the RDS Data API)
- Caching strategies (cache-aside, HTTP cache headers)
- Authentication architecture (Cognito tokens)

### Development Workflows (`references/development_workflows.md`)

- Git workflows (trunk-based, conventional commits)
- CI/CD pipelines (GitHub Actions examples)
- Testing strategies (unit, integration, E2E)
- Code review process (PR templates, checklists)
- Deployment strategies (blue-green, canary, feature flags)
- Monitoring and observability (on the stack above: CloudWatch, X-Ray, ADOT and observability events)

### Tech Stack Guide (`references/tech_stack_guide.md`)

- General comparison of frontend frameworks, backend frameworks, databases, ORMs, auth products and hosting; background only

---

## Quick Reference

### Decision Matrix (stack above)

| Requirement | Choice |
|-------------|---------------|
| SEO-critical or public page | Next.js with SSR, behind CloudFront |
| Employee screens | Role-gated screens in the same Next.js web shell |
| API | OpenAPI spec + API Gateway REST API v1 + Python Lambda |
| Document-shaped or key-value data | DynamoDB |
| Relational queries, vectors | Aurora PostgreSQL Serverless v2 (Data API, pgvector) |
| Sign-in | Cognito |

### Common Issues

| Issue | Solution |
|-------|----------|
| N+1 queries | Batch the reads (DynamoDB `BatchGetItem`, one SQL query with `IN`) |
| Slow builds | Check bundle size, lazy load |
| Type errors | Enable strict mode in tsconfig |
| CORS issues | Configure CORS on the REST API (OpenAPI `x-amazon-apigateway` responses and the Lambda response headers) |
