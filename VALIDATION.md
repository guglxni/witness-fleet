# Documentation validation and limitations

This is documentation-level verification, not a robot/software benchmark. Every application requirement remains planned.

## Executed checks

- Independent `gh api` exact-commit checks for the repository inventory are retained in `evidence/parent-repository-verification.json`.
- `npx -y @google/design.md@0.3.0 lint DESIGN.md` completed with zero errors and zero warnings; actual result is `evidence/design-lint.json`. This validates design tokens/structure/declared contrast pairs, not a running interface's accessibility.
- `python3 scripts/verify_math_examples.py` recomputed the four labeled synthetic arithmetic examples successfully. This is formula arithmetic, not inference or simulator output.
- Citation helper render/verify results are in `evidence/citation-validation.json`; unknown-ID/URL-mapping checks passed on the cited documents. Unused-ledger-source warnings are expected because each document uses a subset; this is not claim-level evidence verification or a claimed citation-coverage percentage.
- Initial `scripts/verify_docs.py` run correctly failed while the validation/review files were not yet present. Final results and mutation checks are recorded in `evidence/docs-validation.json` and `evidence/validator-mutation-tests.json` after final assembly.

## Final structural and syntax checks

The assembled documentation checker returned **no structural errors**, with the explicit protected-file blocker still disclosed. It checked local Markdown links, registered citation IDs, all 23 independently verified repo pins and corresponding `gh` recipes, selected entrypoints against complete pinned trees, and R-001 through R-038.

Three temporary-copy mutations (broken local link, unknown citation ID, and unverified exact pin) were each detected. This validates the documentation checker's sensitivity to those faults, not its ability to detect arbitrary design errors. Every Bash fenced block in REPOSITORIES.md passed `bash -n`; this is syntax validation only, not clone/install execution.

## Known incomplete deliverable

`AGENTS.md`, `CLAUDE.md` and `SKILL.md` are absent because protected-file consent timed out and follow-up approval was not received. No alternate instruction filename or indirect write was used. The validator reports this as an explicit warning/blocker, not completion of the entire request.

## Evidence levels

Repository/link/license-path inspection is not install compatibility, licensing of model weights/data, or a working integration. Public paper snapshots support reading scope, not reproduction. A source citation that resolves is not an independently verified claim. Independent document review is not a runtime audit.

No application dependency install, Cypher execution, graph mutation, physical simulation, API inference, model benchmark, storage durability test, deployment, public repository or submission was performed. Only documentation tooling and synthetic arithmetic ran. Published paper/vendor metrics are not local results.

## Reproduce the documentation checks

From the extracted package root:

```bash
python3 scripts/verify_docs.py
python3 scripts/verify_math_examples.py
npx -y @google/design.md@0.3.0 lint DESIGN.md
```

Python checks use the standard library. DESIGN.md lint downloads/executes the named external documentation CLI if not cached. The package's application instructions are prospective and require explicit dependency/service/access setup.
