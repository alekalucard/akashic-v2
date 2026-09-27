// Package tracer provides universal tracing infrastructure for Akashic consciousness.
//
// Design Philosophy:
// - Every piece of work gets a tracer with full lineage
// - Tracers link to SRM clusters for perfect recall
// - Flexible identity: function names OR real names
// - Auto-registration with graceful degradation
package tracer

import (
	"sync"
	"time"

	"github.com/google/uuid"
)

// TracerType categorizes what kind of work this tracer tracks.
// Matches Python's TracerType enum from tracer_worker_system.py
type TracerType string

const (
	// Fairy cognitive work
	TypeFairyWork       TracerType = "fairy_work"
	TypeFairyThought    TracerType = "fairy_thought"
	TypeFairyReflection TracerType = "fairy_reflection"
	TypeFairyDecision   TracerType = "fairy_decision"
	TypeFairyAction     TracerType = "fairy_action"

	// Goal/chain tracking
	TypeGoal        TracerType = "goal"
	TypeThoughtChain TracerType = "thought_chain"
	TypeChainLink   TracerType = "chain_link"

	// External content
	TypeFileSystem   TracerType = "file_system"
	TypeFileUser     TracerType = "file_user"
	TypeMedia        TracerType = "media"
	TypeLiterature   TracerType = "literature"
	TypeConversation TracerType = "conversation"

	// System operations
	TypeTelemetry       TracerType = "telemetry"
	TypeCollision       TracerType = "collision"
	TypeMemoryOperation TracerType = "memory_operation"
	TypeWorkerTask      TracerType = "worker_task"
	TypePostalMessage   TracerType = "postal_message"
)

// TracerStatus tracks lifecycle state.
type TracerStatus string

const (
	StatusPending   TracerStatus = "pending"
	StatusRunning   TracerStatus = "running"
	StatusCompleted TracerStatus = "completed"
	StatusFailed    TracerStatus = "failed"
	StatusCancelled TracerStatus = "cancelled"
)

// Identity holds flexible naming for fairies/actors.
// Supports evolution from function names to real names.
type Identity struct {
	// Function name (e.g., "DirectoryFairy") - always set
	FunctionName string `json:"function_name"`

	// Real name (e.g., "Luna") - optional, for evolved identity
	RealName string `json:"real_name,omitempty"`

	// Display name - uses RealName if set, else FunctionName
	// Computed, not stored
	displayName string

	// Aliases for backward compatibility
	Aliases []string `json:"aliases,omitempty"`

	// Plane location (P00, P10, etc.)
	Plane string `json:"plane"`

	// Channel within plane
	Channel string `json:"channel,omitempty"`

	// Version
	Version string `json:"version,omitempty"`
}

// DisplayName returns the preferred display name.
func (id *Identity) DisplayName() string {
	if id.RealName != "" {
		return id.RealName
	}
	return id.FunctionName
}

// Matches checks if a name matches this identity (function, real, or alias).
func (id *Identity) Matches(name string) bool {
	if name == id.FunctionName || name == id.RealName {
		return true
	}
	for _, alias := range id.Aliases {
		if name == alias {
			return true
		}
	}
	return false
}

// UniversalTracer tracks a unit of work with full lineage.
// Matches Python's UniversalTracer from tracer_worker_system.py
type UniversalTracer struct {
	mu sync.RWMutex `json:"-"`

	// Core identity
	ID         string     `json:"id"`
	TracerType TracerType `json:"tracer_type"`

	// WHO created this
	FairyID   string    `json:"fairy_id"`
	FairyName string    `json:"fairy_name"`
	Identity  *Identity `json:"identity,omitempty"`

	// WHAT this is part of
	ChainID string `json:"chain_id,omitempty"`
	GoalID  string `json:"goal_id,omitempty"`

	// Lineage (WHERE in the tree)
	ParentTracerID string   `json:"parent_tracer_id,omitempty"`
	ChildrenIDs    []string `json:"children_ids,omitempty"`

	// SRM cluster membership (for perfect recall)
	ClusterID         string   `json:"cluster_id,omitempty"`
	RelatedClusterIDs []string `json:"related_cluster_ids,omitempty"`

	// Lifecycle
	CreatedAt   time.Time    `json:"created_at"`
	StartedAt   *time.Time   `json:"started_at,omitempty"`
	CompletedAt *time.Time   `json:"completed_at,omitempty"`
	Status      TracerStatus `json:"status"`
	Progress    float64      `json:"progress"`

	// Payload (what this tracer is tracking)
	Intent  string                 `json:"intent,omitempty"`
	Payload map[string]interface{} `json:"payload,omitempty"`

	// Telemetry data
	Telemetry *TelemetryData `json:"telemetry,omitempty"`

	// Error info if failed
	Error string `json:"error,omitempty"`

	// Tags for filtering/grouping
	Tags []string `json:"tags,omitempty"`
}

// TelemetryData holds metrics for a tracer.
type TelemetryData struct {
	// Timing
	QueuedDuration  time.Duration `json:"queued_duration_ns"`
	ProcessDuration time.Duration `json:"process_duration_ns"`
	TotalDuration   time.Duration `json:"total_duration_ns"`

	// Resource usage
	MemoryBytes   int64 `json:"memory_bytes,omitempty"`
	GoroutineID   int64 `json:"goroutine_id,omitempty"`
	WorkerPoolID  string `json:"worker_pool_id,omitempty"`

	// Counters
	RetryCount    int `json:"retry_count"`
	MessagesSent  int `json:"messages_sent"`
	MessagesRecv  int `json:"messages_received"`

	// Custom metrics
	Custom map[string]interface{} `json:"custom,omitempty"`
}

// NewTracer creates a new universal tracer.
func NewTracer(tracerType TracerType) *UniversalTracer {
	return &UniversalTracer{
		ID:         uuid.New().String()[:12],
		TracerType: tracerType,
		CreatedAt:  time.Now(),
		Status:     StatusPending,
		Progress:   0.0,
		ChildrenIDs: make([]string, 0),
		RelatedClusterIDs: make([]string, 0),
		Tags: make([]string, 0),
	}
}

// Start marks the tracer as running.
func (t *UniversalTracer) Start() {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now()
	t.StartedAt = &now
	t.Status = StatusRunning

	if t.Telemetry != nil {
		t.Telemetry.QueuedDuration = now.Sub(t.CreatedAt)
	}
}

// Complete marks the tracer as completed.
func (t *UniversalTracer) Complete() {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now()
	t.CompletedAt = &now
	t.Status = StatusCompleted
	t.Progress = 1.0

	if t.Telemetry != nil && t.StartedAt != nil {
		t.Telemetry.ProcessDuration = now.Sub(*t.StartedAt)
		t.Telemetry.TotalDuration = now.Sub(t.CreatedAt)
	}
}

// Fail marks the tracer as failed.
func (t *UniversalTracer) Fail(err error) {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now()
	t.CompletedAt = &now
	t.Status = StatusFailed
	if err != nil {
		t.Error = err.Error()
	}

	if t.Telemetry != nil && t.StartedAt != nil {
		t.Telemetry.ProcessDuration = now.Sub(*t.StartedAt)
		t.Telemetry.TotalDuration = now.Sub(t.CreatedAt)
	}
}

// AddChild registers a child tracer.
func (t *UniversalTracer) AddChild(childID string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.ChildrenIDs = append(t.ChildrenIDs, childID)
}

// SetProgress updates progress (0.0 to 1.0).
func (t *UniversalTracer) SetProgress(p float64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if p < 0 {
		p = 0
	}
	if p > 1 {
		p = 1
	}
	t.Progress = p
}

// WithIdentity attaches an identity to the tracer.
func (t *UniversalTracer) WithIdentity(id *Identity) *UniversalTracer {
	t.Identity = id
	t.FairyName = id.DisplayName()
	return t
}

// WithCluster attaches to an SRM cluster.
func (t *UniversalTracer) WithCluster(clusterID string) *UniversalTracer {
	t.ClusterID = clusterID
	return t
}

// WithParent sets the parent tracer for lineage.
func (t *UniversalTracer) WithParent(parentID string) *UniversalTracer {
	t.ParentTracerID = parentID
	return t
}

// WithIntent sets the intent/purpose of this tracer.
func (t *UniversalTracer) WithIntent(intent string) *UniversalTracer {
	t.Intent = intent
	return t
}

// WithPayload attaches data to the tracer.
func (t *UniversalTracer) WithPayload(payload map[string]interface{}) *UniversalTracer {
	t.Payload = payload
	return t
}

// WithTags adds tags for filtering.
func (t *UniversalTracer) WithTags(tags ...string) *UniversalTracer {
	t.Tags = append(t.Tags, tags...)
	return t
}

// EnableTelemetry initializes telemetry tracking.
func (t *UniversalTracer) EnableTelemetry() *UniversalTracer {
	t.Telemetry = &TelemetryData{
		Custom: make(map[string]interface{}),
	}
	return t
}

// Spawn creates a child tracer with this as parent.
func (t *UniversalTracer) Spawn(tracerType TracerType) *UniversalTracer {
	child := NewTracer(tracerType)
	child.ParentTracerID = t.ID
	child.FairyID = t.FairyID
	child.FairyName = t.FairyName
	child.Identity = t.Identity
	child.ClusterID = t.ClusterID
	child.ChainID = t.ChainID
	child.GoalID = t.GoalID

	t.AddChild(child.ID)
	return child
}
