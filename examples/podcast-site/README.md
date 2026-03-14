# The Build Log — Example Podcast Site

A static podcast website built with Vite + React + TypeScript + Tailwind CSS 4.
Ships as an example with [Adhara Engine](https://github.com/EIM-Global/adhara_engine) to demonstrate building and deploying a real site.

## Run Locally

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## Deploy to Adhara Engine

Make sure Adhara Engine is running (`make status` from the engine root) and you have the CLI installed (`make install`).

### Step 1 — Build and push the Docker image

```bash
# From the examples/podcast-site directory
docker build -t engine.localhost/podcast-site:latest .
docker push engine.localhost/podcast-site:latest
```

### Step 2 — Create a tenant and workspace (skip if you already have one)

```bash
adhara-engine tenant create --name "My Company" --email admin@example.com --plan pro
adhara-engine workspace create --tenant my-company --name "Production"
```

### Step 3 — Create the site and deploy

```bash
adhara-engine site create \
  --workspace my-company/production \
  --name "Podcast Site" \
  --source docker_image \
  --image "engine.localhost/podcast-site:latest" \
  --port 3000

adhara-engine site deploy my-company/production/podcast-site
```

### Step 4 — Open it

```bash
# Via hostname routing
open http://podcast-site.production.my-company.localhost

# Or check the assigned port
adhara-engine site status my-company/production/podcast-site
```

## Deploy to Vercel

The easiest option for a public site:

```bash
# One-command deploy
npx vercel

# Or connect via GitHub for automatic deploys
```

The included `vercel.json` handles SPA routing automatically.

## Customization

All podcast content lives in `src/data.ts`. Edit that file to change:

- Podcast name and tagline
- Host information
- Episode list
- Subscribe links
- Social links

## Project Structure

```
src/
  App.tsx       — Single-page layout with all sections
  data.ts       — All podcast content (edit this to customize)
  index.css     — Tailwind CSS imports
  main.tsx      — React entry point
public/
  favicon.svg   — Microphone icon favicon
```
