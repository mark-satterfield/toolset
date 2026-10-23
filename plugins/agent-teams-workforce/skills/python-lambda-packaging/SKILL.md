---
name: python-lambda-packaging
description: The procedure an agent follows whenever its work touches a Python import, the dependencies or dependency groups of a pyproject.toml, a lock file, the packaging of an AWS Lambda function, a Lambda layer, a CDK function or layer asset, or the build of a Python library - inventory what the code imports, what every attached layer and the runtime provide (nested packages included) and what each listed package brings with it; decide for each package where it comes from and where it is declared; decide shared layer or function zip; build every artifact with explicit contents for the Lambda platform and architecture; check for duplicates, unresolvable versions, size and a working import; and record the decisions. Use before adding, removing, moving or upgrading any Python dependency, before writing or changing any bundling command, layer or library build, and when reviewing such a change.
user-invocable: true
---

# Packaging Python for AWS Lambda: decide, build, check

This skill is a procedure, not background reading. When your work touches anything in the list
below, run every step in order, and put the record of step 8 in your result. A reviewer judges the
change against these steps.

It applies when your work:

- adds, removes or changes an `import` of a package that is not in the standard library or in the
  repository's own source;
- edits `[project] dependencies`, `[project.optional-dependencies]`, `[dependency-groups]` or a
  `[tool.uv]` constraint in a `pyproject.toml`, or a lock file (`uv.lock`, `requirements*.txt`);
- writes or changes the build of a Lambda function zip, a Lambda layer, a CDK `Code.from_asset`
  bundling command, a `LayerVersion`, the `layers` of a function, or a function's `architecture` or
  `runtime`;
- writes or changes the build configuration of a Python library (`[build-system]`,
  `[tool.hatch.build]`, `[tool.setuptools]`).

The arrangement of layers is expected to change as projects develop: packages move into and out of
shared layers, layers get new versions, runtimes change. Never carry a conclusion from an earlier
Task, another repository or memory. Run steps 1 to 3 against the code, the lock files and the layer
versions as they are now.

## The facts the steps rest on

Each step cites the facts it follows from. Verify a fact with the AWS documentation tools when your
work depends on a detail that may have changed.

- **F1. Import order.** Python on Lambda searches the function zip (`/var/task`) first, then the
  layers (`/opt/python/lib/pythonX.Y/site-packages`, then `/opt/python`), then the runtime's own
  packages (`/var/lang/lib/pythonX.Y/site-packages`). The first copy found is the one imported; every
  other copy is dead weight, and a stale copy in the zip silently shadows a newer one in a layer.
  https://docs.aws.amazon.com/lambda/latest/dg/python-package.html ,
  https://aws.amazon.com/blogs/compute/python-3-11-runtime-now-available-in-aws-lambda/
- **F2. Layers merge file by file.** Layers are extracted into `/opt` in the order the function lists
  them; where two layers hold the same file, the later layer's file wins. Two layers carrying one
  package can therefore leave a mixed tree of two versions' files. A package in two layers is a
  defect, never a precedence choice.
  https://docs.aws.amazon.com/lambda/latest/dg/adding-layers.html
- **F3. The 250 MB limit counts every copy.** The unzipped function plus all its layers, AWS-managed
  layers included, may not exceed 250 MB; a function takes at most 5 layers; a zip uploaded directly
  is at most 50 MB (larger goes through S3). The limits cannot be raised. A container-image function
  allows 10 GB but takes no layers at all. Every function version and every layer version also counts
  toward 300 GB of code storage per Region, which cannot be raised either.
  https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html ,
  https://docs.aws.amazon.com/lambda/latest/dg/adding-layers.html
- **F4. The runtime SDK floats.** Every Python runtime ships `boto3`, `botocore` and their
  dependencies, and Lambda updates them without notice. AWS recommends packaging the SDK yourself for
  version control, and warns that shipping one of the SDK's dependencies (for example `urllib3`)
  without the SDK breaks when the runtime SDK is updated. A layer can lock the SDK version. `requests`
  is not in the runtime.
  https://docs.aws.amazon.com/lambda/latest/dg/python-package.html ,
  https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html ,
  https://aws.amazon.com/blogs/compute/upcoming-changes-to-the-python-sdk-in-aws-lambda/
- **F5. Native code is tied to platform, architecture and Python minor.** A package with C, C++ or
  Rust code (for example pydantic-core, cryptography, numpy, orjson, lxml) must come from a Linux
  wheel built for the function's architecture (x86_64 or arm64) and Python minor version. A macOS
  wheel, a wheel for the other architecture, or a layer built for another Python minor fails at
  import, not at deploy. python3.10 and 3.11 run on Amazon Linux 2 (glibc 2.26); python3.12 and later
  run on Amazon Linux 2023 (glibc 2.34). A wheel tagged for a glibc at or below the runtime's runs:
  `manylinux2014` (glibc 2.17) everywhere, up to `manylinux_2_34` on 3.12 and later; `manylinux_2_28`
  and newer fail on 3.11 and earlier. A package that needs a system shared library or executable its
  wheel does not contain needs it in a layer's top-level `lib/` (on `LD_LIBRARY_PATH`) or `bin/` (on
  `PATH`), or a container image. A layer's compatible-runtimes field is a filter, not a check.
  https://docs.aws.amazon.com/lambda/latest/dg/python-package.html ,
  https://docs.aws.amazon.com/powertools/python/latest/build_recipes/cross-platform/ ,
  https://docs.aws.amazon.com/lambda/latest/dg/python-layers.html ,
  https://docs.aws.amazon.com/lambda/latest/dg/packaging-layers.html
- **F6. No bytecode.** AWS says not to ship `__pycache__`, because bytecode compiled on another OS
  or architecture may not be compatible. `pip install` compiles bytecode by default; `uv pip install`
  does not. No AWS source measures a gain from shipping `.pyc`.
  https://docs.aws.amazon.com/lambda/latest/dg/python-package.html ,
  https://docs.astral.sh/uv/pip/compatibility/
- **F7. Size and imports cost cold start.** Every package is downloaded, unpacked and imported at
  init, and init is billed. A layer does not make a cold start faster; Powertools measures a
  single-zip deployment as slightly faster to start than a layered one. Layers buy reuse and smaller
  deploys, not speed.
  https://aws.amazon.com/blogs/compute/understanding-and-remediating-cold-starts-an-aws-lambda-perspective/ ,
  https://docs.aws.amazon.com/powertools/python/latest/build_recipes/build-tools/
- **F8. Where a pyproject declares a package.** `[project] dependencies` is published metadata and
  is what a build that bundles runtime packages installs. `[dependency-groups]` (PEP 735) never
  becomes package metadata and is for development and tests. `[project.optional-dependencies]` is a
  published extra a consumer may request, never a place for development tools. uv's `dev` group is
  synced by default and excluded with `--no-dev`.
  https://packaging.python.org/en/latest/specifications/dependency-groups/ ,
  https://docs.astral.sh/uv/concepts/projects/dependencies/
- **F9. Constraints pin without installing.** `[tool.uv] constraint-dependencies` (or `-c` /
  `UV_CONSTRAINT`) limits the version of a package only if something already pulls it in. It is the
  tool for holding a package at a layer's version; overrides are a last resort for wrong metadata.
  https://docs.astral.sh/uv/concepts/resolution/
- **F10. A layer version is immutable.** A function names an exact layer version ARN. Changing a
  layer means publishing a new version and moving every function to it; a CDK update to a layer
  creates a new version and deletes the old one unless the layer is retained. A function in another
  stack that still names the deleted version keeps running, but its next deploy fails.
  https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html ,
  https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_lambda/README.html
- **F11. CDK copies what it is told to.** With a `bundling` command, the directory `Code.from_asset`
  names is mounted whole into the bundling container, the content of `/asset-output` becomes the
  asset, and `Code.from_asset(..., exclude=[...])` has no effect, so the command alone decides what
  goes in. `PythonLayerVersion` and `PythonFunction` default to x86_64; an arm64 build
  must say so.
  https://constructs.dev/packages/aws-cdk-lib/v/2.274.0/api/Code?lang=python&submodule=aws_lambda ,
  https://constructs.dev/packages/@aws-cdk/aws-lambda-python-alpha/v/2.274.0-alpha.0/api/PythonLayerVersion?lang=python
- **F12. Package metadata is load-bearing.** `importlib.metadata`, `importlib.metadata.version()`
  and entry points read `*.dist-info`; deleting it, or deleting `docs`, `*.txt` or `*.md` inside
  installed packages, can break libraries.
  https://packaging.python.org/en/latest/specifications/entry-points/ ,
  https://docs.aws.amazon.com/powertools/python/latest/build_recipes/performance-optimization/
- **F13. A private index is needed at install time only.** An install that includes a package from a
  private registry fails without the index URL and its token. CDK bundling takes them through its
  `environment`; they are used during bundling and are not in the asset. `build_args` also works but
  rebuilds the bundling image on every synth. With more than one index, uv's default
  `--index-strategy first-index` takes each package only from the first index that has it, which
  blocks a public package of the same name from replacing a private one; `unsafe-best-match`
  removes that protection.
  https://constructs.dev/packages/@aws-cdk/aws-lambda-python-alpha/v/2.274.0-alpha.0?lang=python ,
  https://docs.astral.sh/uv/concepts/indexes/

## Step 1. Name the units and their builds

Before reading a dependency, write down each unit your work affects and what builds it:

- each **function** (its handler, `runtime`, `architecture`, the ordered `layers` list, and the
  command or construct that builds its zip);
- each **layer** (its name, the version a function uses, the Python minor and architecture it was
  built for, and the lock or requirements file it was built from, in whichever repository owns it);
- each **library** (its build backend and the package directories it ships).

Start from the matrix, then confirm in the code. Load the `matrix` skill and run `atw-matrix layers`
for the layers and their users. For each layer your units attach, `atw-matrix node layer:<id>` gives
its home stack, and `atw-matrix node stack:<id>` gives that stack's repository, where the layer is
built. Then read the
units from the CDK code and the build files, not from naming. Where the code and the matrix disagree,
the code is what deploys: work from the code, and name the disagreement in your result.

## Step 2. Inventory what is provided and what is imported

1. **What the code imports at runtime.** List the third-party imports of the shipped source, tests
   excluded. Map each import name to its distribution, because they differ (`yaml` is `PyYAML`,
   `jwt` is `PyJWT`): in the project's environment run
   `uv run python -c "import importlib.metadata as m, json; print(json.dumps(m.packages_distributions(), indent=1))"`.
2. **What each attached layer provides, nested packages included.** A layer installed with its
   dependencies holds every nested package as a top-level `*.dist-info` directory, so list those:
   - a layer built from a lock file you can read: `uv export --frozen --no-dev --no-emit-project --no-hashes`
     in its project gives the full set with exact versions;
   - a published layer version, AWS-managed layers included: fetch its zip and list it -
     `aws lambda get-layer-version --layer-name <name or ARN> --version-number <n> --query Content.Location --output text`,
     download that URL, and `unzip -l layer.zip | grep -E 'dist-info/METADATA$'`.
   Never assume what a layer holds from its name, its documentation or the packages `atw-matrix layers`
   records for it; the Powertools layer's exact extras, for example, are not listed in its
   documentation (F2, F3).
3. **What the runtime provides, and at which version.** The runtime provides the SDK F4 names and no
   other third-party package. Read the SDK's versions and the names of its dependencies, the SDK set
   that step 3 rule 4 decides and step 7.4 checks:
   `docker run --rm --platform linux/<amd64|arm64> --entrypoint /var/lang/bin/python3 public.ecr.aws/lambda/python:<minor> -c "import boto3, botocore, importlib.metadata as m; print(boto3.__version__, botocore.__version__, m.requires('boto3'), m.requires('botocore'))"`.
   The deployed runtime depends on the Region and can differ from the image; where the version
   matters to the decision, also invoke a deployed function on that runtime that prints the same.
4. **What each listed package brings.** `uv tree --no-dev` shows the locked runtime tree;
   `uv tree --invert --package <name>` shows which listed package pulls a package in.

## Step 3. Decide, for each distribution, where it comes from

Take every distribution from step 2.1 and every entry already in `[project] dependencies`, and apply
the first rule that matches, with one exception: rule 4 decides `boto3`, `botocore` and every package
of the SDK set from step 2.3 before rules 2 and 3 are tried, because a package of that set that
arrives through a layer or another package is exactly the split F4 warns about. Write the decision
down for step 8.

1. **Development or test only** (pytest, linters, type checkers, moto, stubs): `[dependency-groups]`,
   never `dependencies` and never an extra (F8).
2. **Provided by an attached layer, directly or nested inside a package the layer carries**: not in
   `dependencies`, so it is not bundled again (F1, F3). If the tests or local development import it,
   put it in a development group and hold it at the layer's exact version with a
   `constraint-dependencies` entry taken from the layer's inventory (F9). When the layer version
   changes, update the constraint in the same change.
3. **Already brought in by another package this unit declares**: not listed (step 2.4 names the
   parent). If the code needs a narrower version than the parent allows, add a constraint, not a
   dependency (F9). Record the parent, so that a change to the parent is checked against this import.
4. **The AWS SDK and its dependencies (the SDK set)**: decide the source explicitly; never leave it to
   accident (F4).
   - If an attached layer pins `botocore`, rule 2 applies to the SDK and to the SDK packages that
     layer carries.
   - If the zip or any attached layer ships any package of the SDK set, whether listed or brought by
     another package (`requests` brings `urllib3`, for example; step 2.4 names the parent), then
     `botocore`, and `boto3` when the code imports it, ships too, from the zip or a layer, resolved
     in the same lock as that package or held to it with a constraint (F9). Otherwise
     a runtime SDK update meets a shipped dependency it was not built with.
   - Relying on the runtime copy is allowed only when nothing ships any package of the SDK set; record
     it as "runtime SDK, version floats".
   - Otherwise list it in `dependencies` or move it into the shared layer (step 4).
5. **Powertools for AWS Lambda**: when the function attaches the AWS-managed Powertools layer, rule 2
   applies, with the extras its code uses checked against the layer's inventory (an extra such as
   `parser` brings pydantic, which is native code, F5). For local development, Powertools documents
   the development-group install with the `aws-sdk` extra (`aws-lambda-powertools[aws-sdk]`), pinned
   to the version the layer carries.
   https://docs.aws.amazon.com/powertools/python/latest/getting-started/install/ . Pin the layer's
   version number in the ARN, and pick the ARN for the function's Python minor and architecture.
6. **Not provided by anything**: `[project] dependencies`, with a lower bound and no upper cap, and let
   the lock file hold the exact version (step 7 checks the bound resolves).

**A published library differs.** A library's `[project] dependencies` is what every consumer's
resolver sees, so a library declares every package its shipped code imports at runtime, whether or not
some layer provides it; leaving one out makes the library broken anywhere outside that layer
arrangement. Use lower bounds, never `==` pins, and keep test tools in groups (F8). The function that
bundles the library is where layer-provided packages are kept out of the zip (step 5, `--no-emit-package`).

## Step 4. Decide shared layer or function zip

For every third-party package that ends up shipped (rules 4 to 6):

1. **A project's own first-party library never goes into a shared third-party layer.** It ships in
   the function zip as a dependency, or in a layer of its own if the project's architecture defines
   one.
2. **Shared layer only when common.** A third-party package goes into a shared layer only when most of
   the project's Python functions import it; one or two consumers means the function zip. Check with
   the matrix lookup of step 1 whether a shared layer already carries it, count the functions that
   import it with the code search `graphrag-lookup` describes, and confirm each consumer in its
   repository's code.
   Moving a package into a shared layer changes the layer's repository and every consuming function
   (step 3 rule 2 in each), and work confined to one repository cannot make that change. In that
   case ship the package in this function's zip, and report the candidate move in `upstreamMissing`
   (or `notes` where the caller's schema has no such field): the package, the shared layer, the
   repository that builds it (step 1) and the consumers you counted.
3. **Every shared layer is built per architecture and per Python minor** when it holds any native code
   (F5), and it holds no package that another attached layer also holds (F2).
4. **Count before adding.** Sum the unzipped size of the zip and every layer, AWS-managed ones
   included (F3); keep at most 5 layers; set the layer order deliberately, since a later layer wins a
   shared file (F2). If the sum approaches 250 MB, first remove duplicates and unused packages; if it
   still does not fit, the function becomes a container image, which takes no layers and needs a new
   function.
5. **Weigh F7.** A layer is not a cold-start optimisation; do not move a package into a layer to speed
   up start. Reduce what is imported at init instead.
6. **Changing a layer changes every function on it** (F10): publish the new version, move each
   function to it, and re-run steps 2 and 3 for each. Retain the old versions of a layer that
   functions outside its own stack attach (F10; the CDK setting is in step 5). Publish a new layer
   version only when its contents change, since every version counts toward the Region's code
   storage (F3).
7. **Native libraries outside wheels**: for a package that needs a system library or executable its
   wheel lacks, build that file on Amazon Linux for the function's architecture into a layer as F5
   places it, and check F3; if it does not fit, the function becomes a container image.

## Step 5. Build with explicit contents

Every artifact states exactly what goes in; nothing enters by copying a whole directory.

**A function zip (or a CDK bundling command that builds one).**

1. Start from an empty output directory every time; an install into an existing target merges stale
   packages.
2. Produce the runtime-only requirement list from the lock, leaving out every package step 3 assigned
   to a layer or the runtime:
   `uv export --frozen --no-dev --no-default-groups --no-emit-project --no-emit-package <each layer-provided package> -o /tmp/requirements.txt`.
   `--no-emit-package` drops only the named packages, so name each nested one too (step 2.4 lists them).
3. Install exactly that list for the Lambda platform, with no dependency resolution of its own and no
   bytecode (F5, F6):
   `uv pip install --target <out> --no-deps --only-binary :all: --python-platform <tag> --python-version <runtime minor> -r /tmp/requirements.txt`.
   Take `<tag>` from the runtime's glibc (F5): `x86_64-manylinux2014` or `aarch64-manylinux2014` for
   python3.11 and earlier, `x86_64-manylinux_2_34` or `aarch64-manylinux_2_34` for python3.12 and
   later. Inside a CDK bundling image for the function's runtime and Docker platform the same
   command runs without `--python-platform` and `--python-version`, since the image is the target.
   An sdist-only package must be built in an Amazon Linux environment; prefer a package with wheels.
   When the lock includes a package from a private index, pass that index to the install as F13
   requires: in CDK through the bundling `environment`, as `UV_INDEX`, or `UV_DEFAULT_INDEX` when
   that index also serves the public packages.
4. Copy only the handler's source package into the root of the output, never the repository root or
   `.` (F11). Tests, `.venv`, caches, docs and build files are not copied.
5. Remove what the install itself leaves that the runtime never reads: `__pycache__/`, `*.pyc`, the
   console scripts the installer writes into `bin/` inside the install target (a layer's top-level
   `bin/` from step 4.7 is a different directory and stays), uv's `.lock` file, and `INSTALLER`,
   `REQUESTED` and `direct_url.json` inside `*.dist-info`. Keep `*.dist-info` itself and its `METADATA`, `entry_points.txt` and `top_level.txt` (F12). Do not
   delete `tests`, `docs`, `*.txt` or `*.md` inside third-party packages by name; some packages import
   modules with those names (for example `numpy.testing`).
6. Files are mode 644 and directories and executables 755.

**In CDK.** Follow `aws-cdk-development` for the construct choice (the stable `aws_lambda.Function`
with `Code.from_asset` bundling, not the alpha `PythonFunction`), and make its bundling command the
sequence above. Set the bundling image to the function's runtime (`runtime.bundling_image`) and
`BundlingOptions(platform=architecture.docker_platform)`, so the container installs wheels for the
function's architecture whatever machine runs the synth. Name as the asset path the smallest directory
that holds `pyproject.toml`, `uv.lock` and the source package, and copy into `/asset-output` only by
name (F11). Pin the uv version the command installs to the exact version that `required-version`
under the repository's `[tool.uv]` names (add one in the same change if it names none), so the asset
does not change between synths. A `LayerVersion` is built the same way into `/asset-output/python`, with
`compatible_architectures` and `compatible_runtimes` set to what it was built for (F11), and with
`removal_policy=RemovalPolicy.RETAIN` when functions outside its own stack attach it (F10).

**A library wheel.** Keep tests outside the package directory (a top-level `tests/` beside `src/`).
List what the wheel ships with `unzip -l dist/*.whl` and its declared dependencies with
`unzip -p dist/*.whl '*.dist-info/METADATA' | grep Requires-Dist`; nothing from a test, a cache or a
dependency group may appear. Exclude with the backend's own setting (for hatchling,
`[tool.hatch.build.targets.wheel] exclude`) only when a file cannot live outside the package.

## Step 6. Do not edit around the lock

Never edit a lock file by hand and never change a published library's version or a pin to get ahead
of what the package index holds; follow the project's instructions on library versions. After
changing `pyproject.toml`, run `uv lock` and commit the lock with the change.

In the project of a function or a layer, set `[tool.uv] required-environments` to Linux on the
architectures it is built for (for example `"sys_platform == 'linux' and platform_machine == 'aarch64'"`),
so that a locked version without a wheel for the function's platform fails at `uv lock` rather than
at build or import time. It covers only packages that publish no source distribution; for the rest,
step 5's install and the import check of step 7 decide.
https://docs.astral.sh/uv/concepts/resolution/#required-environments

## Step 7. Check the result

Run each check; a claim without its output is not a check.

1. **The lock agrees with pyproject:** `uv lock --check`.
2. **Every bound resolves:** the lock resolves after step 6; for a published library also
   `uv lock --resolution lowest-direct` in a scratch copy, and resolve with `--no-sources` so only
   published metadata is used. No lower bound may exceed the version a layer that provides the package
   carries.
3. **No duplicates across zip and layers:** list the distributions of the output directory and of each
   attached layer and intersect them; the result must be empty.
   `find <dir> -maxdepth 2 -name '*.dist-info' -exec basename {} \; | sed 's/-[0-9].*//' | tr 'A-Z_' 'a-z-' | sort -u`
   for each directory (a layer's content is under `python/`), then `comm -12` on each pair.
4. **The SDK is not split:** check the lists of check 3 against step 3 rule 4; the check fails when
   that rule's condition does not hold.
5. **Nothing that should be out is in:**
   `find <out> \( -name __pycache__ -o -name '*.pyc' -o -name tests -path '*/<handler package>/*' \)`
   prints nothing; the handler is at the root.
6. **Size:** `du -sk` of the output directory plus each layer's unzipped content is under 250 MB, and
   the zipped function is under 50 MB unless it uploads through S3 (CDK assets do).
7. **It imports on the Lambda platform:** run the handler module's import in the runtime's base image
   for the function's architecture, with the zip at `/var/task` and the layers extracted in order into
   `/opt`:
   `docker run --rm --platform linux/<amd64|arm64> -v <out>:/var/task:ro -v <merged layers>:/opt:ro -e PYTHONPATH=/var/task:/opt/python --entrypoint /var/lang/bin/python3 public.ecr.aws/lambda/python:<minor> -c "import <handler module>"`.
   An `ImportError`, a `GLIBC_` error or a wrong-ELF error means step 3 or step 5 is wrong.
8. **After a deploy you are allowed to make:**
   `aws lambda get-function --function-name <name> --query 'Configuration.[CodeSize,Layers]'`
   confirms the size and the layer versions actually attached.

## Step 8. Record the decisions

Put a packaging record in your result (in `notes`, or the field the caller's schema provides): one
line per distribution with its import (or "not imported"), where it comes from (function zip; layer
name and version; runtime; or "through <parent>"), where the pyproject declares it (dependencies,
group name, constraint, or nowhere), and the rule from step 3 that decided it; then the outputs of the
step 7 checks. A reviewer, and the next agent that changes this unit, start from this record and
re-run steps 1 to 3 against the arrangement as it then is.
