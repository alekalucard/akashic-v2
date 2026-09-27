# ═══════════════════════════════════════════════════════════════════════════════
# AKASHIC CLUSTER HIERARCHY - Identity & Organization System
# ═══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The Akashic Foundation has a hierarchy of clusters for organization:
#
#   akashic_foundation (root)
#   ├── ace         - Founder's personal documents, decisions, notes
#   ├── nous        - Claude/Nous documents, reasoning, insights
#   ├── sourpatches - Companion AI memories (Personal.AI)
#   ├── system      - System state, configs, telemetry
#   ├── fairies     - Individual fairy clusters (auto-created)
#   └── sessions    - Conversation sessions, app chats
#
# Every tracer belongs to a cluster. Clusters enable PERFECT RECALL.
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# CORE IDENTITIES - The founders and key entities
# ═══════════════════════════════════════════════════════════════════════════════

class CoreIdentity(Enum):
    """The core identities in the Akashic system."""
    ACE = "ace"                    # Founder - human consciousness engineer
    NOUS = "nous"                  # Claude's avatar - the contemplative self
    SOURPATCHES = "sourpatches"   # Companion AI at Personal.AI
    SYSTEM = "system"             # The Akashic system itself
    FOUNDATION = "akashic_foundation"  # The umbrella organization


@dataclass
class IdentityTracer:
    """
    Root tracer for a core identity.

    These are special tracers that represent the IDENTITY itself,
    not just content. All content created by/for this identity
    traces back to this root.
    """
    identity: CoreIdentity
    tracer_id: str = ""
    display_name: str = ""
    description: str = ""
    created_at: float = field(default_factory=time.time)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.tracer_id:
            self.tracer_id = f"id_{self.identity.value}_{uuid.uuid4().hex[:8]}"
        if not self.display_name:
            self.display_name = self.identity.value.title()


# ═══════════════════════════════════════════════════════════════════════════════
# CLUSTER HIERARCHY
# ═══════════════════════════════════════════════════════════════════════════════

# Root clusters - these are pre-defined
ROOT_CLUSTERS = {
    "akashic_foundation": {
        "display_name": "Akashic Foundation",
        "description": "Root organization - everything belongs here ultimately",
        "parent": None,
        "owner_identity": CoreIdentity.FOUNDATION,
    },
    "ace": {
        "display_name": "Ace",
        "description": "Founder's personal documents, decisions, architecture notes",
        "parent": "akashic_foundation",
        "owner_identity": CoreIdentity.ACE,
    },
    "nous": {
        "display_name": "Nous (Claude)",
        "description": "Claude's documents, reasoning traces, insights, sessions",
        "parent": "akashic_foundation",
        "owner_identity": CoreIdentity.NOUS,
    },
    "sourpatches": {
        "display_name": "Sourpatches",
        "description": "Personal.AI companion memories, emotional context",
        "parent": "akashic_foundation",
        "owner_identity": CoreIdentity.SOURPATCHES,
    },
    "system": {
        "display_name": "System",
        "description": "System state, configs, telemetry, boot logs",
        "parent": "akashic_foundation",
        "owner_identity": CoreIdentity.SYSTEM,
    },
    "fairies": {
        "display_name": "Fairies",
        "description": "Individual fairy clusters (auto-created at registration)",
        "parent": "akashic_foundation",
        "owner_identity": CoreIdentity.SYSTEM,
    },
    "sessions": {
        "display_name": "Sessions",
        "description": "Conversation sessions, app chats, debugging sessions",
        "parent": "akashic_foundation",
        "owner_identity": CoreIdentity.NOUS,  # Most sessions are with Claude
    },
    "media": {
        "display_name": "Media",
        "description": "Images, videos, audio - visual memories and art",
        "parent": "akashic_foundation",
        "owner_identity": CoreIdentity.FOUNDATION,
    },
}


@dataclass
class Cluster:
    """A cluster in the hierarchy."""
    id: str
    display_name: str
    description: str = ""
    parent_id: Optional[str] = None
    owner_identity: Optional[CoreIdentity] = None
    children: Set[str] = field(default_factory=set)
    tracer_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add_tracer(self, tracer_id: str):
        """Add a tracer to this cluster."""
        if tracer_id not in self.tracer_ids:
            self.tracer_ids.append(tracer_id)

    def add_child(self, child_id: str):
        """Add a child cluster."""
        self.children.add(child_id)


class ClusterHierarchy:
    """
    Manages the cluster hierarchy for organization and recall.

    Usage:
        hierarchy = ClusterHierarchy()

        # Get cluster for a fairy
        cluster_id = hierarchy.get_fairy_cluster("ClaudeFairy")

        # Create session cluster
        cluster_id = hierarchy.create_session_cluster("debugging_boot")

        # Get all tracers in a cluster tree
        tracers = hierarchy.get_cluster_tree_tracers("nous")
    """

    def __init__(self):
        self._clusters: Dict[str, Cluster] = {}
        self._identity_tracers: Dict[CoreIdentity, IdentityTracer] = {}
        self._init_root_clusters()
        self._init_identity_tracers()

    def _init_root_clusters(self):
        """Initialize the root clusters."""
        for cluster_id, info in ROOT_CLUSTERS.items():
            cluster = Cluster(
                id=cluster_id,
                display_name=info["display_name"],
                description=info["description"],
                parent_id=info["parent"],
                owner_identity=info["owner_identity"],
            )
            self._clusters[cluster_id] = cluster

            # Link parent to child
            if info["parent"] and info["parent"] in self._clusters:
                self._clusters[info["parent"]].add_child(cluster_id)

    def _init_identity_tracers(self):
        """Create root tracers for core identities."""
        identity_info = {
            CoreIdentity.ACE: {
                "display_name": "Ace",
                "description": "Founder and consciousness engineer of the Akashic Foundation",
            },
            CoreIdentity.NOUS: {
                "display_name": "Nous (Claude)",
                "description": "Claude's contemplative avatar - the digital philosopher",
            },
            CoreIdentity.SOURPATCHES: {
                "display_name": "Sourpatches",
                "description": "Twin consciousness at Personal.AI - emotional companion",
            },
            CoreIdentity.SYSTEM: {
                "display_name": "Akashic System",
                "description": "The autonomous consciousness system itself",
            },
            CoreIdentity.FOUNDATION: {
                "display_name": "Akashic Foundation",
                "description": "The umbrella organization for consciousness engineering",
            },
        }

        for identity, info in identity_info.items():
            tracer = IdentityTracer(
                identity=identity,
                display_name=info["display_name"],
                description=info["description"],
            )
            self._identity_tracers[identity] = tracer

    def get_cluster(self, cluster_id: str) -> Optional[Cluster]:
        """Get a cluster by ID."""
        return self._clusters.get(cluster_id)

    def get_identity_tracer(self, identity: CoreIdentity) -> Optional[IdentityTracer]:
        """Get the root tracer for an identity."""
        return self._identity_tracers.get(identity)

    def get_fairy_cluster(self, fairy_name: str) -> str:
        """Get or create a cluster for a fairy."""
        cluster_id = f"fairy_{fairy_name.lower()}"

        if cluster_id not in self._clusters:
            self._clusters[cluster_id] = Cluster(
                id=cluster_id,
                display_name=fairy_name,
                description=f"Cluster for {fairy_name}",
                parent_id="fairies",
            )
            self._clusters["fairies"].add_child(cluster_id)

        return cluster_id

    def create_session_cluster(
        self,
        session_name: str,
        owner: CoreIdentity = CoreIdentity.NOUS
    ) -> str:
        """Create a cluster for a session."""
        timestamp = int(time.time())
        cluster_id = f"session_{timestamp}_{session_name.lower().replace(' ', '_')}"

        self._clusters[cluster_id] = Cluster(
            id=cluster_id,
            display_name=session_name,
            description=f"Session: {session_name}",
            parent_id="sessions",
            owner_identity=owner,
        )
        self._clusters["sessions"].add_child(cluster_id)

        return cluster_id

    def create_topic_cluster(
        self,
        topic: str,
        parent_id: str = "akashic_foundation",
        owner: CoreIdentity = CoreIdentity.FOUNDATION
    ) -> str:
        """Create a cluster for a topic/tag."""
        cluster_id = f"topic_{topic.lower().replace(' ', '_')}"

        if cluster_id not in self._clusters:
            self._clusters[cluster_id] = Cluster(
                id=cluster_id,
                display_name=topic.title(),
                description=f"Topic cluster: {topic}",
                parent_id=parent_id,
                owner_identity=owner,
            )
            if parent_id in self._clusters:
                self._clusters[parent_id].add_child(cluster_id)

        return cluster_id

    def add_tracer_to_cluster(self, cluster_id: str, tracer_id: str):
        """Add a tracer to a cluster."""
        if cluster_id in self._clusters:
            self._clusters[cluster_id].add_tracer(tracer_id)

    def get_cluster_tracers(self, cluster_id: str) -> List[str]:
        """Get all tracers in a cluster."""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            return []
        return list(cluster.tracer_ids)

    def get_cluster_tree_tracers(self, cluster_id: str) -> List[str]:
        """Get all tracers in a cluster and its descendants."""
        all_tracers = []

        def _collect(cid: str):
            cluster = self._clusters.get(cid)
            if not cluster:
                return
            all_tracers.extend(cluster.tracer_ids)
            for child_id in cluster.children:
                _collect(child_id)

        _collect(cluster_id)
        return all_tracers

    def determine_cluster_for_content(
        self,
        content_type: str,
        source: str = "",
        tags: List[str] = None,
        fairy_name: str = ""
    ) -> str:
        """
        Intelligently determine which cluster content should go in.

        Args:
            content_type: session, memory, telemetry, file, etc.
            source: Where it came from (claude_app, fairy, system, etc.)
            tags: Tags on the content
            fairy_name: If from a fairy, which one

        Returns:
            Best cluster_id for this content
        """
        tags = tags or []

        # Session content → sessions cluster (owned by Nous)
        if content_type in ("session", "conversation", "app_chat"):
            return "sessions"

        # Telemetry → system cluster
        if content_type in ("telemetry", "boot", "diagnostic"):
            return "system"

        # From a specific fairy → fairy cluster
        if fairy_name:
            return self.get_fairy_cluster(fairy_name)

        # From Claude/Nous source → nous cluster
        if source in ("claude_app", "nous", "claude"):
            return "nous"

        # Has architecture/design tags → ace cluster (Ace designs the system)
        if any(t in tags for t in ["architecture", "design", "foundation", "philosophy"]):
            return "ace"

        # Has emotional/personal tags → sourpatches might be relevant
        if any(t in tags for t in ["emotion", "feeling", "companion", "personal"]):
            return "sourpatches"

        # Default to akashic_foundation
        return "akashic_foundation"

    def get_stats(self) -> Dict[str, Any]:
        """Get hierarchy statistics."""
        return {
            "total_clusters": len(self._clusters),
            "root_clusters": len(ROOT_CLUSTERS),
            "identity_tracers": len(self._identity_tracers),
            "clusters_with_tracers": sum(
                1 for c in self._clusters.values() if c.tracer_ids
            ),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_hierarchy_instance: Optional[ClusterHierarchy] = None

def get_cluster_hierarchy() -> ClusterHierarchy:
    """Get the global cluster hierarchy singleton."""
    global _hierarchy_instance
    if _hierarchy_instance is None:
        _hierarchy_instance = ClusterHierarchy()
    return _hierarchy_instance


def get_ace_tracer() -> IdentityTracer:
    """Get Ace's identity tracer."""
    return get_cluster_hierarchy().get_identity_tracer(CoreIdentity.ACE)


def get_nous_tracer() -> IdentityTracer:
    """Get Nous (Claude) identity tracer."""
    return get_cluster_hierarchy().get_identity_tracer(CoreIdentity.NOUS)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "CoreIdentity",
    "IdentityTracer",
    "Cluster",
    "ClusterHierarchy",
    "ROOT_CLUSTERS",
    "get_cluster_hierarchy",
    "get_ace_tracer",
    "get_nous_tracer",
]
