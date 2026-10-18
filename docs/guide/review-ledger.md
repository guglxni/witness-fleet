# Review and execution ledger

## Publication and deployments

- GitHub source publication: clean original-code snapshot, with original development history retained locally; complete third-party downloads and runtime databases excluded.
- Original and published Git histories plus publication tree scanned with Gitleaks. No unresolved credential finding remained.
- Vercel: GitHub-connected `site/`, public production, SSO protection removed with explicit user approval, git-fork protection retained.
- Azure: dedicated resource group, private disk-local FalkorDB and gateway, Caddy HTTPS, no SSH/database/simulator public ingress. Independent Caddy config validation passed.

## Independent checks incorporated

1. Public gateway contract review required an independent route allowlist, capability cookies, strict origin/CSRF, durable bounded admission, global mutation lock, sanitized DTO and restart quarantine. The implementation adopted these controls.
2. Independent implementation review found a startup-order defect: a losing process mutated session status before acquiring its lock. A regression reproduced it. Repair moved locking before ledger initialization. Independent focused review passed **9 tests**, including real seven-task simulation.
3. Parent production checks completed a real HTTPS mission, verified seven task/command outcomes, delivery and exact request replay. Browser release interaction was also exercised. No health-only result is claimed as fleet proof.
4. Linux CI revealed fixed-step assumptions in legacy recovery tests and missing clean-runner services. Those are corrected only with measured evidence; Actions keeps the failure history visible.

## Evidence scope

Reviews bind to the source bytes they inspect. Presentation-only changes do not extend an old security review to new authentication behavior. Film playback, diagram rendering, UI tests, native tests and production execution are separate claims. No physical robot safety certification, universal correctness, or distributed exactly-once guarantee is asserted.
