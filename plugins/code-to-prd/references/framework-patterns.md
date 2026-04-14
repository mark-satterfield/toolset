# Framework-Specific Patterns

Quick reference for identifying routes, components, state, and APIs across frontend and backend frameworks.

## React (CRA / Vite)

| Aspect | Where to Look |
|--------|--------------|
| Routes | `react-router-dom` — `<Route path="...">` or `createBrowserRouter` |
| Components | `.tsx` / `.jsx` files, default exports |
| State | Redux (`store/`), Zustand, Jotai, Recoil, React Context |
| API | `axios`, `fetch`, TanStack Query (`useQuery`), SWR (`useSWR`) |
| Forms | React Hook Form, Formik, Ant Design Form, custom `useState` |
| i18n | `react-i18next`, `react-intl` |

## Next.js (App Router)

| Aspect | Where to Look |
|--------|--------------|
| Routes | `app/` directory — `page.tsx` = route, folders = segments |
| Layouts | `layout.tsx` per directory |
| Loading | `loading.tsx`, `error.tsx`, `not-found.tsx` |
| API routes | `app/api/` or `pages/api/` (Pages Router) |
| Server actions | `"use server"` directive |
| Middleware | `middleware.ts` at root |

## Next.js (Pages Router)

| Aspect | Where to Look |
|--------|--------------|
| Routes | `pages/` directory — filename = route |
| Data fetching | `getServerSideProps`, `getStaticProps`, `getStaticPaths` |
| API routes | `pages/api/` |

## Vue 3

| Aspect | Where to Look |
|--------|--------------|
| Routes | `vue-router` — `routes` array in `router/index.ts` |
| Components | `.vue` SFCs (`<template>`, `<script setup>`, `<style>`) |
| State | Pinia (`stores/`), Vuex (`store/`) |
| API | `axios`, `fetch`, VueQuery |
| Forms | VeeValidate, FormKit, custom `ref()` / `reactive()` |
| i18n | `vue-i18n` |

## Nuxt 3

| Aspect | Where to Look |
|--------|--------------|
| Routes | `pages/` directory (file-system routing) |
| Layouts | `layouts/` |
| API routes | `server/api/` |
| Data fetching | `useFetch`, `useAsyncData`, `$fetch` |
| State | `useState`, Pinia |
| Middleware | `middleware/` |

## Angular

| Aspect | Where to Look |
|--------|--------------|
| Routes | `app-routing.module.ts` or `Routes` array |
| Components | `@Component` decorator, `*.component.ts` |
| State | NgRx (`store/`), services with `BehaviorSubject` |
| API | `HttpClient` in services |
| Forms | Reactive Forms (`FormGroup`), Template-driven forms |
| i18n | `@angular/localize`, `ngx-translate` |
| Guards | `CanActivate`, `CanDeactivate` |

## Svelte / SvelteKit

| Aspect | Where to Look |
|--------|--------------|
| Routes | `src/routes/` (file-system routing with `+page.svelte`) |
| Layouts | `+layout.svelte` |
| Data loading | `+page.ts` / `+page.server.ts` (`load` function) |
| API routes | `+server.ts` |
| State | Svelte stores (`writable`, `readable`, `derived`) |

## NestJS

| Aspect | Where to Look |
|--------|--------------|
| Routes | `@Controller('prefix')` + `@Get()/@Post()/@Put()/@Delete()` decorators |
| Modules | `*.module.ts` — `@Module({ controllers, providers, imports })` |
| Services | `*.service.ts` — injected via constructor, contains business logic |
| DTOs | `*.dto.ts` — `class-validator` decorators define validation rules |
| Entities | `*.entity.ts` — TypeORM `@Entity()` / Prisma schemas |
| Auth | `@UseGuards(AuthGuard)`, `@Roles('admin')`, Passport strategies |
| Middleware | `*.middleware.ts`, registered in module `configure()` |
| Pipes | `ValidationPipe`, `ParseIntPipe` — input transformation |
| Config | `ConfigModule`, `.env` files, `config/` directory |

## Express / Fastify

| Aspect | Where to Look |
|--------|--------------|
| Routes | `router.get('/path', handler)`, `app.post('/path', ...)` |
| Middleware | `app.use(...)`, `router.use(...)` |
| Controllers | Route handler files in `routes/`, `controllers/` |
| Models | Mongoose schemas (`*.model.ts`), Sequelize models, Prisma |
| Auth | `passport`, `jsonwebtoken`, middleware auth checks |
| Validation | `express-validator`, `joi`, `zod`, custom middleware |

## Django

| Aspect | Where to Look |
|--------|--------------|
| Routes | `urls.py` — `urlpatterns = [path('...', view)]` |
| Views | `views.py` — function-based or class-based views (`APIView`, `ViewSet`) |
| Models | `models.py` — `class MyModel(models.Model)` with field definitions |
| Forms | `forms.py` — `ModelForm`, `Form` with validation |
| Serializers | `serializers.py` (DRF) — `ModelSerializer`, field-level validation |
| Admin | `admin.py` — `@admin.register`, `list_display`, `search_fields`, `list_filter` |
| Templates | `templates/` — Jinja2/Django template HTML files |
| Middleware | `MIDDLEWARE` in `settings.py` |
| Auth | `django.contrib.auth`, `rest_framework.permissions`, `@login_required` |
| Signals | `signals.py` — `post_save`, `pre_delete` hooks (hidden business logic) |
| Management commands | `management/commands/` — CLI operations |
| Celery tasks | `tasks.py` — async/background operations |

## Django REST Framework (DRF)

| Aspect | Where to Look |
|--------|--------------|
| Endpoints | `router.register('prefix', ViewSet)` in `urls.py` |
| ViewSets | `viewsets.py` — `ModelViewSet` (full CRUD), `ReadOnlyModelViewSet` |
| Serializers | `serializers.py` — field types, validators, nested relations |
| Permissions | `permission_classes = [IsAuthenticated, IsAdminUser]` |
| Filtering | `django-filter`, `search_fields`, `ordering_fields` |
| Pagination | `DEFAULT_PAGINATION_CLASS` in settings, per-view override |
| Throttling | `DEFAULT_THROTTLE_CLASSES`, per-view `throttle_classes` |

## FastAPI

| Aspect | Where to Look |
|--------|--------------|
| Routes | `@app.get('/path')`, `@router.post('/path')` decorators |
| Models | Pydantic `BaseModel` classes — request/response schemas |
| Dependencies | `Depends(...)` — auth, DB sessions, shared logic |
| DB | SQLAlchemy models, Tortoise ORM, or raw SQL |
| Auth | `OAuth2PasswordBearer`, JWT middleware, `Depends(get_current_user)` |
| Background | `BackgroundTasks`, Celery integration |

## AWS CDK (Python + TypeScript)

| Aspect | Where to Look |
|--------|--------------|
| Stack definitions | Classes ending in `Stack` inheriting from `Stack` — `class FooStack(Stack)` (Python) or `class FooStack extends Stack` (TS) |
| Construct definitions | Classes ending in `Construct` inheriting from `Construct` |
| Lambda functions | `aws_lambda.Function(...)` / `lambda_.Function(...)` (Python), `new lambda.Function(...)` / `new NodejsFunction(...)` / `new PythonFunction(...)` (TS) |
| DynamoDB tables | `aws_dynamodb.Table(...)` (Python), `new dynamodb.Table(...)` (TS) |
| API Gateway | `aws_apigateway.RestApi(...)` / `LambdaRestApi(...)` (Python), `new RestApi(...)` / `new HttpApi(...)` (TS) |
| SQS queues | `aws_sqs.Queue(...)` (Python), `new sqs.Queue(...)` (TS) |
| EventBridge | `aws_events.EventBus(...)`, `aws_events.Rule(...)` |
| Cognito | `aws_cognito.UserPool(...)` |
| SSM cross-stack wiring | `ssm.StringParameter.fromStringParameterName(...)` (consume), `ssm.StringParameter(...)` (produce) |
| CloudFront | `aws_cloudfront.Distribution(...)` + `aws_cloudfront_origins.S3Origin(...)` |
| Stack props | `class FooStackProps(StackProps)` (Python), `interface FooStackProps extends StackProps` (TS) |
| CDK app entry | `app.py` (Python), `bin/*.ts` (TypeScript) |

**Key CDK patterns to document:**
- Cross-stack SSM parameter paths (interface contract between stacks)
- Lambda event sources: `lambda_.add_event_source(SqsEventSource(...))` or `add_event_source(new SqsEventSource(...))`
- Lambda Powertools layer: ARN-pinned layer attachment
- 4-wave deployment: infra → layers → services → frontends (ordering constraint)

## AWS Lambda (Python 3.12)

| Aspect | Where to Look |
|--------|--------------|
| Handler function | `def handler(event, context)` in main file |
| Powertools logger | `@logger.inject_lambda_context` decorator |
| Powertools tracer | `@tracer.capture_lambda_handler` decorator |
| Powertools metrics | `@metrics.log_metrics` decorator |
| Event source type | `event` structure: API Gateway (`event["httpMethod"]`), SQS (`event["Records"]`), EventBridge (`event["detail"]`) |
| Environment variables | `os.environ["PARAM_NAME"]` — often SSM params injected at deploy time |
| DynamoDB access | `boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])` |
| Response format | API Gateway expects `{"statusCode": 200, "body": json.dumps(...)}` |
| Error handling | Try/except with structured log + re-raise vs returning error response |

**Lambda Powertools V3 patterns:**
```python
from aws_lambda_powertools import Logger, Tracer, Metrics
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="SkillSpoke")

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event, context):
    ...
```

## GitHub Actions

| Aspect | Where to Look |
|--------|--------------|
| Trigger events | `on:` block — `push`, `pull_request`, `workflow_dispatch`, `schedule` |
| Job definitions | `jobs:` block — each named job with `runs-on`, `steps` |
| Environment secrets | `${{ secrets.SECRET_NAME }}` |
| Environment variables | `env:` block at workflow/job/step level |
| Deployment environments | `environment:` field on jobs (dev/staging/prod) |
| Step outputs | `id:` + `${{ steps.id.outputs.name }}` |
| Conditional execution | `if: github.ref == 'refs/heads/main'` |
| Matrix builds | `strategy.matrix` — multiple versions or environments in one workflow |
| Artifact upload | `actions/upload-artifact@v4` |
| CDK deploy step | `run: cdk deploy --all` or task runner invocation |

## Taskfile (go-task)

| Aspect | Where to Look |
|--------|--------------|
| Task targets | Top-level keys under `tasks:` |
| Task description | `desc:` field on each task |
| Task dependencies | `deps:` array — tasks that must run first |
| Commands | `cmds:` array of shell commands |
| Environment variables | `env:` block at task level |
| Dotenv loading | `dotenv:` field |
| Directory context | `dir:` field (task runs in this directory) |
| Silent mode | `silent: true` suppresses echo |
| Default task | `default:` task alias |

**4-wave deployment pattern:**
```yaml
tasks:
  deploy:infra:
    desc: Deploy base network, IAM, shared resources
    cmds: [cdk deploy InfraStack]
  deploy:layers:
    desc: Deploy Lambda layers
    deps: [deploy:infra]
    cmds: [cdk deploy LayersStack]
  deploy:services:
    desc: Deploy backend Lambda stacks
    deps: [deploy:layers]
    cmds: [cdk deploy --all --exclusively services/*]
  deploy:frontends:
    desc: Deploy Next.js static export + CloudFront
    deps: [deploy:services]
    cmds: [cdk deploy FrontendStack]
```

## React Native + Expo (SDK 54+ / Expo Router 6)

| Aspect | Where to Look |
|--------|--------------|
| Screens | `app/` directory — Expo Router file-system routing (same as Next.js App Router) |
| Layouts | `app/_layout.tsx` — root layout, `app/(tabs)/_layout.tsx` — tab layout |
| Tab navigation | `app/(tabs)/` directory — each file = one tab |
| Stack navigation | `expo-router` `<Stack>` component in `_layout.tsx` |
| Styling | NativeWind — `className` props with Tailwind classes |
| Native modules | `expo-*` packages (`expo-camera`, `expo-location`, etc.) |
| State | Zustand, React Context, or TanStack Query for server state |
| API calls | Same patterns as React: `fetch`, axios, TanStack Query |
| Auth guards | `useRouter().replace('/login')` in `useEffect` or layout-level redirect |
| Deep links | `app.json` `scheme:` field + Expo Router dynamic routes |
| Notifications | `expo-notifications` |

**Key Expo Router patterns:**
```
app/
├── _layout.tsx          # Root layout (auth check, theme provider)
├── (tabs)/
│   ├── _layout.tsx      # Tab bar config
│   ├── index.tsx        # Home tab
│   └── profile.tsx      # Profile tab
├── (auth)/
│   ├── login.tsx        # Login screen
│   └── register.tsx     # Register screen
└── [id]/
    └── detail.tsx       # Dynamic screen with `id` param
```

## MCP Servers (fastmcp / Python)

| Aspect | Where to Look |
|--------|--------------|
| Server definition | `mcp = FastMCP("server-name")` or `server = Server("server-name")` |
| Tool registration | `@mcp.tool()` decorator on async functions |
| Tool input schema | Function parameters with type hints — auto-converted to JSON Schema |
| Tool description | Docstring on the tool function |
| Resources | `@mcp.resource("path://pattern")` decorator |
| Prompts | `@mcp.prompt()` decorator |
| Transport | `mcp.run(transport="stdio")` or `mcp.run(transport="sse")` |
| Error handling | Raise `McpError` with `ErrorCode` for protocol-level errors |

**fastmcp tool pattern:**
```python
from fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
async def search_users(query: str, limit: int = 10) -> list[dict]:
    """Search users by name or email. Returns list of user objects."""
    ...
```

**What to document per MCP server:**
- Each tool: name, description, input params (type, required, description), return shape
- Transport type: stdio (embedded) vs SSE/HTTP (standalone service)
- Auth mechanism (if any)
- Which Claude agent/workflow uses this server

## Common Patterns Across Frameworks

### Mock Detection
```
# Likely mock
setTimeout(() => resolve(data), 500)
Promise.resolve(mockData)
import { data } from './fixtures'
faker.name.firstName()

# Likely real
axios.get('/api/users')
fetch('/api/data')
httpClient.post(url, body)
useSWR('/api/resource')
```

### Permission Patterns
```
# React
{hasPermission('admin') && <Button>Delete</Button>}
<ProtectedRoute roles={['admin', 'manager']}>

# Vue
v-if="user.role === 'admin'"
v-permission="'user:delete'"

# Angular
*ngIf="authService.hasRole('admin')"
canActivate: [AuthGuard]
```

### Form Validation
```
# React Hook Form
{ required: 'Name is required', maxLength: { value: 50, message: 'Too long' } }

# VeeValidate (Vue)
rules="required|email|max:100"

# Angular Reactive Forms
Validators.required, Validators.minLength(3), Validators.pattern(...)

# NestJS (class-validator)
@IsString() @IsNotEmpty() @MaxLength(50) name: string;
@IsEmail() email: string;
@IsEnum(UserRole) role: UserRole;

# Django Forms
name = forms.CharField(max_length=50, required=True)
email = forms.EmailField()

# DRF Serializers
name = serializers.CharField(max_length=50)
email = serializers.EmailField(required=True)

# FastAPI (Pydantic)
name: str = Field(max_length=50)
email: EmailStr
```

### Database Model Patterns
```
# Django
class Order(models.Model):
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2)

# TypeORM (NestJS)
@Entity()
export class Order {
    @Column({ type: 'enum', enum: OrderStatus })
    status: OrderStatus;
    @ManyToOne(() => User)
    user: User;
}

# Prisma
model Order {
    status  OrderStatus
    user    User @relation(fields: [userId], references: [id])
    total   Decimal
}
```
