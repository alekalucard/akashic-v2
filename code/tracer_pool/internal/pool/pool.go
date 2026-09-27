// Package pool provides smart worker pools with goroutine-based scheduling.
//
// Features:
// - Three priority lanes (like Rust postal)
// - Autoscaling based on queue depth and latency
// - Per-fairy worker pools with isolation
// - Smart scheduling with backpressure
// - Full tracer integration
package pool

import (
	"context"
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"akashic/tracer_pool/internal/registry"
	"akashic/tracer_pool/internal/tracer"
)

// Priority levels (matching Rust postal)
type Priority int

const (
	PriorityHigh   Priority = 0
	PriorityNormal Priority = 1
	PriorityLow    Priority = 2
)

// Task represents work to be done.
type Task struct {
	// Tracer for this task
	Tracer *tracer.UniversalTracer

	// The work to do
	Work func(ctx context.Context) error

	// Priority level
	Priority Priority

	// Context for cancellation
	Ctx context.Context

	// When this was queued
	QueuedAt time.Time

	// Result channel (optional)
	Done chan error
}

// PoolConfig configures a worker pool.
type PoolConfig struct {
	// Pool name (usually fairy name)
	Name string

	// Worker limits
	MinWorkers int
	MaxWorkers int

	// Queue capacities per priority
	HighCapacity   int
	NormalCapacity int
	LowCapacity    int

	// Target latency for autoscaling
	TargetP95Ms int64

	// Autoscale interval
	AutoscaleInterval time.Duration

	// CPU pressure thresholds
	CPUHotThreshold  float64
	CPUCoolThreshold float64
}

// DefaultConfig returns sensible defaults.
func DefaultConfig(name string) *PoolConfig {
	return &PoolConfig{
		Name:              name,
		MinWorkers:        1,
		MaxWorkers:        runtime.NumCPU(),
		HighCapacity:      128,
		NormalCapacity:    512,
		LowCapacity:       1024,
		TargetP95Ms:       150,
		AutoscaleInterval: 250 * time.Millisecond,
		CPUHotThreshold:   0.85,
		CPUCoolThreshold:  0.55,
	}
}

// Pool is a smart worker pool with priority lanes.
type Pool struct {
	config *PoolConfig

	// Priority queues
	highQueue   chan *Task
	normalQueue chan *Task
	lowQueue    chan *Task

	// Worker management
	workerCount atomic.Int32
	workers     sync.WaitGroup
	stopCh      chan struct{}
	mu          sync.RWMutex

	// Metrics
	metrics *PoolMetrics

	// Registry for tracer registration
	registry *registry.Registry

	// Identity for this pool's fairy
	identity *tracer.Identity

	// Running state
	running atomic.Bool
}

// PoolMetrics tracks pool performance.
type PoolMetrics struct {
	mu sync.RWMutex

	TasksQueued    atomic.Int64
	TasksCompleted atomic.Int64
	TasksFailed    atomic.Int64
	TasksDropped   atomic.Int64

	// Latency tracking (last 100 samples)
	latencies   []time.Duration
	latencyIdx  int
	latencyFull bool
}

func newPoolMetrics() *PoolMetrics {
	return &PoolMetrics{
		latencies: make([]time.Duration, 100),
	}
}

func (m *PoolMetrics) recordLatency(d time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.latencies[m.latencyIdx] = d
	m.latencyIdx = (m.latencyIdx + 1) % len(m.latencies)
	if m.latencyIdx == 0 {
		m.latencyFull = true
	}
}

func (m *PoolMetrics) P95() time.Duration {
	m.mu.RLock()
	defer m.mu.RUnlock()

	count := m.latencyIdx
	if m.latencyFull {
		count = len(m.latencies)
	}
	if count == 0 {
		return 0
	}

	// Simple P95: sort and get 95th percentile
	sorted := make([]time.Duration, count)
	copy(sorted, m.latencies[:count])

	// Bubble sort (fine for 100 items)
	for i := 0; i < len(sorted)-1; i++ {
		for j := 0; j < len(sorted)-i-1; j++ {
			if sorted[j] > sorted[j+1] {
				sorted[j], sorted[j+1] = sorted[j+1], sorted[j]
			}
		}
	}

	idx := int(float64(count) * 0.95)
	if idx >= count {
		idx = count - 1
	}
	return sorted[idx]
}

func (m *PoolMetrics) Stats() map[string]interface{} {
	return map[string]interface{}{
		"tasks_queued":    m.TasksQueued.Load(),
		"tasks_completed": m.TasksCompleted.Load(),
		"tasks_failed":    m.TasksFailed.Load(),
		"tasks_dropped":   m.TasksDropped.Load(),
		"p95_ms":          m.P95().Milliseconds(),
	}
}

// NewPool creates a new worker pool.
func NewPool(config *PoolConfig) *Pool {
	if config == nil {
		config = DefaultConfig("default")
	}

	p := &Pool{
		config:      config,
		highQueue:   make(chan *Task, config.HighCapacity),
		normalQueue: make(chan *Task, config.NormalCapacity),
		lowQueue:    make(chan *Task, config.LowCapacity),
		stopCh:      make(chan struct{}),
		metrics:     newPoolMetrics(),
		registry:    registry.GlobalRegistry(),
	}

	return p
}

// WithIdentity attaches an identity to this pool.
func (p *Pool) WithIdentity(id *tracer.Identity) *Pool {
	p.identity = id
	return p
}

// WithRegistry uses a custom registry.
func (p *Pool) WithRegistry(reg *registry.Registry) *Pool {
	p.registry = reg
	return p
}

// Start begins the worker pool.
func (p *Pool) Start() {
	if p.running.Swap(true) {
		return // Already running
	}

	// Start minimum workers
	for i := 0; i < p.config.MinWorkers; i++ {
		p.spawnWorker()
	}

	// Start autoscaler
	go p.autoscaler()
}

// Stop gracefully shuts down the pool.
func (p *Pool) Stop() {
	if !p.running.Swap(false) {
		return // Not running
	}

	close(p.stopCh)
	p.workers.Wait()
}

// Submit submits a task to the pool.
func (p *Pool) Submit(task *Task) error {
	if !p.running.Load() {
		return ErrPoolStopped
	}

	task.QueuedAt = time.Now()

	// Initialize tracer if not set
	if task.Tracer == nil {
		task.Tracer = tracer.NewTracer(tracer.TypeWorkerTask)
		if p.identity != nil {
			task.Tracer.WithIdentity(p.identity)
		}
	}
	task.Tracer.EnableTelemetry()

	// Register with registry
	p.registry.Register(task.Tracer)

	// Route to appropriate queue
	queue := p.queueFor(task.Priority)
	select {
	case queue <- task:
		p.metrics.TasksQueued.Add(1)
		return nil
	default:
		// Queue full - apply backpressure
		return p.applyBackpressure(task)
	}
}

// SubmitFunc is a convenience wrapper for simple functions.
func (p *Pool) SubmitFunc(priority Priority, work func(ctx context.Context) error) error {
	return p.Submit(&Task{
		Priority: priority,
		Work:     work,
		Ctx:      context.Background(),
	})
}

// SubmitWithTracer submits work with an existing tracer.
func (p *Pool) SubmitWithTracer(priority Priority, t *tracer.UniversalTracer, work func(ctx context.Context) error) error {
	return p.Submit(&Task{
		Tracer:   t,
		Priority: priority,
		Work:     work,
		Ctx:      context.Background(),
	})
}

func (p *Pool) queueFor(priority Priority) chan *Task {
	switch priority {
	case PriorityHigh:
		return p.highQueue
	case PriorityNormal:
		return p.normalQueue
	default:
		return p.lowQueue
	}
}

func (p *Pool) applyBackpressure(task *Task) error {
	// Try to drop oldest low priority task
	select {
	case dropped := <-p.lowQueue:
		if dropped.Tracer != nil {
			dropped.Tracer.Fail(ErrDroppedBackpressure)
		}
		p.metrics.TasksDropped.Add(1)

		// Retry submission
		queue := p.queueFor(task.Priority)
		select {
		case queue <- task:
			p.metrics.TasksQueued.Add(1)
			return nil
		default:
			return ErrQueueFull
		}
	default:
		// No low priority to drop
		if task.Priority == PriorityLow {
			p.metrics.TasksDropped.Add(1)
			return ErrQueueFull
		}
		return ErrQueueFull
	}
}

func (p *Pool) spawnWorker() {
	p.workerCount.Add(1)
	p.workers.Add(1)

	go func() {
		defer p.workers.Done()
		defer p.workerCount.Add(-1)

		for {
			// Priority order: HIGH -> NORMAL -> LOW
			var task *Task
			select {
			case <-p.stopCh:
				return
			case task = <-p.highQueue:
			default:
				select {
				case <-p.stopCh:
					return
				case task = <-p.highQueue:
				case task = <-p.normalQueue:
				default:
					select {
					case <-p.stopCh:
						return
					case task = <-p.highQueue:
					case task = <-p.normalQueue:
					case task = <-p.lowQueue:
					case <-time.After(20 * time.Millisecond):
						continue
					}
				}
			}

			if task == nil {
				continue
			}

			p.executeTask(task)
		}
	}()
}

func (p *Pool) executeTask(task *Task) {
	start := time.Now()

	// Update tracer
	if task.Tracer != nil {
		task.Tracer.Start()
		task.Tracer.Telemetry.QueuedDuration = start.Sub(task.QueuedAt)
	}

	// Execute
	ctx := task.Ctx
	if ctx == nil {
		ctx = context.Background()
	}

	err := task.Work(ctx)

	// Record result
	elapsed := time.Since(start)
	p.metrics.recordLatency(elapsed)

	if task.Tracer != nil {
		task.Tracer.Telemetry.ProcessDuration = elapsed
		if err != nil {
			task.Tracer.Fail(err)
			p.metrics.TasksFailed.Add(1)
		} else {
			task.Tracer.Complete()
			p.metrics.TasksCompleted.Add(1)
		}
	} else {
		if err != nil {
			p.metrics.TasksFailed.Add(1)
		} else {
			p.metrics.TasksCompleted.Add(1)
		}
	}

	// Signal completion
	if task.Done != nil {
		task.Done <- err
		close(task.Done)
	}
}

func (p *Pool) autoscaler() {
	ticker := time.NewTicker(p.config.AutoscaleInterval)
	defer ticker.Stop()

	for {
		select {
		case <-p.stopCh:
			return
		case <-ticker.C:
			p.checkScale()
		}
	}
}

func (p *Pool) checkScale() {
	current := int(p.workerCount.Load())
	queueDepth := len(p.highQueue) + len(p.normalQueue) + len(p.lowQueue)
	p95 := p.metrics.P95().Milliseconds()

	// Simple autoscaling logic
	shouldScaleUp := (queueDepth > current*8 || p95 > p.config.TargetP95Ms) &&
		current < p.config.MaxWorkers

	shouldScaleDown := queueDepth < 2 &&
		p95 < p.config.TargetP95Ms/2 &&
		current > p.config.MinWorkers

	if shouldScaleUp {
		p.spawnWorker()
	} else if shouldScaleDown {
		// Signal one worker to stop (they check stopCh)
		// This is a simple approach; more sophisticated would be to have per-worker stop channels
	}
}

// QueueDepth returns total items across all queues.
func (p *Pool) QueueDepth() int {
	return len(p.highQueue) + len(p.normalQueue) + len(p.lowQueue)
}

// Workers returns current worker count.
func (p *Pool) Workers() int {
	return int(p.workerCount.Load())
}

// Metrics returns pool metrics.
func (p *Pool) Metrics() map[string]interface{} {
	stats := p.metrics.Stats()
	stats["workers"] = p.Workers()
	stats["queue_depth"] = p.QueueDepth()
	stats["pool_name"] = p.config.Name
	return stats
}

// Errors
var (
	ErrPoolStopped        = poolError("pool is stopped")
	ErrQueueFull          = poolError("queue is full")
	ErrDroppedBackpressure = poolError("dropped due to backpressure")
)

type poolError string

func (e poolError) Error() string { return string(e) }
