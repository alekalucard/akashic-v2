# Deploy Queue - Shared Memory Bridge

This folder enables file deployment between Windows and Alienware
WITHOUT needing SSH. It uses the Akashic shared memory pattern.

## How it works:

1. **Windows stages files here** with a `manifest.json` describing deployment
2. **Alienware reads the manifest** and copies files to their destinations
3. **No SSH required** - just the shared folder access

## Folder Structure:

```
deploy_queue/
  manifest.json        # What to deploy
  files/               # Staged files to deploy
  completed/           # Processed manifests (history)
```

## To Deploy Files:

1. Copy files to `files/` subdirectory
2. Create/update `manifest.json` with deployment instructions
3. Alienware watcher picks up and executes

## Mount Points:

- Windows: F:\Sandbox\failure_factory\akashic_v2\fairies\.satellite
- Alienware: Mount via SMB at ~/akashic_satellite or /mnt/akashic
