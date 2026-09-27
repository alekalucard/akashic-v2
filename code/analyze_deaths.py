"""Quick analysis of fairy_deaths.jsonl"""
import json

deaths = 0
stales = 0
unique_deaths = set()
death_cycles = {}

with open("state/fairy_deaths.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
            event_type = evt.get("event", "")
            if event_type == "FAIRY_DEATH":
                deaths += 1
                name = evt.get("fairy", "?")
                unique_deaths.add(name)
                death_cycles[name] = death_cycles.get(name, 0) + 1
            elif event_type == "FAIRY_STALE":
                stales += 1
        except json.JSONDecodeError:
            pass

print(f"Total DEATH events: {deaths}")
print(f"Total STALE events: {stales}")
print(f"Unique fairies that died: {len(unique_deaths)}")
print()

print("Death cycle counts (fairies that died most):")
for name, count in sorted(death_cycles.items(), key=lambda x: -x[1])[:25]:
    print(f"  {name:40s} died {count}x")

cycling = sum(1 for c in death_cycles.values() if c > 1)
print(f"\nFairies cycling (died > 1 time): {cycling}")
print(f"Fairies that died exactly once: {sum(1 for c in death_cycles.values() if c == 1)}")

# Show last 5 death events with beat numbers
print("\nMost recent 5 death events:")
recent_deaths = []
with open("state/fairy_deaths.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
            if evt.get("event") == "FAIRY_DEATH":
                recent_deaths.append(evt)
                if len(recent_deaths) > 5:
                    recent_deaths.pop(0)
        except:
            pass

for d in recent_deaths:
    print(f"  Beat {d.get('global_beat',0):6d} | {d.get('fairy','?'):35s} | silent {d.get('silence_seconds',0):.0f}s | {d.get('timestamp','?')}")
