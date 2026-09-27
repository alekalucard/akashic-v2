# Alienware Cardinal Setup - Quick Start

## One-Liner Setup (after mounting shared folder)

```bash
# 1. Mount the Windows share (adjust IP)
sudo mkdir -p /mnt/akashic && sudo mount -t cifs //192.168.1.X/akashic /mnt/akashic -o username=Ace,uid=$(id -u)

# 2. Create local akashic folder
mkdir -p ~/akashic_shared

# 3. Symlink to shared (or copy if mount doesn't work)
ln -s /mnt/akashic/.satellite ~/akashic_shared/.satellite
# OR copy: cp -r /mnt/akashic/.satellite ~/akashic_shared/

# 4. Run the Cardinal agent
export AKASHIC_SHARED=~/akashic_shared/.satellite
python3 ~/akashic_shared/.satellite/alienware_cardinal_agent.py --status
```

## If SMB Mount Doesn't Work

Copy the .satellite folder manually:
```bash
# On Alienware, create the folder
mkdir -p ~/akashic_shared/.satellite

# From a USB drive or download:
cp -r /media/usb/.satellite/* ~/akashic_shared/.satellite/

# Or use any file transfer method you have working
```

## Start the Cardinal Agent

```bash
# One-time run (process pending tasks)
python3 ~/akashic_shared/.satellite/alienware_cardinal_agent.py

# Watch mode (continuous)
python3 ~/akashic_shared/.satellite/alienware_cardinal_agent.py --watch

# Check status
python3 ~/akashic_shared/.satellite/alienware_cardinal_agent.py --status
```

## Deploy WoW Scripts

Once Cardinal is running, it will automatically:
1. Check `deploy_queue/manifest.json` for staged files
2. Copy files to the target directories
3. Update status

Or manually:
```bash
# Quick deploy from staged files
cp -r ~/akashic_shared/.satellite/deploy_queue/files/fairy_class/* ~/AzerothCore/lua_scripts/fairy_class/

# Reload Eluna
# In WoW server console: .reload eluna
```

## Prerequisites

- Ollama running: `ollama serve`
- Mistral model: `ollama pull mistral`
- Python 3.8+
- httpx: `pip install httpx`
