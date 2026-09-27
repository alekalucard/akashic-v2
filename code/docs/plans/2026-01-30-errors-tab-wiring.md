# Errors Tab - Wire to Forensic Team Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the Tauri GUI Errors tab to use the existing forensic team (ForensicScribeFairy, AkashicLibrarianFairy, TracerDaemonFairy) with Good/Bad/Ugly classification.

**Architecture:** Server.py telemetry endpoint pulls from ForensicScribeFairy's error registry and returns structured data using the 3-6-9 Good/Bad/Ugly pattern from boot_audit.py.

**Tech Stack:** Python (server.py), JavaScript (dashboard/ui/app.js), Existing fairies

---

## Background

The system has all the pieces but they're disconnected:
- **ForensicScribeFairy** (`fairies/P10_Memory/ForensicScribeFairy/fairy.py`) - Already collects errors via `telemetry.*`, `tracer.*`, `fairy.error` subscriptions
- **AkashicLibrarianFairy** - Maintains bugs feed via `get_bugs()`
- **boot_audit.py** - Has the Good/Bad/Ugly classification (Severity enum)
- **Server.py** - Currently only pulls from UnifiedRegistry, NOT from ForensicScribe

## Current Data Flow (Broken)
```
Fairies emit errors → ForensicScribeFairy collects → [DEAD END - not used]
Server.py pulls from UnifiedRegistry → Errors tab shows nothing useful
```

## Target Data Flow (Fixed)
```
Fairies emit errors → ForensicScribeFairy collects → Server.py pulls from ForensicScribe
                                                   → Returns Good/Bad/Ugly structured data
                                                   → Errors tab displays properly
```

---

### Task 1: Add ForensicScribe Integration to Server

**Files:**
- Modify: `server.py` (around line 397-425 in telemetry section)

**Step 1: Add import at top of server.py**

```python
# Add with other fairy imports
try:
    from fairies.P10_Memory.ForensicScribeFairy.fairy import get_forensic_fairy
except ImportError:
    get_forensic_fairy = None
```

**Step 2: Modify telemetry section to use ForensicScribeFairy**

Replace the telemetry section (lines ~397-425) with:

```python
# Telemetry section for errors tab - Good/Bad/Ugly from ForensicScribe
the_good = []
the_bad = []
the_ugly = []

# Get from ForensicScribeFairy (primary source)
try:
    forensic = get_forensic_fairy() if get_forensic_fairy else None
    if forensic:
        error_summary = forensic.get_error_summary()
        all_cards = forensic.get_all_cards()

        # Classify by health status
        for actor, card in all_cards.items():
            health = card.get("health", {})
            status = health.get("status", "unknown")
            errors = card.get("errors", {})

            entry = {
                "name": actor,
                "plane": card.get("plane", ""),
                "status": status,
                "message": health.get("message", ""),
                "error_count": errors.get("count", 0),
                "last_error": errors.get("last"),
            }

            if status in ("ok", "info"):
                the_good.append(entry)
            elif status in ("warn", "warning"):
                the_bad.append(entry)
            elif status in ("error", "critical"):
                the_ugly.append(entry)

        # Add top errors to the_ugly
        for err in error_summary.get("errors", [])[:10]:
            the_ugly.append({
                "name": err.get("actor", "unknown"),
                "plane": "",
                "status": "error",
                "message": err.get("message", "")[:200],
                "error_count": err.get("count", 1),
                "last_error": err.get("message"),
            })
except Exception as e:
    print(f"[STATUS] ForensicScribe error: {e}")

# Fallback: still get dead fairies from fairy list
dead_fairies = [
    {"name": f["name"], "plane": f.get("plane", ""), "age": "failed"}
    for f in fairy_list if f["status"] == "failed"
]

# Add dead fairies to the_ugly
for df in dead_fairies:
    if not any(u["name"] == df["name"] for u in the_ugly):
        the_ugly.append({
            "name": df["name"],
            "plane": df.get("plane", ""),
            "status": "dead",
            "message": "No heartbeat",
            "error_count": 1,
            "last_error": "Fairy is dead",
        })

status["telemetry"] = {
    "deadFairies": dead_fairies,  # Keep for backwards compat
    "theGood": the_good,
    "theBad": the_bad,
    "theUgly": the_ugly,
    "summary": {
        "good": len(the_good),
        "bad": len(the_bad),
        "ugly": len(the_ugly),
        "healthScore": 100 + len(the_good) - (len(the_bad) * 3) - (len(the_ugly) * 10)
    }
}
```

**Step 3: Run server and test endpoint**

Run: `curl http://127.0.0.1:5757/status | jq .telemetry`
Expected: JSON with `theGood`, `theBad`, `theUgly` arrays

**Step 4: Commit**

```bash
git add server.py
git commit -m "feat(telemetry): wire errors tab to ForensicScribeFairy with Good/Bad/Ugly"
```

---

### Task 2: Update GUI Errors Tab to Display Good/Bad/Ugly

**Files:**
- Modify: `dashboard/ui/index.html` (panel-telemetry section, ~lines 459-501)

**Step 1: Replace the Errors Tab HTML structure**

Replace the `<section class="tab-panel" id="panel-telemetry">` section with:

```html
<!-- Telemetry/Errors Tab -->
<section class="tab-panel" id="panel-telemetry">
    <div class="panel-grid" style="grid-template-columns: repeat(3, 1fr);">
        <!-- The Good -->
        <div class="card">
            <h2 class="card-title" style="color: #4ade80;">The Good</h2>
            <p class="card-subtitle">Healthy fairies and systems</p>
            <div class="stat-row">
                <span class="stat-label">Count</span>
                <span class="stat-value" id="good-count" style="color: #4ade80;">0</span>
            </div>
            <div class="fairy-list" id="good-list" style="max-height: 200px; overflow-y: auto;">
                <div class="empty-state">Loading...</div>
            </div>
        </div>

        <!-- The Bad -->
        <div class="card">
            <h2 class="card-title" style="color: #fbbf24;">The Bad</h2>
            <p class="card-subtitle">Needs attention (warnings)</p>
            <div class="stat-row">
                <span class="stat-label">Count</span>
                <span class="stat-value" id="bad-count" style="color: #fbbf24;">0</span>
            </div>
            <div class="fairy-list" id="bad-list" style="max-height: 200px; overflow-y: auto;">
                <div class="empty-state">Loading...</div>
            </div>
        </div>

        <!-- The Ugly -->
        <div class="card">
            <h2 class="card-title" style="color: #f87171;">The Ugly</h2>
            <p class="card-subtitle">Critical issues and dead fairies</p>
            <div class="stat-row">
                <span class="stat-label">Count</span>
                <span class="stat-value" id="ugly-count" style="color: #f87171;">0</span>
            </div>
            <div class="fairy-list" id="ugly-list" style="max-height: 200px; overflow-y: auto;">
                <div class="empty-state">Loading...</div>
            </div>
        </div>
    </div>

    <!-- Health Score -->
    <div class="card" style="margin-top: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h2 class="card-title">System Health Score</h2>
                <p class="card-subtitle">Formula: 100 + good - (bad x 3) - (ugly x 10)</p>
            </div>
            <span class="stat-value" id="health-score" style="font-size: 48px; color: #4ade80;">100</span>
        </div>
    </div>

    <!-- Error Log (keep for detailed view) -->
    <div class="card" style="margin-top: 16px;">
        <h2 class="card-title">Error Details</h2>
        <p class="card-subtitle">Recent errors from The Ugly (newest first)</p>
        <div class="error-log" id="error-log" style="max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 12px;">
            <div class="empty-state">No errors recorded yet</div>
        </div>
        <button class="btn" onclick="clearErrors()" style="margin-top: 12px;">Clear Log</button>
    </div>
</section>
```

**Step 2: Verify HTML is valid**

Open in browser and verify structure renders

**Step 3: Commit**

```bash
git add dashboard/ui/index.html
git commit -m "feat(ui): update errors tab with Good/Bad/Ugly layout"
```

---

### Task 3: Update JavaScript to Handle Good/Bad/Ugly Data

**Files:**
- Modify: `dashboard/ui/app.js` (updateTelemetry function)

**Step 1: Find and update updateTelemetry function**

Search for `function updateTelemetry` and replace with safe DOM manipulation (no innerHTML with dynamic content):

```javascript
function updateTelemetry(data) {
    // Good/Bad/Ugly from ForensicScribe
    var theGood = data.theGood || [];
    var theBad = data.theBad || [];
    var theUgly = data.theUgly || [];
    var summary = data.summary || { good: 0, bad: 0, ugly: 0, healthScore: 100 };

    // Update counts
    document.getElementById('good-count').textContent = theGood.length;
    document.getElementById('bad-count').textContent = theBad.length;
    document.getElementById('ugly-count').textContent = theUgly.length;

    // Update health score with color
    var scoreEl = document.getElementById('health-score');
    scoreEl.textContent = summary.healthScore;
    if (summary.healthScore >= 80) {
        scoreEl.style.color = '#4ade80';  // Green
    } else if (summary.healthScore >= 50) {
        scoreEl.style.color = '#fbbf24';  // Yellow
    } else {
        scoreEl.style.color = '#f87171';  // Red
    }

    // Helper to render a list using safe DOM methods
    function renderList(containerId, items, emptyMessage) {
        var container = document.getElementById(containerId);
        // Clear safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }

        if (items.length === 0) {
            var emptyDiv = document.createElement('div');
            emptyDiv.className = 'empty-state';
            emptyDiv.textContent = emptyMessage || 'None';
            container.appendChild(emptyDiv);
            return;
        }

        items.forEach(function(item) {
            var div = document.createElement('div');
            div.className = 'fairy-item';
            div.style.padding = '8px';
            div.style.marginBottom = '4px';
            div.style.borderRadius = '4px';
            div.style.background = 'rgba(0,0,0,0.2)';

            var name = document.createElement('div');
            name.style.fontWeight = 'bold';
            name.textContent = item.name || 'Unknown';

            var details = document.createElement('div');
            details.style.fontSize = '11px';
            details.style.opacity = '0.7';
            var detailText = (item.plane || '') + ' - ' + (item.message || item.status || '');
            if (item.error_count > 1) {
                detailText += ' (x' + item.error_count + ')';
            }
            details.textContent = detailText;

            div.appendChild(name);
            div.appendChild(details);
            container.appendChild(div);
        });
    }

    // Render the three lists
    renderList('good-list', theGood, 'All systems healthy');
    renderList('bad-list', theBad, 'No warnings');
    renderList('ugly-list', theUgly, 'No critical issues');

    // Update error log from theUgly using safe DOM methods
    var errorLog = document.getElementById('error-log');
    while (errorLog.firstChild) {
        errorLog.removeChild(errorLog.firstChild);
    }

    if (theUgly.length === 0) {
        var emptyDiv = document.createElement('div');
        emptyDiv.className = 'empty-state';
        emptyDiv.textContent = 'No errors recorded';
        errorLog.appendChild(emptyDiv);
    } else {
        theUgly.forEach(function(err) {
            var div = document.createElement('div');
            div.style.padding = '4px 8px';
            div.style.marginBottom = '2px';
            div.style.borderLeft = '3px solid #f87171';
            div.style.background = 'rgba(248, 113, 113, 0.1)';
            div.textContent = '[' + (err.name || 'unknown') + '] ' + (err.last_error || err.message || 'Error');
            errorLog.appendChild(div);
        });
    }

    // Backwards compat: also update old counters if they exist
    var deathCount = document.getElementById('death-count');
    if (deathCount) {
        deathCount.textContent = (data.deadFairies || []).length;
    }
    var errorCountEl = document.getElementById('error-count');
    if (errorCountEl) {
        errorCountEl.textContent = theUgly.length;
    }
}
```

**Step 2: Verify the function works**

Start server, open GUI, check Errors tab shows Good/Bad/Ugly

**Step 3: Commit**

```bash
git add dashboard/ui/app.js
git commit -m "feat(ui): implement Good/Bad/Ugly rendering in errors tab"
```

---

### Task 4: Ensure ForensicScribeFairy Boots with Shared Fabric

**Files:**
- Modify: `unconscious_mind/fairy.py` or boot sequence to ensure ForensicScribeFairy gets shared fabric

**Step 1: Check if ForensicScribeFairy is in boot sequence**

Search for ForensicScribe in boot files and ensure it's created with fabric parameter.

**Step 2: If missing, add to boot sequence**

In the fairy boot sequence, ensure:
```python
from fairies.P10_Memory.ForensicScribeFairy.fairy import ForensicScribeFairy, set_forensic_fairy

forensic = ForensicScribeFairy(fabric=self.fabric)
forensic.boot()
set_forensic_fairy(forensic)
```

**Step 3: Test boot**

Run: `python server.py`
Expected: ForensicScribeFairy boots and logs "[ForensicScribeFairy] Booted"

**Step 4: Commit**

```bash
git add unconscious_mind/fairy.py
git commit -m "feat(boot): ensure ForensicScribeFairy boots with shared fabric"
```

---

### Task 5: Test Full Integration

**Step 1: Start the system**
```bash
python server.py
```

**Step 2: Open browser to test raw API**
```
http://127.0.0.1:5757/status
```
Verify telemetry contains `theGood`, `theBad`, `theUgly`

**Step 3: Launch Tauri GUI**
```bash
cd dashboard/src-tauri
cargo run --release
```

**Step 4: Navigate to Errors tab**

Verify:
- Three columns: Good, Bad, Ugly
- Health score at bottom
- Error details populated from theUgly

**Step 5: Trigger an error to test**

Stop a fairy or inject an error, verify it appears in theUgly

---

## Summary

After these tasks:
1. Server.py pulls from ForensicScribeFairy instead of just UnifiedRegistry
2. Data is classified into Good/Bad/Ugly using health status
3. GUI displays the three categories with health score
4. The forensic team (ForensicScribe, Librarian, TracerDaemon, DiaryHub) is actually used
