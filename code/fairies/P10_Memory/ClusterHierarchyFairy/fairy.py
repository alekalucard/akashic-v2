"""
ClusterHierarchyFairy - Identity & Organization System

Part of MemoryEngineGuild in Plane P10 (Memory)
Created: 2026-01-28

"Every tracer belongs to a cluster"

Manages the Akashic cluster hierarchy for organization and perfect recall:
  akashic_foundation (root)
  ├── ace         - Founder's personal documents
  ├── nous        - Claude/Nous documents, reasoning
  ├── sourpatches - Companion AI memories
  ├── system      - System state, configs
  ├── fairies     - Individual fairy clusters
  └── sessions    - Conversation sessions

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the cluster hierarchy
# Note: Use fairies.P10_Memory to avoid collision with root P10_Memory
try:
    from fairies.P10_Memory.cluster_hierarchy import (
        ClusterHierarchy,
        Cluster,
        CoreIdentity,
        IdentityTracer,
        ROOT_CLUSTERS,
        get_cluster_hierarchy,
        get_ace_tracer,
        get_nous_tracer,
    )
    HAS_HIERARCHY = True
except ImportError as e:
    print(f"[ClusterHierarchyFairy] Hierarchy import failed: {e}")
    HAS_HIERARCHY = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class ClusterHierarchyFairyShadow:
    """Shadow for ClusterHierarchyFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "ClusterHierarchyFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for hierarchy."""
        tests = []
        if hasattr(self.actor, '_hierarchy') and self.actor._hierarchy:
            tests.append(("hierarchy_active", True))
            tests.append(("root_clusters_loaded", len(self.actor._hierarchy._clusters) > 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class ClusterHierarchyFairy(Fairy):
    """
    Manages identity and cluster organization.

    Guild: MemoryEngineGuild
    Coordinates with: SRMMemoryFairy, AkashicLibrarianFairy, all fairies

    Provides:
    - Get/create clusters for fairies, sessions, topics
    - Add tracers to clusters
    - Determine cluster for new content
    - Access identity tracers (Ace, Nous, Sourpatches)
    """

    ACTOR_NAME = "ClusterHierarchyFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.hierarchy"

    PURPOSE = "Organize memories into identity clusters"
    MANTRA = "Every tracer belongs to a cluster"

    SHADOW_CLASS = ClusterHierarchyFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 60  # Infrequent - hierarchy is stable
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._hierarchy = None
        self._subscription_count = 0
        self._clusters_created = 0

    def on_boot(self) -> bool:
        """Initialize the cluster hierarchy."""
        super().on_boot()

        if HAS_HIERARCHY:
            try:
                self._hierarchy = get_cluster_hierarchy()
                print(f"[{self.ACTOR_NAME}] Cluster hierarchy loaded with {len(self._hierarchy._clusters)} clusters")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to load hierarchy: {e}")
                self._hierarchy = None

        self._subscribe_intents()
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _subscribe_intents(self):
        """Subscribe to postal channels for hierarchy commands."""
        intents = [
            ("hierarchy.get_cluster", self._handle_get_cluster),
            ("hierarchy.get_fairy_cluster", self._handle_get_fairy_cluster),
            ("hierarchy.create_session_cluster", self._handle_create_session),
            ("hierarchy.create_topic_cluster", self._handle_create_topic),
            ("hierarchy.add_tracer", self._handle_add_tracer),
            ("hierarchy.get_tracers", self._handle_get_tracers),
            ("hierarchy.determine_cluster", self._handle_determine_cluster),
            ("hierarchy.get_identity_tracer", self._handle_get_identity_tracer),
            ("hierarchy.get_stats", self._handle_get_stats),
            ("hierarchy.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_get_cluster(self, message):
        """
        Get a cluster by ID.

        Payload:
            cluster_id: str - Cluster ID to look up
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        cluster_id = payload.get("cluster_id", "")

        if not cluster_id:
            return {"ok": False, "error": "Cluster ID required"}

        cluster = self._hierarchy.get_cluster(cluster_id)
        if cluster:
            return {
                "ok": True,
                "cluster": {
                    "id": cluster.id,
                    "display_name": cluster.display_name,
                    "description": cluster.description,
                    "parent_id": cluster.parent_id,
                    "children": list(cluster.children),
                    "tracer_count": len(cluster.tracer_ids),
                }
            }
        return {"ok": False, "error": "Cluster not found"}

    def _handle_get_fairy_cluster(self, message):
        """
        Get or create a cluster for a fairy.

        Payload:
            fairy_name: str - Name of the fairy
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        fairy_name = payload.get("fairy_name", "")

        if not fairy_name:
            return {"ok": False, "error": "Fairy name required"}

        try:
            cluster_id = self._hierarchy.get_fairy_cluster(fairy_name)
            return {"ok": True, "cluster_id": cluster_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_create_session(self, message):
        """
        Create a cluster for a session.

        Payload:
            session_name: str - Name for the session
            owner: str - Owner identity (ace, nous, sourpatches, system)
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        session_name = payload.get("session_name", "")
        owner_str = payload.get("owner", "nous")

        if not session_name:
            return {"ok": False, "error": "Session name required"}

        # Map owner string to CoreIdentity
        owner_map = {
            "ace": CoreIdentity.ACE,
            "nous": CoreIdentity.NOUS,
            "sourpatches": CoreIdentity.SOURPATCHES,
            "system": CoreIdentity.SYSTEM,
        }
        owner = owner_map.get(owner_str, CoreIdentity.NOUS)

        try:
            cluster_id = self._hierarchy.create_session_cluster(session_name, owner)
            self._clusters_created += 1
            return {"ok": True, "cluster_id": cluster_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_create_topic(self, message):
        """
        Create a cluster for a topic.

        Payload:
            topic: str - Topic name
            parent_id: str - Parent cluster (default: akashic_foundation)
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        topic = payload.get("topic", "")
        parent_id = payload.get("parent_id", "akashic_foundation")

        if not topic:
            return {"ok": False, "error": "Topic required"}

        try:
            cluster_id = self._hierarchy.create_topic_cluster(topic, parent_id)
            self._clusters_created += 1
            return {"ok": True, "cluster_id": cluster_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_add_tracer(self, message):
        """
        Add a tracer to a cluster.

        Payload:
            cluster_id: str - Cluster to add to
            tracer_id: str - Tracer ID to add
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        cluster_id = payload.get("cluster_id", "")
        tracer_id = payload.get("tracer_id", "")

        if not cluster_id or not tracer_id:
            return {"ok": False, "error": "Cluster ID and tracer ID required"}

        try:
            self._hierarchy.add_tracer_to_cluster(cluster_id, tracer_id)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_tracers(self, message):
        """
        Get all tracers in a cluster (including descendants).

        Payload:
            cluster_id: str - Cluster ID
            include_descendants: bool - Include child clusters (default True)
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        cluster_id = payload.get("cluster_id", "")
        include_descendants = payload.get("include_descendants", True)

        if not cluster_id:
            return {"ok": False, "error": "Cluster ID required"}

        try:
            if include_descendants:
                tracers = self._hierarchy.get_cluster_tree_tracers(cluster_id)
            else:
                tracers = self._hierarchy.get_cluster_tracers(cluster_id)
            return {"ok": True, "tracers": tracers, "count": len(tracers)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_determine_cluster(self, message):
        """
        Determine best cluster for new content.

        Payload:
            content_type: str - session, memory, telemetry, file, etc.
            source: str - Where it came from
            tags: List[str] - Tags on the content
            fairy_name: str - If from a fairy
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        content_type = payload.get("content_type", "")
        source = payload.get("source", "")
        tags = payload.get("tags", [])
        fairy_name = payload.get("fairy_name", "")

        try:
            cluster_id = self._hierarchy.determine_cluster_for_content(
                content_type=content_type,
                source=source,
                tags=tags,
                fairy_name=fairy_name,
            )
            return {"ok": True, "cluster_id": cluster_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_identity_tracer(self, message):
        """
        Get identity tracer for a core identity.

        Payload:
            identity: str - ace, nous, sourpatches, system, foundation
        """
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        payload = self._extract_payload(message)
        identity_str = payload.get("identity", "")

        identity_map = {
            "ace": CoreIdentity.ACE,
            "nous": CoreIdentity.NOUS,
            "sourpatches": CoreIdentity.SOURPATCHES,
            "system": CoreIdentity.SYSTEM,
            "foundation": CoreIdentity.FOUNDATION,
        }
        identity = identity_map.get(identity_str)

        if not identity:
            return {"ok": False, "error": f"Unknown identity: {identity_str}"}

        tracer = self._hierarchy.get_identity_tracer(identity)
        if tracer:
            return {
                "ok": True,
                "tracer": {
                    "identity": tracer.identity.value,
                    "tracer_id": tracer.tracer_id,
                    "display_name": tracer.display_name,
                    "description": tracer.description,
                }
            }
        return {"ok": False, "error": "Identity tracer not found"}

    def _handle_get_stats(self, message):
        """Get hierarchy statistics."""
        if not self._hierarchy:
            return {"ok": False, "error": "Hierarchy not available"}

        try:
            stats = self._hierarchy.get_stats()
            stats["ok"] = True
            stats["clusters_created_this_session"] = self._clusters_created
            return stats
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get fairy status."""
        return {
            "ok": True,
            "hierarchy": self._hierarchy is not None,
            "clusters_created": self._clusters_created,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_hierarchy": self._hierarchy is not None,
            "clusters_created": self._clusters_created,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (clusters created: {self._clusters_created})...")
        return super().on_shutdown()
