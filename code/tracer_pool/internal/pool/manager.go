// Package pool - PoolManager for per-fairy worker pools.
package pool

import (
	"context"
	"sync"

	"akashic/tracer_pool/internal/registry"
	"akashic/tracer_pool/internal/tracer"
)

// PoolManager manages per-fairy worker pools.
type PoolManager struct {
	mu sync.RWMutex

	// Per-fairy pools
	pools map[string]*Pool

	// Default config template
	defaultConfig *PoolConfig

	// Shared registry
	registry *registry.Registry

	// Global pool for unaffiliated work
	globalPool *Pool
}

// Global singleton
var (
	globalManager *PoolManager
	managerOnce   sync.Once
)

// GlobalManager returns the global pool manager.
func GlobalManager() *PoolManager {
	managerOnce.Do(func() {
		globalManager = NewPoolManager()
	})
	return globalManager
}

// NewPoolManager creates a new pool manager.
func NewPoolManager() *PoolManager {
	m := &PoolManager{
		pools:         make(map[string]*Pool),
		defaultConfig: DefaultConfig("global"),
		registry:      registry.GlobalRegistry(),
	}

	// Create global pool for unaffiliated work
	m.globalPool = NewPool(DefaultConfig("_global_"))
	m.globalPool.WithRegistry(m.registry)
	m.globalPool.Start()

	return m
}

// SetDefaultConfig sets the default config for new pools.
func (m *PoolManager) SetDefaultConfig(config *PoolConfig) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.defaultConfig = config
}

// GetOrCreatePool gets or creates a pool for a fairy.
func (m *PoolManager) GetOrCreatePool(fairyName string) *Pool {
	m.mu.RLock()
	pool := m.pools[fairyName]
	m.mu.RUnlock()

	if pool != nil {
		return pool
	}

	// Create new pool
	m.mu.Lock()
	defer m.mu.Unlock()

	// Double-check after acquiring write lock
	if pool = m.pools[fairyName]; pool != nil {
		return pool
	}

	// Create config from template
	config := *m.defaultConfig
	config.Name = fairyName

	pool = NewPool(&config)
	pool.WithRegistry(m.registry)
	pool.Start()

	m.pools[fairyName] = pool
	return pool
}

// GetOrCreatePoolWithIdentity creates a pool with full identity support.
func (m *PoolManager) GetOrCreatePoolWithIdentity(id *tracer.Identity) *Pool {
	pool := m.GetOrCreatePool(id.FunctionName)
	pool.WithIdentity(id)

	// Register identity
	m.registry.RegisterIdentity(id)

	return pool
}

// GetPool gets an existing pool by fairy name (no create).
func (m *PoolManager) GetPool(fairyName string) *Pool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.pools[fairyName]
}

// GlobalPool returns the global pool for unaffiliated work.
func (m *PoolManager) GlobalPool() *Pool {
	return m.globalPool
}

// Submit submits work to a specific fairy's pool.
func (m *PoolManager) Submit(fairyName string, priority Priority, work func() error) error {
	pool := m.GetOrCreatePool(fairyName)
	return pool.SubmitFunc(priority, func(_ context.Context) error {
		return work()
	})
}

// SubmitGlobal submits work to the global pool.
func (m *PoolManager) SubmitGlobal(priority Priority, work func() error) error {
	return m.globalPool.SubmitFunc(priority, func(_ context.Context) error {
		return work()
	})
}

// Shutdown stops all pools.
func (m *PoolManager) Shutdown() {
	m.mu.Lock()
	defer m.mu.Unlock()

	for _, pool := range m.pools {
		pool.Stop()
	}
	m.globalPool.Stop()
	m.pools = make(map[string]*Pool)
}

// Stats returns stats for all pools.
func (m *PoolManager) Stats() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()

	poolStats := make(map[string]interface{})
	for name, pool := range m.pools {
		poolStats[name] = pool.Metrics()
	}

	return map[string]interface{}{
		"pool_count":   len(m.pools),
		"global_pool":  m.globalPool.Metrics(),
		"fairy_pools":  poolStats,
		"registry":     m.registry.Stats(),
	}
}

// Pools returns list of pool names.
func (m *PoolManager) Pools() []string {
	m.mu.RLock()
	defer m.mu.RUnlock()

	names := make([]string, 0, len(m.pools))
	for name := range m.pools {
		names = append(names, name)
	}
	return names
}
