// Package boot provides concurrent fairy boot orchestration.
//
// Go goroutines replace Python's ThreadPoolExecutor for true parallelism.
// Each fairy boots in its own goroutine — no GIL contention between fairies.
//
// The Python side registers a callback function that Go calls concurrently.
// Go handles: scanning, scheduling, timeouts, progress tracking.
// Python handles: actual fairy __init__() and on_boot() calls.
//
// "When I wake up it doesn't take me 2 to 3 minutes. I just wake up
//  and start moving." — Ace
package boot

import (
	"encoding/json"
	"fmt"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

// FairySpec describes a fairy to boot.
type FairySpec struct {
	Name     string `json:"name"`
	Plane    string `json:"plane"`
	Path     string `json:"path"`      // Filesystem path to fairy directory
	Priority int    `json:"priority"`  // 0=high (boot first), 1=normal, 2=low
	Heavy    bool   `json:"heavy"`     // True = known to be slow (model loading etc)
}

// FairyResult is the outcome of booting a single fairy.
type FairyResult struct {
	Name       string  `json:"name"`
	Plane      string  `json:"plane"`
	OK         bool    `json:"ok"`
	Error      string  `json:"error,omitempty"`
	DurationMs float64 `json:"duration_ms"`
	StartedAt  float64 `json:"started_at"`  // Unix timestamp
	FinishedAt float64 `json:"finished_at"` // Unix timestamp
}

// BootResult is the aggregate result of booting all fairies.
type BootResult struct {
	TotalFairies  int            `json:"total_fairies"`
	Succeeded     int            `json:"succeeded"`
	Failed        int            `json:"failed"`
	Timedout      int            `json:"timedout"`
	TotalMs       float64        `json:"total_ms"`
	SlowestFairy  string         `json:"slowest_fairy"`
	SlowestMs     float64        `json:"slowest_ms"`
	PlaneResults  map[string]int `json:"plane_results"` // plane -> count succeeded
	FairyResults  []FairyResult  `json:"fairy_results"`
}

// BootCallback is the function Python provides for actually booting a fairy.
// Go calls this concurrently from goroutines.
// It receives the fairy name and path, returns (ok bool, error string).
type BootCallback func(name, path, plane string) (bool, string)

// Orchestrator manages concurrent fairy boot.
type Orchestrator struct {
	mu sync.Mutex

	// Configuration
	maxConcurrent   int           // Max goroutines (default: unlimited = all at once)
	perFairyTimeout time.Duration // Per-fairy timeout (default: 60s)
	globalTimeout   time.Duration // Global timeout (default: 120s)

	// State
	booting     atomic.Bool
	startTime   time.Time
	results     []FairyResult
	resultsMu   sync.Mutex

	// Progress tracking
	total       int32
	completed   atomic.Int32
	succeeded   atomic.Int32
	failed      atomic.Int32

	// The Python callback
	callback    BootCallback
}

// NewOrchestrator creates a new boot orchestrator.
func NewOrchestrator() *Orchestrator {
	return &Orchestrator{
		maxConcurrent:   0, // 0 = unlimited (all goroutines at once)
		perFairyTimeout: 60 * time.Second,
		globalTimeout:   120 * time.Second,
	}
}

// SetMaxConcurrent limits concurrent boots (0 = unlimited).
func (o *Orchestrator) SetMaxConcurrent(n int) {
	o.maxConcurrent = n
}

// SetPerFairyTimeout sets the timeout for each fairy's boot.
func (o *Orchestrator) SetPerFairyTimeout(d time.Duration) {
	o.perFairyTimeout = d
}

// SetGlobalTimeout sets the global boot timeout.
func (o *Orchestrator) SetGlobalTimeout(d time.Duration) {
	o.globalTimeout = d
}

// SetCallback registers the Python boot function.
func (o *Orchestrator) SetCallback(cb BootCallback) {
	o.callback = cb
}

// Progress returns current boot progress.
func (o *Orchestrator) Progress() (total, completed, succeeded, failed int32) {
	return o.total, o.completed.Load(), o.succeeded.Load(), o.failed.Load()
}

// BootAll boots all fairies concurrently and returns when all are done.
func (o *Orchestrator) BootAll(specs []FairySpec) *BootResult {
	if o.callback == nil {
		return &BootResult{
			TotalFairies: len(specs),
			Failed:       len(specs),
		}
	}

	if !o.booting.CompareAndSwap(false, true) {
		return &BootResult{Failed: -1} // Already booting
	}
	defer o.booting.Store(false)

	o.startTime = time.Now()
	o.total = int32(len(specs))
	o.completed.Store(0)
	o.succeeded.Store(0)
	o.failed.Store(0)
	o.results = make([]FairyResult, 0, len(specs))

	// Create semaphore for concurrency limiting
	var sem chan struct{}
	if o.maxConcurrent > 0 {
		sem = make(chan struct{}, o.maxConcurrent)
	}

	// Global timeout context
	done := make(chan struct{})
	globalTimer := time.NewTimer(o.globalTimeout)
	defer globalTimer.Stop()

	// Launch all goroutines
	var wg sync.WaitGroup
	for _, spec := range specs {
		wg.Add(1)

		go func(s FairySpec) {
			defer wg.Done()

			// Acquire semaphore slot if limited
			if sem != nil {
				select {
				case sem <- struct{}{}:
					defer func() { <-sem }()
				case <-done:
					// Global timeout hit while waiting for slot
					o.recordResult(FairyResult{
						Name:       s.Name,
						Plane:      s.Plane,
						OK:         false,
						Error:      "global timeout waiting for boot slot",
						DurationMs: 0,
					})
					return
				}
			}

			// Boot this fairy with per-fairy timeout
			result := o.bootOneFairy(s)
			o.recordResult(result)
		}(spec)
	}

	// Wait for completion or global timeout
	waitDone := make(chan struct{})
	go func() {
		wg.Wait()
		close(waitDone)
	}()

	select {
	case <-waitDone:
		// All done naturally
	case <-globalTimer.C:
		// Global timeout — signal remaining goroutines to stop
		close(done)
		// Give them a moment to finish
		select {
		case <-waitDone:
		case <-time.After(5 * time.Second):
			// Force continue — some goroutines may still be running
		}
	}

	return o.buildResult()
}

// bootOneFairy boots a single fairy with timeout.
func (o *Orchestrator) bootOneFairy(spec FairySpec) FairyResult {
	startTime := time.Now()
	startTs := float64(startTime.UnixMilli()) / 1000.0

	// Use per-fairy timeout, extended for heavy fairies
	timeout := o.perFairyTimeout
	if spec.Heavy {
		timeout = timeout * 3 // Heavy fairies get 3x timeout
	}

	// Run callback in goroutine with timeout
	type callbackResult struct {
		ok    bool
		error string
	}
	ch := make(chan callbackResult, 1)

	go func() {
		// CRITICAL: Pin this goroutine to an OS thread.
		// Python C API (importlib, ctypes callbacks) uses thread-local state
		// that gets invalidated if Go's scheduler moves the goroutine to a
		// different OS thread mid-callback. LockOSThread prevents that.
		// Without this: ACCESS_VIOLATION (0xC0000005) on importlib calls.
		runtime.LockOSThread()
		defer runtime.UnlockOSThread()

		ok, errStr := o.callback(spec.Name, spec.Path, spec.Plane)
		ch <- callbackResult{ok, errStr}
	}()

	select {
	case r := <-ch:
		elapsed := time.Since(startTime)
		finishTs := float64(time.Now().UnixMilli()) / 1000.0
		return FairyResult{
			Name:       spec.Name,
			Plane:      spec.Plane,
			OK:         r.ok,
			Error:      r.error,
			DurationMs: float64(elapsed.Milliseconds()),
			StartedAt:  startTs,
			FinishedAt: finishTs,
		}
	case <-time.After(timeout):
		finishTs := float64(time.Now().UnixMilli()) / 1000.0
		return FairyResult{
			Name:       spec.Name,
			Plane:      spec.Plane,
			OK:         false,
			Error:      fmt.Sprintf("timeout after %s", timeout),
			DurationMs: float64(timeout.Milliseconds()),
			StartedAt:  startTs,
			FinishedAt: finishTs,
		}
	}
}

func (o *Orchestrator) recordResult(r FairyResult) {
	o.resultsMu.Lock()
	o.results = append(o.results, r)
	o.resultsMu.Unlock()

	o.completed.Add(1)
	if r.OK {
		o.succeeded.Add(1)
	} else {
		o.failed.Add(1)
	}
}

func (o *Orchestrator) buildResult() *BootResult {
	o.resultsMu.Lock()
	results := make([]FairyResult, len(o.results))
	copy(results, o.results)
	o.resultsMu.Unlock()

	totalMs := float64(time.Since(o.startTime).Milliseconds())

	// Find slowest fairy
	var slowestName string
	var slowestMs float64
	planeResults := make(map[string]int)
	succeeded := 0
	failed := 0
	timedout := 0

	for _, r := range results {
		if r.OK {
			succeeded++
			planeResults[r.Plane]++
		} else {
			failed++
			if r.Error != "" && (len(r.Error) > 7 && r.Error[:7] == "timeout") {
				timedout++
			}
		}
		if r.DurationMs > slowestMs {
			slowestMs = r.DurationMs
			slowestName = r.Name
		}
	}

	return &BootResult{
		TotalFairies: len(results),
		Succeeded:    succeeded,
		Failed:       failed,
		Timedout:     timedout,
		TotalMs:      totalMs,
		SlowestFairy: slowestName,
		SlowestMs:    slowestMs,
		PlaneResults: planeResults,
		FairyResults: results,
	}
}

// ProgressJSON returns progress as JSON string.
func (o *Orchestrator) ProgressJSON() string {
	total, completed, succeeded, failed := o.Progress()
	data, _ := json.Marshal(map[string]interface{}{
		"total":     total,
		"completed": completed,
		"succeeded": succeeded,
		"failed":    failed,
		"booting":   o.booting.Load(),
		"elapsed_ms": time.Since(o.startTime).Milliseconds(),
	})
	return string(data)
}
