// Package registry provides the global tracer registry with multiple lookup paths.
//
// Lookup capabilities (for perfect recall):
// - By tracer ID
// - By fairy ID/name
// - By SRM cluster ID
// - By chain/goal ID
// - By parent (get full lineage)
// - By tags
// - By status
package registry

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"time"

	"akashic/tracer_pool/internal/tracer"
)

// Registry is the global tracer registry.
type Registry struct {
	mu sync.RWMutex

	// Primary storage
	tracers map[string]*tracer.UniversalTracer

	// Index by fairy
	byFairy map[string][]string // fairy_id -> []tracer_id

	// Index by fairy name (supports real names)
	byFairyName map[string][]string // fairy_name -> []tracer_id

	// Index by SRM cluster (perfect recall)
	byCluster map[string][]string // cluster_id -> []tracer_id

	// Index by chain
	byChain map[string][]string // chain_id -> []tracer_id

	// Index by goal
	byGoal map[string][]string // goal_id -> []tracer_id

	// Index by tag
	byTag map[string][]string // tag -> []tracer_id

	// Index by status
	byStatus map[tracer.TracerStatus][]string

	// Identity registry (fairy function names -> Identity)
	identities map[string]*tracer.Identity

	// Persistence
	persistPath string
	autosave    bool
	saveTimer   *time.Timer
}

// Global singleton
var (
	globalRegistry *Registry
	registryOnce   sync.Once
)

// GlobalRegistry returns the global registry singleton.
func GlobalRegistry() *Registry {
	registryOnce.Do(func() {
		globalRegistry = NewRegistry()
	})
	return globalRegistry
}

// NewRegistry creates a new registry.
func NewRegistry() *Registry {
	r := &Registry{
		tracers:     make(map[string]*tracer.UniversalTracer),
		byFairy:     make(map[string][]string),
		byFairyName: make(map[string][]string),
		byCluster:   make(map[string][]string),
		byChain:     make(map[string][]string),
		byGoal:      make(map[string][]string),
		byTag:       make(map[string][]string),
		byStatus:    make(map[tracer.TracerStatus][]string),
		identities:  make(map[string]*tracer.Identity),
	}
	return r
}

// SetPersistPath configures persistence and loads existing state.
func (r *Registry) SetPersistPath(path string) error {
	r.mu.Lock()
	r.persistPath = path
	r.mu.Unlock()

	// Try to load existing state
	return r.Load()
}

// EnableAutosave starts periodic saves.
func (r *Registry) EnableAutosave(interval time.Duration) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.autosave = true
	r.startAutosave(interval)
}

func (r *Registry) startAutosave(interval time.Duration) {
	if r.saveTimer != nil {
		r.saveTimer.Stop()
	}
	r.saveTimer = time.AfterFunc(interval, func() {
		_ = r.Save()
		r.mu.Lock()
		r.startAutosave(interval)
		r.mu.Unlock()
	})
}

// Register adds a tracer to the registry and indexes it.
func (r *Registry) Register(t *tracer.UniversalTracer) *tracer.UniversalTracer {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Store tracer
	r.tracers[t.ID] = t

	// Index by fairy
	if t.FairyID != "" {
		r.byFairy[t.FairyID] = append(r.byFairy[t.FairyID], t.ID)
	}

	// Index by fairy name (supports real names and function names)
	if t.FairyName != "" {
		r.byFairyName[t.FairyName] = append(r.byFairyName[t.FairyName], t.ID)
	}
	if t.Identity != nil {
		// Also index by function name if different from display
		if t.Identity.FunctionName != "" && t.Identity.FunctionName != t.FairyName {
			r.byFairyName[t.Identity.FunctionName] = append(r.byFairyName[t.Identity.FunctionName], t.ID)
		}
		// Index by aliases
		for _, alias := range t.Identity.Aliases {
			r.byFairyName[alias] = append(r.byFairyName[alias], t.ID)
		}
	}

	// Index by cluster (perfect recall)
	if t.ClusterID != "" {
		r.byCluster[t.ClusterID] = append(r.byCluster[t.ClusterID], t.ID)
	}
	for _, relatedCluster := range t.RelatedClusterIDs {
		r.byCluster[relatedCluster] = append(r.byCluster[relatedCluster], t.ID)
	}

	// Index by chain
	if t.ChainID != "" {
		r.byChain[t.ChainID] = append(r.byChain[t.ChainID], t.ID)
	}

	// Index by goal
	if t.GoalID != "" {
		r.byGoal[t.GoalID] = append(r.byGoal[t.GoalID], t.ID)
	}

	// Index by tags
	for _, tag := range t.Tags {
		r.byTag[tag] = append(r.byTag[tag], t.ID)
	}

	// Index by status
	r.byStatus[t.Status] = append(r.byStatus[t.Status], t.ID)

	return t
}

// Get retrieves a tracer by ID.
func (r *Registry) Get(id string) *tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.tracers[id]
}

// GetByFairy returns all tracers for a fairy ID.
func (r *Registry) GetByFairy(fairyID string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := r.byFairy[fairyID]
	return r.getMultiple(ids)
}

// GetByFairyName returns all tracers for a fairy by name.
// Supports function names, real names, and aliases.
func (r *Registry) GetByFairyName(name string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := r.byFairyName[name]
	return r.getMultiple(ids)
}

// GetByCluster returns all tracers for an SRM cluster (perfect recall).
func (r *Registry) GetByCluster(clusterID string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := r.byCluster[clusterID]
	return r.getMultiple(ids)
}

// GetByChain returns all tracers in a thought chain.
func (r *Registry) GetByChain(chainID string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := r.byChain[chainID]
	return r.getMultiple(ids)
}

// GetByGoal returns all tracers for a goal.
func (r *Registry) GetByGoal(goalID string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := r.byGoal[goalID]
	return r.getMultiple(ids)
}

// GetByTag returns all tracers with a specific tag.
func (r *Registry) GetByTag(tag string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := r.byTag[tag]
	return r.getMultiple(ids)
}

// GetByStatus returns all tracers with a specific status.
func (r *Registry) GetByStatus(status tracer.TracerStatus) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := r.byStatus[status]
	return r.getMultiple(ids)
}

// GetLineage returns the full parent->child chain for a tracer.
func (r *Registry) GetLineage(tracerID string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var lineage []*tracer.UniversalTracer

	// Walk up to root
	current := r.tracers[tracerID]
	var ancestors []*tracer.UniversalTracer
	for current != nil {
		ancestors = append([]*tracer.UniversalTracer{current}, ancestors...)
		if current.ParentTracerID == "" {
			break
		}
		current = r.tracers[current.ParentTracerID]
	}

	lineage = append(lineage, ancestors...)
	return lineage
}

// GetDescendants returns all descendants of a tracer.
func (r *Registry) GetDescendants(tracerID string) []*tracer.UniversalTracer {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var descendants []*tracer.UniversalTracer
	r.collectDescendants(tracerID, &descendants)
	return descendants
}

func (r *Registry) collectDescendants(tracerID string, descendants *[]*tracer.UniversalTracer) {
	t := r.tracers[tracerID]
	if t == nil {
		return
	}

	for _, childID := range t.ChildrenIDs {
		child := r.tracers[childID]
		if child != nil {
			*descendants = append(*descendants, child)
			r.collectDescendants(childID, descendants)
		}
	}
}

func (r *Registry) getMultiple(ids []string) []*tracer.UniversalTracer {
	result := make([]*tracer.UniversalTracer, 0, len(ids))
	for _, id := range ids {
		if t := r.tracers[id]; t != nil {
			result = append(result, t)
		}
	}
	return result
}

// RegisterIdentity registers a fairy identity for name resolution.
func (r *Registry) RegisterIdentity(id *tracer.Identity) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.identities[id.FunctionName] = id

	// Also register by real name and aliases
	if id.RealName != "" {
		r.identities[id.RealName] = id
	}
	for _, alias := range id.Aliases {
		r.identities[alias] = id
	}
}

// ResolveIdentity looks up an identity by any name.
func (r *Registry) ResolveIdentity(name string) *tracer.Identity {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.identities[name]
}

// UpdateStatus updates a tracer's status and re-indexes.
func (r *Registry) UpdateStatus(tracerID string, status tracer.TracerStatus) {
	r.mu.Lock()
	defer r.mu.Unlock()

	t := r.tracers[tracerID]
	if t == nil {
		return
	}

	// Remove from old status index
	oldStatus := t.Status
	r.removeFromIndex(r.byStatus[oldStatus], tracerID)

	// Update status
	t.Status = status

	// Add to new status index
	r.byStatus[status] = append(r.byStatus[status], tracerID)
}

func (r *Registry) removeFromIndex(slice []string, id string) []string {
	for i, v := range slice {
		if v == id {
			return append(slice[:i], slice[i+1:]...)
		}
	}
	return slice
}

// Stats returns registry statistics.
func (r *Registry) Stats() map[string]interface{} {
	r.mu.RLock()
	defer r.mu.RUnlock()

	statusCounts := make(map[string]int)
	for status, ids := range r.byStatus {
		statusCounts[string(status)] = len(ids)
	}

	return map[string]interface{}{
		"total_tracers":   len(r.tracers),
		"total_fairies":   len(r.byFairy),
		"total_clusters":  len(r.byCluster),
		"total_chains":    len(r.byChain),
		"total_goals":     len(r.byGoal),
		"total_identities": len(r.identities),
		"by_status":       statusCounts,
	}
}

// Save persists the registry to disk.
func (r *Registry) Save() error {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if r.persistPath == "" {
		return nil
	}

	// Ensure directory exists
	dir := filepath.Dir(r.persistPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(r.tracers, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(r.persistPath, data, 0644)
}

// Load restores the registry from disk.
func (r *Registry) Load() error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.persistPath == "" {
		return nil
	}

	data, err := os.ReadFile(r.persistPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // No saved state, that's fine
		}
		return err
	}

	var tracers map[string]*tracer.UniversalTracer
	if err := json.Unmarshal(data, &tracers); err != nil {
		return err
	}

	// Re-register each tracer to rebuild indexes
	for _, t := range tracers {
		r.tracers[t.ID] = t
		r.indexTracer(t)
	}

	return nil
}

func (r *Registry) indexTracer(t *tracer.UniversalTracer) {
	if t.FairyID != "" {
		r.byFairy[t.FairyID] = append(r.byFairy[t.FairyID], t.ID)
	}
	if t.FairyName != "" {
		r.byFairyName[t.FairyName] = append(r.byFairyName[t.FairyName], t.ID)
	}
	if t.ClusterID != "" {
		r.byCluster[t.ClusterID] = append(r.byCluster[t.ClusterID], t.ID)
	}
	if t.ChainID != "" {
		r.byChain[t.ChainID] = append(r.byChain[t.ChainID], t.ID)
	}
	if t.GoalID != "" {
		r.byGoal[t.GoalID] = append(r.byGoal[t.GoalID], t.ID)
	}
	for _, tag := range t.Tags {
		r.byTag[tag] = append(r.byTag[tag], t.ID)
	}
	r.byStatus[t.Status] = append(r.byStatus[t.Status], t.ID)
}

// Clear removes all tracers (for testing).
func (r *Registry) Clear() {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.tracers = make(map[string]*tracer.UniversalTracer)
	r.byFairy = make(map[string][]string)
	r.byFairyName = make(map[string][]string)
	r.byCluster = make(map[string][]string)
	r.byChain = make(map[string][]string)
	r.byGoal = make(map[string][]string)
	r.byTag = make(map[string][]string)
	r.byStatus = make(map[tracer.TracerStatus][]string)
}
