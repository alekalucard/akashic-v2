// Package main provides Python/C bindings for the tracer pool.
//
// This uses cgo to export functions that Python can call via ctypes.
// Build with: go build -buildmode=c-shared -o tracer_pool.dll ./pkg/bridge
package main

/*
#include <stdlib.h>
#include <stdint.h>

// Callback function type for Python handlers
typedef void (*WorkCallback)(void* ctx);
typedef void (*ResultCallback)(void* ctx, int success, const char* error);

// Boot callback: Python provides this to boot a single fairy.
// Go calls it concurrently from goroutines.
// Returns: 0 = success, non-zero = failure. error_out filled on failure.
typedef int (*BootFairyCallback)(const char* name, const char* path, const char* plane, char* error_out, int error_buf_size);

// Progress callback: called by Go to report boot progress.
typedef void (*BootProgressCallback)(int total, int completed, int succeeded, int failed);

// C helper to call boot fairy callback (CGo can't call function pointers directly)
static inline int call_boot_fairy(BootFairyCallback cb, const char* name, const char* path, const char* plane, char* error_out, int error_buf_size) {
    return cb(name, path, plane, error_out, error_buf_size);
}

// C helper to call progress callback
static inline void call_boot_progress(BootProgressCallback cb, int total, int completed, int succeeded, int failed) {
    cb(total, completed, succeeded, failed);
}
*/
import "C"
import (
	"context"
	"encoding/json"
	"runtime"
	"sync"
	"time"
	"unsafe"

	"akashic/tracer_pool/internal/boot"
	"akashic/tracer_pool/internal/pool"
	"akashic/tracer_pool/internal/registry"
	"akashic/tracer_pool/internal/tracer"
)

var (
	// Manager instance
	manager *pool.PoolManager
	reg     *registry.Registry
	initOnce sync.Once

	// Callback storage (prevent GC)
	callbacks sync.Map
	callbackID uint64
	callbackMu sync.Mutex

	// Boot orchestrator
	bootOrch     *boot.Orchestrator
	bootCallback C.BootFairyCallback
	bootProgress C.BootProgressCallback
	bootMu       sync.Mutex
)

func init() {
	initOnce.Do(func() {
		manager = pool.GlobalManager()
		reg = registry.GlobalRegistry()
	})
}

//export TracerPoolInit
func TracerPoolInit() C.int {
	initOnce.Do(func() {
		manager = pool.GlobalManager()
		reg = registry.GlobalRegistry()
	})
	return 0
}

//export TracerPoolShutdown
func TracerPoolShutdown() {
	if manager != nil {
		manager.Shutdown()
	}
}

//export CreateTracer
func CreateTracer(tracerType *C.char) *C.char {
	tType := tracer.TracerType(C.GoString(tracerType))
	t := tracer.NewTracer(tType)
	t.EnableTelemetry()
	reg.Register(t)

	return C.CString(t.ID)
}

//export CreateTracerFull
func CreateTracerFull(
	tracerType *C.char,
	fairyName *C.char,
	clusterID *C.char,
	intent *C.char,
	payloadJSON *C.char,
) *C.char {
	tType := tracer.TracerType(C.GoString(tracerType))
	t := tracer.NewTracer(tType)
	t.EnableTelemetry()

	if fairyName != nil {
		t.FairyName = C.GoString(fairyName)
	}
	if clusterID != nil {
		t.ClusterID = C.GoString(clusterID)
	}
	if intent != nil {
		t.Intent = C.GoString(intent)
	}
	if payloadJSON != nil {
		var payload map[string]interface{}
		if err := json.Unmarshal([]byte(C.GoString(payloadJSON)), &payload); err == nil {
			t.Payload = payload
		}
	}

	reg.Register(t)
	return C.CString(t.ID)
}

//export TracerStart
func TracerStart(tracerID *C.char) {
	t := reg.Get(C.GoString(tracerID))
	if t != nil {
		t.Start()
	}
}

//export TracerComplete
func TracerComplete(tracerID *C.char) {
	t := reg.Get(C.GoString(tracerID))
	if t != nil {
		t.Complete()
	}
}

//export TracerFail
func TracerFail(tracerID *C.char, errorMsg *C.char) {
	t := reg.Get(C.GoString(tracerID))
	if t != nil {
		t.Error = C.GoString(errorMsg)
		t.Fail(nil)
	}
}

//export TracerSetProgress
func TracerSetProgress(tracerID *C.char, progress C.double) {
	t := reg.Get(C.GoString(tracerID))
	if t != nil {
		t.SetProgress(float64(progress))
	}
}

//export TracerSpawn
func TracerSpawn(parentID *C.char, tracerType *C.char) *C.char {
	parent := reg.Get(C.GoString(parentID))
	if parent == nil {
		return nil
	}

	tType := tracer.TracerType(C.GoString(tracerType))
	child := parent.Spawn(tType)
	child.EnableTelemetry()
	reg.Register(child)

	return C.CString(child.ID)
}

//export GetTracer
func GetTracer(tracerID *C.char) *C.char {
	t := reg.Get(C.GoString(tracerID))
	if t == nil {
		return nil
	}

	data, err := json.Marshal(t)
	if err != nil {
		return nil
	}
	return C.CString(string(data))
}

//export GetTracersByFairy
func GetTracersByFairy(fairyName *C.char) *C.char {
	tracers := reg.GetByFairyName(C.GoString(fairyName))
	data, err := json.Marshal(tracers)
	if err != nil {
		return nil
	}
	return C.CString(string(data))
}

//export GetTracersByCluster
func GetTracersByCluster(clusterID *C.char) *C.char {
	tracers := reg.GetByCluster(C.GoString(clusterID))
	data, err := json.Marshal(tracers)
	if err != nil {
		return nil
	}
	return C.CString(string(data))
}

//export GetLineage
func GetLineage(tracerID *C.char) *C.char {
	lineage := reg.GetLineage(C.GoString(tracerID))
	data, err := json.Marshal(lineage)
	if err != nil {
		return nil
	}
	return C.CString(string(data))
}

//export RegisterIdentity
func RegisterIdentity(
	functionName *C.char,
	realName *C.char,
	plane *C.char,
	channel *C.char,
	aliasesJSON *C.char,
) {
	id := &tracer.Identity{
		FunctionName: C.GoString(functionName),
		Plane:        C.GoString(plane),
	}
	if realName != nil {
		id.RealName = C.GoString(realName)
	}
	if channel != nil {
		id.Channel = C.GoString(channel)
	}
	if aliasesJSON != nil {
		var aliases []string
		if err := json.Unmarshal([]byte(C.GoString(aliasesJSON)), &aliases); err == nil {
			id.Aliases = aliases
		}
	}

	reg.RegisterIdentity(id)
}

//export ResolveIdentity
func ResolveIdentity(name *C.char) *C.char {
	id := reg.ResolveIdentity(C.GoString(name))
	if id == nil {
		return nil
	}
	data, err := json.Marshal(id)
	if err != nil {
		return nil
	}
	return C.CString(string(data))
}

//export GetOrCreatePool
func GetOrCreatePool(fairyName *C.char) C.int {
	name := C.GoString(fairyName)
	p := manager.GetOrCreatePool(name)
	if p != nil {
		return 0
	}
	return -1
}

//export SubmitTask
func SubmitTask(
	fairyName *C.char,
	priority C.int,
	tracerID *C.char,
	callback C.WorkCallback,
	ctx unsafe.Pointer,
	resultCallback C.ResultCallback,
	resultCtx unsafe.Pointer,
) C.int {
	name := C.GoString(fairyName)
	p := manager.GetOrCreatePool(name)

	// Get or create tracer
	var t *tracer.UniversalTracer
	if tracerID != nil {
		t = reg.Get(C.GoString(tracerID))
	}
	if t == nil {
		t = tracer.NewTracer(tracer.TypeWorkerTask)
		t.FairyName = name
		t.EnableTelemetry()
		reg.Register(t)
	}

	// Store callback info
	callbackMu.Lock()
	callbackID++
	id := callbackID
	callbackMu.Unlock()

	callbacks.Store(id, struct {
		cb  C.WorkCallback
		ctx unsafe.Pointer
		rcb C.ResultCallback
		rctx unsafe.Pointer
	}{callback, ctx, resultCallback, resultCtx})

	// Submit task (simplified - no callbacks for now, use polling)
	err := p.SubmitWithTracer(pool.Priority(priority), t, func(c context.Context) error {
		// Work is tracked via tracer - Python can poll for completion
		return nil
	})

	if err != nil {
		return -1
	}

	return 0
}

//export GetPoolStats
func GetPoolStats(fairyName *C.char) *C.char {
	var stats map[string]interface{}
	if fairyName != nil {
		name := C.GoString(fairyName)
		p := manager.GetPool(name)
		if p != nil {
			stats = p.Metrics()
		}
	} else {
		stats = manager.Stats()
	}

	data, err := json.Marshal(stats)
	if err != nil {
		return nil
	}
	return C.CString(string(data))
}

//export GetRegistryStats
func GetRegistryStats() *C.char {
	stats := reg.Stats()
	data, err := json.Marshal(stats)
	if err != nil {
		return nil
	}
	return C.CString(string(data))
}

// ============================================================
// Boot Orchestrator exports
// ============================================================

//export BootOrchestratorInit
func BootOrchestratorInit(maxConcurrent C.int, perFairyTimeoutMs C.int, globalTimeoutMs C.int) C.int {
	bootMu.Lock()
	defer bootMu.Unlock()

	bootOrch = boot.NewOrchestrator()

	if maxConcurrent > 0 {
		bootOrch.SetMaxConcurrent(int(maxConcurrent))
	}
	if perFairyTimeoutMs > 0 {
		bootOrch.SetPerFairyTimeout(time.Duration(perFairyTimeoutMs) * time.Millisecond)
	}
	if globalTimeoutMs > 0 {
		bootOrch.SetGlobalTimeout(time.Duration(globalTimeoutMs) * time.Millisecond)
	}

	return 0
}

//export BootSetCallback
func BootSetCallback(cb C.BootFairyCallback, progressCb C.BootProgressCallback) C.int {
	bootMu.Lock()
	defer bootMu.Unlock()

	if bootOrch == nil {
		return -1
	}

	// Store C callbacks (prevent GC)
	bootCallback = cb
	bootProgress = progressCb

	// Wrap the C callback into a Go BootCallback
	// This is called concurrently from goroutines — the C callback
	// calls into Python's ctypes CFUNCTYPE which acquires the GIL.
	//
	// CRITICAL: LockOSThread pins this goroutine to one OS thread.
	// Python C API uses thread-local state (PyThreadState) that gets
	// invalidated if Go's scheduler migrates the goroutine to another
	// OS thread during the callback. Without this: ACCESS_VIOLATION.
	//
	// Note: boot.go also calls LockOSThread in bootOneFairy's goroutine.
	// Both locks are needed — boot.go pins the outer goroutine, this
	// pins the callback execution context. Belt and suspenders.
	bootOrch.SetCallback(func(name, path, plane string) (bool, string) {
		// Pin to OS thread for Python C API safety
		runtime.LockOSThread()
		defer runtime.UnlockOSThread()

		cName := C.CString(name)
		cPath := C.CString(path)
		cPlane := C.CString(plane)
		defer C.free(unsafe.Pointer(cName))
		defer C.free(unsafe.Pointer(cPath))
		defer C.free(unsafe.Pointer(cPlane))

		// Error buffer for the callback to fill
		errBuf := (*C.char)(C.malloc(1024))
		defer C.free(unsafe.Pointer(errBuf))

		// Call Python's boot function through C helper
		result := C.call_boot_fairy(cb, cName, cPath, cPlane, errBuf, 1024)

		if result == 0 {
			return true, ""
		}
		return false, C.GoString(errBuf)
	})

	return 0
}

//export BootAllFairies
func BootAllFairies(specsJSON *C.char) *C.char {
	bootMu.Lock()
	orch := bootOrch
	progressCb := bootProgress
	bootMu.Unlock()

	if orch == nil {
		errResult := map[string]interface{}{
			"error": "boot orchestrator not initialized",
		}
		data, _ := json.Marshal(errResult)
		return C.CString(string(data))
	}

	// Parse fairy specs from JSON
	var specs []boot.FairySpec
	if err := json.Unmarshal([]byte(C.GoString(specsJSON)), &specs); err != nil {
		errResult := map[string]interface{}{
			"error": "invalid specs JSON: " + err.Error(),
		}
		data, _ := json.Marshal(errResult)
		return C.CString(string(data))
	}

	// Start progress reporter goroutine
	if progressCb != nil {
		go func() {
			// Pin to OS thread — this goroutine calls into Python via C callback
			runtime.LockOSThread()
			defer runtime.UnlockOSThread()

			ticker := time.NewTicker(500 * time.Millisecond)
			defer ticker.Stop()
			for {
				total, completed, succeeded, failed := orch.Progress()
				if total == 0 {
					return
				}
				// Call progress callback through C helper
				C.call_boot_progress(progressCb, C.int(total), C.int(completed), C.int(succeeded), C.int(failed))
				if completed >= total {
					return
				}
				<-ticker.C
			}
		}()
	}

	// Boot all fairies — this blocks until all are done or global timeout
	result := orch.BootAll(specs)

	// Serialize result to JSON
	data, err := json.Marshal(result)
	if err != nil {
		errResult := map[string]interface{}{
			"error": "failed to serialize result: " + err.Error(),
		}
		data, _ = json.Marshal(errResult)
		return C.CString(string(data))
	}

	return C.CString(string(data))
}

//export BootGetProgress
func BootGetProgress() *C.char {
	bootMu.Lock()
	orch := bootOrch
	bootMu.Unlock()

	if orch == nil {
		return C.CString("{}")
	}

	return C.CString(orch.ProgressJSON())
}

//export BootIsRunning
func BootIsRunning() C.int {
	bootMu.Lock()
	orch := bootOrch
	bootMu.Unlock()

	if orch == nil {
		return 0
	}

	total, completed, _, _ := orch.Progress()
	if total > 0 && completed < total {
		return 1
	}
	return 0
}

//export FreeString
func FreeString(s *C.char) {
	if s != nil {
		C.free(unsafe.Pointer(s))
	}
}

// Main is required for c-shared build mode
func main() {}
