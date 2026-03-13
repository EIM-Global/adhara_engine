 Here's the full command sequence, assuming Adhara Engine is already running (make status):
                                                                                                                                                          
  # 1. Build the Docker image                                                                                                                             
  cd /Users/pfarrell/projects/eim_clients/jungle_habitas/jungle_habitas                                                                                   
  make build                                                                                                                                              
                                                                                                                                                          
  # 2. Tag and push to the local Adhara registry                          
  docker tag jungle-habitas:latest localhost:5000/eim/jungle-habitas:latest
  docker push localhost:5000/eim/jungle-habitas:latest                    
                                                                          
  # 3. Create tenant + workspace (skip if they already exist)             
  adhara-engine tenant create --name "EIM" --email admin@example.com --plan pro
  adhara-engine workspace create --tenant eim --name "Production"         
                                                                          
  # 4. Create the site                                                                                                                                    
  adhara-engine site create \                                                                                                                             
    --workspace eim/production \                                                                                                                          
    --name "Jungle Habitas" \                                                                                                                             
    --source docker_image \                                               
    --image "localhost:5000/eim/jungle-habitas:latest" \             
    --port 3000                                                      
                                                                          
  # 5. Deploy                                                             
  adhara-engine site deploy eim/production/jungle-habitas

  # 6. Check status
  adhara-engine site status eim/production/jungle-habitas

  # 7. Open in browser (pick one)
  open http://jungle-habitas.production.eim.localhost
  # or use the assigned port from step 6:
  # open http://localhost:{host_port}

  Kairos: Six commands from zero to running — build, push, create tenant/workspace, create site, deploy, open.







  Deploy Patrick Farrell

   Files Created/Modified                                             
                                                                          
  ┌──────────────────────────────────┬────────────────────────────┐  
  │               File               │           Action           │                                                                                       
  ├──────────────────────────────────┼────────────────────────────┤                                                                                       
  │ iampatrickfarrell/next.config.ts │ Added output: 'standalone' │
  ├──────────────────────────────────┼────────────────────────────┤
  │ iampatrickfarrell/Dockerfile     │ Created — 3-stage build    │
  ├──────────────────────────────────┼────────────────────────────┤
  │ iampatrickfarrell/.dockerignore  │ Created                    │
  └──────────────────────────────────┴────────────────────────────┘

  Deploy Commands

  1. Build & push to engine registry:

  cd ~/projects/eim_internal/iampatrickfarrell

  # Build with your env vars as build args
  docker build \
    --build-arg ADHARA_API_KEY=adhara_pk_403b7ae3__rlLvIjvEMVSjgZzGBfxPaS8ayhny2qXtOenFuApu68 \
    --build-arg ADHARA_WORKSPACE_ID=04b6d26a-5b07-4ca5-9cef-3ae8615389a4 \
    --build-arg NEXT_PUBLIC_SITE_URL=https://iampatrickfarrell.com \
    -t iampatrickfarrell:latest .

  # Tag and push to engine registry
  docker tag iampatrickfarrell:latest localhost:5000/iampatrickfarrell:latest
  docker push localhost:5000/iampatrickfarrell:latest

  2. Create resources & deploy via CLI:

  # Activate CLI
  source ~/projects/eim_internal/adhara_engine/cli/.venv/bin/activate

  # Create tenant + workspace + site
  adhara-engine tenant create --name "Patrick Farrell" --email "patrick@iampatrickfarrell.com"
  adhara-engine workspace create --tenant patrick-farrell --name production
  adhara-engine site create \
    --workspace patrick-farrell/production \
    --name iampatrickfarrell \
    --source docker_image \
    --image localhost:5000/iampatrickfarrell:latest \
    --port 3000

  # Set runtime env vars (server-side, not baked into build)
  adhara-engine env set patrick-farrell/production/iampatrickfarrell "ADHARA_BASE_URL=https://api.adharaweb.com/"
  adhara-engine env set patrick-farrell/production/iampatrickfarrell "ADHARA_API_KEY=adhara_pk_403b7ae3__rlLvIjvEMVSjgZzGBfxPaS8ayhny2qXtOenFuApu68"
  adhara-engine env set patrick-farrell/production/iampatrickfarrell "ADHARA_WORKSPACE_ID=04b6d26a-5b07-4ca5-9cef-3ae8615389a4"

  # Deploy
  adhara-engine site deploy patrick-farrell/production/iampatrickfarrell

  3. Add custom domain:

  adhara-engine domain add patrick-farrell/production/iampatrickfarrell iampatrickfarrell.com

  Then point DNS: A record for iampatrickfarrell.com → your engine VM IP.

  Or use the deploy script:

  bash ~/projects/eim_internal/adhara_engine/scripts/deploy-site.sh \
    ~/projects/eim_internal/iampatrickfarrell


  📋 SUMMARY: Removed ADHARA_API_KEY, ADHARA_BASE_URL, and ADHARA_WORKSPACE_ID from build-time ARGs/ENVs. They're not needed at build time (no
  generateStaticParams) — they're fetched at runtime via SSR with revalidate: 60.
                                                                          
  The updated build command is now just:                                  
                                                                     
  docker build -t iampatrickfarrell:latest .                              
                                                                     
  No --build-arg needed for secrets. Set them at runtime after deployment:
                                                                     
  adhara-engine env set patrick-farrell/production/iampatrickfarrell "ADHARA_BASE_URL=https://api.adharaweb.com/"                                         
  adhara-engine env set patrick-farrell/production/iampatrickfarrell "ADHARA_API_KEY=adhara_pk_403b7ae3__rlLvIjvEMVSjgZzGBfxPaS8ayhny2qXtOenFuApu68"      
  adhara-engine env set patrick-farrell/production/iampatrickfarrell "ADHARA_WORKSPACE_ID=04b6d26a-5b07-4ca5-9cef-3ae8615389a4"
  adhara-engine site restart patrick-farrell/production/iampatrickfarrell

  🗣️  Kairos: Fixed — removed secret ARGs from Dockerfile. Those vars are runtime-only since there's no static prerendering.




  # 1. Build and push the image                                                                                                                           
  cd /Users/pfarrell/projects/eim_clients/angela_papa/angelapapa                                                                                          
  docker build -t localhost:5000/angelapapa:latest .                                                                                                      
  docker push localhost:5000/angelapapa:latest                                                                                                            
                                                                                                                                                          
  # 2. Create tenant, workspace, and site                                                                                                                 
  adhara-engine tenant create --name "Angela Papa" --email "angela@angelapapa.com"                                                                        
  adhara-engine workspace create --tenant angela-papa --name production                                                                                   
  adhara-engine site create \                                                                                                                             
    --workspace angela-papa/production \                                  
    --name angelapapa \                                                   
    --source docker_image \                                                                                                                               
    --image localhost:5000/angelapapa:latest \                                                                                                            
    --port 3000                                                                                                                                           
                                                                                                                                                          
  # 3. Set runtime env vars (server-side secrets)                                                                                                         
  adhara-engine env set angela-papa/production/angelapapa DATABASE_URL=<value>                                                                            
  adhara-engine env set angela-papa/production/angelapapa STRIPE_SECRET_KEY=<value>                                                                       
  adhara-engine env set angela-papa/production/angelapapa NOTION_TOKEN=<value>                                                                            
  # ... any other server-side secrets from her .env                                                                                                       
                                                                                                                                                          
  # 4. Deploy
  adhara-engine site deploy angela-papa/production/angelapapa

  Once deployed, the site will be available at http://angelapapa.production.angela-papa.localhost.


adhara-engine site create \
--workspace kaitlin-otoole/production \
--name kaitlinotoole \
--source docker_image \
--image localhost:5000/kaitlinotoole:latest \
--port 3000





docker build --build-arg VITE_ADHARA_WORKSPACE_ID=01ee8da5-2b4f-434a-975a-792885e5865d -t localhost:5000/djloversclub:latest .



adhara-engine site create --workspace dj-lovers-club/production --name djloversclub --source docker_image --image localhost:5000/djloversclub:latest --port 3000

dhara-engine env set dj-lovers-club/production/djloversclub ADHARA_BASE_URL=https://api.adharaweb.com

adhara-engine env set dj-lovers-club/production/djloversclub ADHARA_API_KEY=adhara_pk_a7e4f86b_gTKwoC9kD4F1K0btADpWGTE1QfTVew4CmZmN2HGmekE


docker build --build-arg ADHARA_WORKSPACE_ID=0d335227-ae79-46c2-8814-e28bee583b77 --build-arg ADHARA_API_KEY=adhara_pk_4977dd1c_HGmkEg9uTSJb4tLw_JwC0c2lbIBZPVstaq0dv_O_QXk -t localhost:5000/islandsofvenus:latest .                          


docker push localhost:5000/islandsofvenus:latest     




docker build \
    --build-arg ADHARA_WORKSPACE_ID=your-workspace-id \
    --build-arg ADHARA_API_CREDENTIAL=your-api-key \
    -t localhost:5000/islandsofvenus:latest \
    /Users/pfarrell/projects/eim_clients/islandsofvenus/islandsofvenus


printf "ADHARA_API_BASE=https://api.adharaweb.com\nADHARA_WORKSPACE_ID=your-workspace-id\nADHARA_API_KEY=your-api-key\n" > /Users/pfarrell/projects/eim_clients/islandsofvenus/islandsofvenus/.env.production 


docker build -t localhost:5000/islandsofvenus:latest /Users/pfarrell/projects/eim_clients/islandsofvenus/islandsofvenus



adhara-engine site create --workspace islands-of-venus/production --name "Islands of Venus" --source docker_image --image "localhost:5000/islandsofvenus:latest" --port 3000