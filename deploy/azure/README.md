# Azure hosting

This deployment uses one Linux VM, a digest-pinned application container, a private FalkorDB container and Caddy HTTPS. Vercel serves the separately built static product site, linking to the same-origin Azure demonstration UI. No cross-origin cookies, public raw operator APIs, hardware commands or model calls are required.

## Provision

```bash
az group create -n rg-witness-fleet -l eastus --tags project=witness-fleet
az deployment group validate -g rg-witness-fleet --template-file deploy/azure/main.bicep \
  --parameters sshPublicKey=@$HOME/.ssh/id_ed25519.pub
az deployment group create -g rg-witness-fleet -n witness-fleet-initial \
  --template-file deploy/azure/main.bicep --parameters sshPublicKey=@$HOME/.ssh/id_ed25519.pub
```

Confirm region/size availability and actual recurring compute/disk/IP/registry charges first. The tested initial SKU is Standard_D2as_v4 in East US; this is not a free serverless deployment. Only inbound TCP80/443 are opened by the dedicated NSG. The VM SSH service is not publicly admitted by that NSG. Operator administration uses Azure Run Command.

Cloud-init installs Docker and Azure CLI. App state and graph AOF volumes reside on the VM managed OS disk's local filesystem, not a network share. `deleteOption: Detach` preserves the OS disk on VM deletion; **do not delete the VM or disks as routine cleanup**. This single-VM deployment is not high availability and needs an operator backup/retention policy before production use.

## Authentication

Create a user-assigned identity for GitHub OIDC with an exact federated subject restricted to the repository's production environment, audience `api://AzureADTokenExchange`, and issuer `https://token.actions.githubusercontent.com`. This repository uses GitHub's immutable subject format: `repo:guglxni@84870556/witness-fleet@1423606102:environment:production`. Verify the live prefix with `gh api repos/guglxni/witness-fleet/actions/oidc/customization/sub`; do not copy the older name-only subject, which fails Azure login. A fork must use its own exact owner/repository identifiers, not this value. See [GitHub's immutable subject change](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/). Scope `Virtual Machine Contributor` to this resource group and `AcrPush` to the dedicated registry. Scope VM system identity `AcrPull` to that registry. Do not enable the registry admin account. No long-lived Azure secret belongs in GitHub.

Set GitHub production environment variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`, `AZURE_REGISTRY`, and `DEMO_HOST`. These identifiers are not credentials. Restrict the production environment to main.

## Deploy and read back

The verified source workflow builds the app image, pushes it, resolves a content digest and invokes `deploy-runtime.sh image@sha256:… hostname git-sha`. The script starts a private graph if absent, refuses implicit recovery of a stopped retained graph, gracefully stops and retains a prior app container, then starts the new image with the same durable data directory. It does not remove containers, volumes or graph records. Restart invalidates prior visitor sessions rather than resuming physical commands.

Read `https://<DEMO_HOST>/healthz` and require the exact Git SHA. Health proves only process liveness. Real acceptance additionally requires a fresh visitor session, native recovery, explicit configured simulation-release confirmation, fresh courier sensing and delivery through the public UI/API. Never call a pending/unknown command twice with a new key to force success.

## Public boundary

Dedicated `witness_fleet.hosting` exposes only bounded `/demo/v1/*` routes. Host, HTTPS, exact Origin, CSRF and high-entropy secure HttpOnly cookies gate mutation. It does not mount the local `/api/*` router, expose raw graph/source blobs, accept caller graph/owner IDs, or provide reset/HOLD-clear endpoints. Process locks and durable lifetime/active caps bound admission. All data is synthetic simulation data. Capacity exhaustion retains evidence and closes admission.
