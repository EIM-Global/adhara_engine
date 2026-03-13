  Design: Workspace Deploy Guide & Site Source Flows

  Problem 1: The Deploy Guide Only Shows docker_image

  Fix: Replace the single "Deploy Your First Site" guide with a tabbed quick-start showing 3 paths:

  ┌────────────────────┬────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┐
  │        Tab         │           Title            │                                  When to Use                                  │
  ├────────────────────┼────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ From GitHub/GitLab │ Connect a Git Repository   │ You have code in a remote repo — we clone, build, and deploy automatically    │
  ├────────────────────┼────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ From Registry      │ Deploy a Registry Image    │ You've already built an image and pushed it to the local or external registry │
  ├────────────────────┼────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ Local Build & Push │ Build Locally, Deploy Here │ You build on your machine and push the image to our registry                  │
  └────────────────────┴────────────────────────────┴───────────────────────────────────────────────────────────────────────────────┘

  Each tab shows ~3 steps relevant to that flow.

  Only show this guide when the workspace has 0 sites. Once sites exist, replace it with a smaller "Add another site" hint or just remove it.

  Problem 2: Existing Sites Need "Push an Update" Guidance

  Fix: On the SiteDetail page, in the Overview tab, add a contextual "Deploy Updates" section based on the site's source_type:

  ┌─────────────────┬────────────────────────────────────────────────────────────────────────────────────────────┐
  │   source_type   │                                        What to show                                        │
  ├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────┤
  │ git_repo        │ "Push to {branch} on GitHub/GitLab and it auto-deploys" + manual "Rebuild & Deploy" button │
  ├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────┤
  │ docker_image    │ "Push a new tag to the registry, then click Rebuild" + docker build & push commands        │
  ├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────┤
  │ docker_registry │ "Push a new image to {registry}, then click Rebuild"                                       │
  └─────────────────┴────────────────────────────────────────────────────────────────────────────────────────────┘

  Problem 3: Create Site Form Needs Better Organization

  Fix: Restructure the Create Site form as a wizard/stepper with clear intent:

  Step 1: "How do you want to deploy?"
  - Connect Git Repository (GitHub, GitLab, Bitbucket) → shows URL + branch + optional token
  - Use a Registry Image → shows local registry picker or remote URL
  - Push from Local Machine → shows push instructions, then image picker

  Step 2: Configure (source-type-specific fields)

  Step 3: Review & Create

  Problem 4: Do We Need Our Own Git Server?

  No. Here's why:
  - The clone happens in a temp dir during the build pipeline and is cleaned up after
  - We only need the code long enough to run docker build
  - GitHub/GitLab PATs or deploy tokens handle auth
  - Webhook auto-deploy handles the "push and it redeploys" flow
  - Hosting a git server (Gitea/Gogs) would add significant complexity for little benefit at this stage

  If you ever want hosted git: Add Gitea as an optional Docker Compose service. But it's Phase 2+ material.

  Problem 5: Upload Source Type Has No UI

  Defer for now. The upload type is partially built in the backend but has no UI. It would require:
  - A file upload dropzone (tar.gz or zip)
  - MinIO storage integration in the frontend
  - This is lower priority than git and registry flows

  ---
  Implementation Plan

  Phase 1: Redesign Workspace Deploy Guide (WorkspaceDetail.tsx)

  - Replace single docker_image guide with 3-tab quick-start (Git, Registry, Local Build)
  - Only show when workspace has 0 sites
  - Each tab shows the right 3-4 steps for that workflow
  - "Connect Git Repository" tab shows:
    a. Click "+ New Site" and select "Git Repository"
    b. Enter your repo URL and optionally a deploy token
    c. Site auto-deploys on every push to your branch

  Phase 2: Improve Create Site Form (WorkspaceDetail.tsx)

  - Reorganize source type selection as 3 clear cards instead of a dropdown
  - Better labeling: "Connect Git Repo" / "Registry Image" / "Local Build & Push"
  - Remove the upload option from UI for now (backend still supports it)
  - Clarify that docker_image and docker_registry are for "image already exists"

  Phase 3: Add "Deploy Updates" Section to SiteDetail

  - On the Overview tab, below status, show contextual update instructions
  - Git sites: "Push to {branch} and it auto-deploys" + webhook status
  - Image sites: docker build + docker push commands with the correct registry path
  - Manual "Rebuild & Deploy" button always visible

  Files to Modify

  - ui/src/pages/WorkspaceDetail.tsx — deploy guide + create form
  - ui/src/pages/SiteDetail.tsx — add deploy updates section in overview

  Files NOT Modified

  - No backend changes needed — all source types and pipeline stages already work
  - No new services needed — no git server required

  ---
  Patrick, does this plan align with your vision? Key decisions:

  1. No git server needed — we clone from GitHub/GitLab with PATs, code is ephemeral during builds
  2. 3-tab quick start replacing the current single docker_image guide
  3. Contextual update instructions per site on the detail page
  4. Defer upload UI to a future phase