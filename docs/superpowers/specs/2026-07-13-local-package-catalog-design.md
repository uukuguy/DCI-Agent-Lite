# Local Package Catalog Design

> Status: approved for autonomous delivery after AF-070 under the existing framework north star.

## Goal

Turn checked-in `dci.package/v1` manifests into a usable local discovery surface.
Callers provide explicit local directories; the catalog validates their direct
JSON children, records deterministic package identities, supports exact
`package_id@version` selection, and feeds selected manifests to the existing
Python composer.

## Chosen approach

Build a small Python filesystem catalog with explicit roots and exact-version
selection.

Three approaches were considered:

1. **Explicit local catalog — selected.** It makes the existing package contract
   usable without adding distribution infrastructure or hidden global state.
2. **Application assembly manifest.** Binding runtimes, packages, and executors
   is premature until package discovery has a stable source and identity model.
3. **Third runtime adapter.** Another adapter increases runtime coverage but does
   not make the package layer usable and may require external provider access.

## Public API

Add `src/dci/framework/package_catalog.py` with:

```python
@dataclass(frozen=True, order=True)
class PackageRef:
    package_id: str
    version: str

@dataclass(frozen=True)
class CatalogEntry:
    ref: PackageRef
    source: Path
    manifest: Mapping[str, object]

@dataclass(frozen=True)
class PackageCatalog:
    entries: tuple[CatalogEntry, ...]

    def select(self, refs: Iterable[PackageRef]) -> tuple[Mapping[str, object], ...]: ...

def discover_packages(roots: Iterable[Path]) -> PackageCatalog: ...
```

`discover_packages` canonicalizes every root, requires each root to be a real
directory, rejects duplicate canonical roots, and examines only direct child
files whose names end in `.json`. Root argument order and filesystem enumeration
order do not affect catalog order.

Each JSON file must decode to an object and pass `validate_package_manifest`.
Entries are sorted by `(package_id, version, canonical source path)`. A duplicate
`package_id@version` is rejected even when the files are byte-identical, because
source precedence would otherwise be implicit.

`PackageCatalog.select` accepts exact `PackageRef` values only. It rejects
duplicate requested refs and unknown refs, then returns fresh manifest mappings
sorted by `PackageRef`. Exact selection deliberately avoids semantic-version
ranges, prerelease rules, lockfiles, dependency solving, and implicit upgrades.

## Filesystem and trust boundary

Catalog roots are trusted operator input, not agent/model input. Discovery:

- does not recurse;
- rejects symlink roots and symlink manifest files;
- ignores non-JSON direct children;
- fails the whole discovery operation on unreadable, malformed, non-object, or
  protocol-invalid JSON files;
- never loads Python modules, entry points, commands, prompts, credentials, or
  environment configuration; and
- performs no network request, installation, mutation, or execution.

Canonical source paths are local operator evidence. They are not copied into
package manifests, Agent Runtime Protocol values, model prompts, or provider
requests.

## Data flow

1. The operator/configuration layer supplies one or more explicit catalog roots.
2. Discovery canonicalizes and sorts roots and direct `.json` children.
3. Each document is decoded and validated through the canonical package
   protocol validator.
4. The catalog rejects duplicate exact identities and stores a deterministic
   tuple of entries.
5. The caller selects exact `PackageRef` values.
6. Selected manifest copies pass unchanged to `compose_packages` with explicit
   host capability/policy/event/artifact edges.

The catalog discovers and selects; the composer validates graph relationships;
a future execution layer remains outside both boundaries.

## Error behavior

Expose `PackageCatalogError(ValueError)` with safe structural messages for:

- missing, non-directory, or symlink roots;
- duplicate canonical roots;
- symlink manifest files;
- unreadable or malformed JSON;
- non-object JSON;
- invalid `dci.package/v1` manifests;
- duplicate `package_id@version` identities;
- duplicate requested refs; and
- unknown requested refs.

Errors may name the local source path or package identity, but never echo file
contents. Underlying JSON/parser/protocol exceptions are chained for local
debugging while the public error text remains content-free.

## Language boundary

Python owns discovery because it already owns composition and local
orchestration. TypeScript continues validating the same canonical manifests and
does not implement a parallel filesystem catalog in this package. A TypeScript
catalog may be added later only when a real Node consumer needs it and can share
the same conformance fixture contract.

## Verification strategy

Tests use temporary directories and prove:

- root and directory enumeration permutations yield identical catalog entries;
- all eight checked-in manifests are discoverable and exact-selectable;
- selected manifests compose into both existing reference graphs;
- malformed, non-object, protocol-invalid, symlinked, duplicate-root, duplicate-
  identity, duplicate-selection, and unknown-selection cases fail closed;
- error text never includes sentinel file contents; and
- discovery does not recurse or treat non-JSON files as packages.

Closure runs fresh full Python, TypeScript, and Rust tests plus compilation,
Ruff, Rust formatting, Clippy, shell syntax, scope audit, and diff checks.

## Non-goals

- No network registry, package download, installation, publishing, or cache.
- No version ranges, dependency solver, prerelease semantics, lockfile, or
  implicit upgrade policy.
- No Python entry points, module imports, plugin loading, or executable package
  hooks.
- No runtime/executor binding, workflow scheduling, command execution, or code
  repair.
- No global user catalog, background watcher, mutable index, database, remote
  service, authentication, or tenancy.

## Acceptance

- Explicit local roots produce one deterministic validated catalog.
- Exact identities select fresh manifests and integrate with the existing
  composer without changing package semantics.
- Every filesystem, identity, decoding, validation, and selection ambiguity
  fails closed with safe errors.
- Discovery remains Python-local and TypeScript retains canonical manifest
  validation without a duplicate catalog.
- Documentation and every repository closure gate pass with fresh evidence.
