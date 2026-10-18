---
name: "senior-fullstack"
description: Fullstack development for SkillSpoke's stack (Next.js web and React Native mobile on the CDS design system, calling Python Lambda services on aws-lambda-powertools behind API Gateway REST API v1, with Cognito sign-in), with code quality analysis scoring security and complexity. Use when the user asks to "scaffold a new project", "create a Next.js app", "analyze code quality", "audit my codebase", "what stack should I use", "generate project boilerplate", or mentions fullstack development, project setup, or tech stack comparison.
---

# Senior Fullstack

Fullstack development skill with project scaffolding and code quality analysis tools.

## SkillSpoke's stack

The stack is decided; confirm it against the solution strategy and the architecture constraints (arc42 sections 4 and 2) in the `skillspoke-docs` vault. A stack choice is not re-made per project.

| Layer | SkillSpoke |
|-------|------------|
| Web front end | Next.js, TypeScript, on the CDS design system (`cds` skills), behind CloudFront and AWS WAF |
| Mobile front end | React Native, on the CDS design system |
| API | API Gateway REST API v1, spec-first in OpenAPI; the web client uses its own generated client. HTTP API v2 is not used; live push uses the API Gateway WebSocket API |
| Backend | Python Lambdas on `aws-lambda-powertools` through `shared-chassis-lib` (see `senior-backend`). Django, Flask and FastAPI are banned; Node.js backends (Express, Fastify, NestJS) and Next.js API routes are not SkillSpoke's backend |
| Data | DynamoDB, Aurora PostgreSQL Serverless v2 through the RDS Data API, versioned S3, each owned by one service |
| Auth | Amazon Cognito, one user pool per trust domain |
| Infrastructure | CDK in Python through `shared-cdk-lib`, names from the naming command (`resource-naming`) |
| Payments | Stripe |

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

Generates generic fullstack project structures with boilerplate code. A new SkillSpoke repository is created by the `polyrepo-steward` from the project's repository templates, not by this scaffolder; use the scaffolder only for a throwaway prototype outside the SkillSpoke repositories.

**Templates:**
- `nextjs` - Next.js 14+ with App Router, TypeScript, Tailwind CSS (the only template whose front end matches SkillSpoke's; SkillSpoke styles with CDS, not ad hoc Tailwind)
- `fastapi-react`, `mern`, `django-react` - generic stacks SkillSpoke does not use (FastAPI and Django are banned; MongoDB and Express are not in the stack); never use them for SkillSpoke work

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

A new SkillSpoke repository comes from the `polyrepo-steward`; this workflow is for a throwaway prototype outside the SkillSpoke repositories.

1. Use SkillSpoke's stack (see the table at the top)
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

SkillSpoke's stack is fixed (see the table at the top). For a new SkillSpoke capability:

1. **Web or mobile UI** → Next.js or React Native on CDS
2. **API** → an OpenAPI specification first, then API Gateway REST API v1 with Python Lambda handlers
3. **Real-time features** → the API Gateway WebSocket API
4. **Work between services** → SkillSpoke events through the events service (`skillspoke-events`)

`references/tech_stack_guide.md` compares general frameworks; it is background for reading other systems, not a menu for SkillSpoke.

---

## Reference Guides

The references hold general fullstack knowledge; where they recommend a framework, database, auth product or host outside SkillSpoke's stack, follow the stack table at the top instead.

### Architecture Patterns (`references/architecture_patterns.md`)

- Frontend component architecture (Atomic Design, Container/Presentational)
- Backend patterns (Clean Architecture, Repository Pattern)
- API design (REST conventions; SkillSpoke uses REST, not GraphQL)
- Database patterns (transactions, access through the RDS Data API)
- Caching strategies (cache-aside, HTTP cache headers)
- Authentication architecture (Cognito tokens)

### Development Workflows (`references/development_workflows.md`)

- Git workflows (trunk-based, conventional commits)
- CI/CD pipelines (GitHub Actions examples)
- Testing strategies (unit, integration, E2E)
- Code review process (PR templates, checklists)
- Deployment strategies (blue-green, canary, feature flags)
- Monitoring and observability (in SkillSpoke: CloudWatch, X-Ray, ADOT and observability events)

### Tech Stack Guide (`references/tech_stack_guide.md`)

- General comparison of frontend frameworks, backend frameworks, databases, ORMs, auth products and hosting; background only

---

## Quick Reference

### SkillSpoke Decision Matrix

| Requirement | SkillSpoke |
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
