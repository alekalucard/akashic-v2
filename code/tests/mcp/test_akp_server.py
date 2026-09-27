# tests/mcp/test_akp_server.py
"""
TDD Tests for AKP Server SessionManager - Pattern: EXTERNAL MIND MANAGEMENT

These tests define the expected behavior of the SessionManager system:
- Sessions should be created for external minds connecting via WebSocket
- Sessions should track topic subscriptions with proper cleanup
- Permission checking should validate publish/subscribe rights
- Wildcard pattern matching should work for subscriptions (consciousness.*)
- Session destruction should clean up all resources

((Cause + Affect) > Effect > Affect > infinity)
  Connect  Trust   Interact Ripple  Memory

Run: pytest tests/mcp/test_akp_server.py -v
Expected: FAIL initially (TDD - SessionManager not yet implemented)
"""
import pytest
import sys
import time
from pathlib import Path
from typing import Set

# Add project root and postal_core/python to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))


class TestSessionManagerCreatesSession:
    """
    Test: Session manager should create sessions for external minds.

    The SessionManager is responsible for tracking connected external minds,
    their permissions, subscriptions, and lifecycle. When an external mind
    connects via WebSocket, a session should be created.
    """

    def test_create_session_returns_session_id(self):
        """
        Creating a session should return a unique session ID.

        When an external mind connects, it needs a session ID to:
        - Track its subscriptions
        - Validate its permissions
        - Clean up on disconnect
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="TestExternalMind",
            capabilities={"subscribe", "publish"},
            metadata={"client_type": "test"}
        )

        # Session ID should be returned
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_create_session_stores_session_data(self):
        """
        Created session should be retrievable with its data.

        After creating a session, we should be able to:
        - Retrieve it by session_id
        - Access its fairy_name, capabilities, metadata
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="DataMind",
            capabilities={"subscribe"},
            metadata={"version": "1.0"}
        )

        # Session should be retrievable
        session = manager.get_session(session_id)
        assert session is not None
        assert session.fairy_name == "DataMind"
        assert "subscribe" in session.capabilities
        assert session.metadata.get("version") == "1.0"

    def test_create_multiple_sessions_unique_ids(self):
        """
        Multiple sessions should have unique IDs.

        When multiple external minds connect, each gets a unique session ID.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        id1 = manager.create_session(fairy_name="Mind1")
        id2 = manager.create_session(fairy_name="Mind2")
        id3 = manager.create_session(fairy_name="Mind3")

        # All IDs should be unique
        assert len({id1, id2, id3}) == 3

    def test_session_tracks_creation_time(self):
        """
        Sessions should track when they were created.

        This is needed for:
        - Session expiration
        - Analytics/monitoring
        - Debugging connection issues
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        before = time.time()
        session_id = manager.create_session(fairy_name="TimeMind")
        after = time.time()

        session = manager.get_session(session_id)

        assert session.created_at >= before
        assert session.created_at <= after


class TestSessionManagerTracksSubscriptions:
    """
    Test: Sessions should track topic subscriptions.

    When an external mind subscribes to topics (e.g., "consciousness.collision"),
    the session should track these subscriptions for:
    - Message routing
    - Cleanup on disconnect
    - Permission validation
    """

    def test_add_subscription_to_session(self):
        """
        Should be able to add subscriptions to a session.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()
        session_id = manager.create_session(fairy_name="SubMind")

        # Add a subscription
        result = manager.add_subscription(session_id, "consciousness.collision")

        assert result is True

        # Verify subscription is tracked
        session = manager.get_session(session_id)
        assert "consciousness.collision" in session.subscriptions

    def test_list_session_subscriptions(self):
        """
        Should be able to list all subscriptions for a session.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()
        session_id = manager.create_session(fairy_name="ListMind")

        manager.add_subscription(session_id, "consciousness.collision")
        manager.add_subscription(session_id, "chemistry.signal")
        manager.add_subscription(session_id, "postal.heartbeat")

        subscriptions = manager.list_subscriptions(session_id)

        assert len(subscriptions) == 3
        assert "consciousness.collision" in subscriptions
        assert "chemistry.signal" in subscriptions
        assert "postal.heartbeat" in subscriptions

    def test_remove_subscription_from_session(self):
        """
        Should be able to remove subscriptions from a session.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()
        session_id = manager.create_session(fairy_name="RemoveMind")

        manager.add_subscription(session_id, "topic.a")
        manager.add_subscription(session_id, "topic.b")

        # Remove one subscription
        result = manager.remove_subscription(session_id, "topic.a")

        assert result is True

        subscriptions = manager.list_subscriptions(session_id)
        assert "topic.a" not in subscriptions
        assert "topic.b" in subscriptions

    def test_subscription_tracks_subscription_id(self):
        """
        Each subscription should have an associated subscription ID.

        This ID is needed for unsubscribing from the postal system.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()
        session_id = manager.create_session(fairy_name="TrackMind")

        sub_id = manager.add_subscription(
            session_id,
            "consciousness.collision",
            subscription_id=42  # The postal system's internal ID
        )

        session = manager.get_session(session_id)

        # Should track both topic -> sub_id mapping
        assert session.get_subscription_id("consciousness.collision") == 42


class TestPermissionChecking:
    """
    Test: Should validate permissions for publish/subscribe.

    External minds have different permission levels:
    - Some can only subscribe (read-only)
    - Some can publish to specific topics
    - Some have full access

    Permission checking protects the system from unauthorized actions.
    """

    def test_session_without_publish_cannot_publish(self):
        """
        Sessions without 'publish' capability should be denied publish.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        # Create session with only subscribe capability
        session_id = manager.create_session(
            fairy_name="ReadOnlyMind",
            capabilities={"subscribe"}  # No 'publish' capability
        )

        # Should not be allowed to publish
        can_publish = manager.can_publish(session_id, "any.topic")
        assert can_publish is False

    def test_session_with_publish_can_publish(self):
        """
        Sessions with 'publish' capability should be allowed to publish.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="WriteMind",
            capabilities={"subscribe", "publish"}
        )

        can_publish = manager.can_publish(session_id, "any.topic")
        assert can_publish is True

    def test_session_without_subscribe_cannot_subscribe(self):
        """
        Sessions without 'subscribe' capability should be denied subscription.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        # Create session with only publish capability
        session_id = manager.create_session(
            fairy_name="WriteOnlyMind",
            capabilities={"publish"}  # No 'subscribe' capability
        )

        can_subscribe = manager.can_subscribe(session_id, "any.topic")
        assert can_subscribe is False

    def test_topic_specific_permissions(self):
        """
        Permissions can be restricted to specific topic patterns.

        An external mind might only be allowed to publish to its own namespace.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        # Create session with topic-specific publish permission
        session_id = manager.create_session(
            fairy_name="NamespacedMind",
            capabilities={"subscribe", "publish"},
            allowed_topics={"external.namespaced.*"}  # Can only publish to this pattern
        )

        # Should be allowed to publish to matching topic
        assert manager.can_publish(session_id, "external.namespaced.data") is True

        # Should NOT be allowed to publish to non-matching topic
        assert manager.can_publish(session_id, "consciousness.collision") is False

    def test_invalid_session_denied_all_permissions(self):
        """
        Non-existent sessions should be denied all permissions.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        fake_session_id = "nonexistent-session-12345"

        assert manager.can_publish(fake_session_id, "any.topic") is False
        assert manager.can_subscribe(fake_session_id, "any.topic") is False


class TestCanSubscribePatternMatching:
    """
    Test: Should match wildcard patterns (consciousness.*).

    Topics use hierarchical naming with wildcard support:
    - "consciousness.*" matches "consciousness.collision", "consciousness.stream"
    - "fairy.wake.P10.*" matches any P10 fairy wake events
    - "#" can match multiple levels (MQTT-style)

    This allows flexible subscription patterns.
    """

    def test_star_matches_single_level(self):
        """
        Single asterisk (*) should match one level of hierarchy.

        "consciousness.*" should match:
        - "consciousness.collision" -> YES
        - "consciousness.stream" -> YES
        - "consciousness.collision.high" -> NO (too deep)
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="WildcardMind",
            capabilities={"subscribe"},
            allowed_topics={"consciousness.*"}
        )

        # Should match single level
        assert manager.can_subscribe(session_id, "consciousness.collision") is True
        assert manager.can_subscribe(session_id, "consciousness.stream") is True

        # Should NOT match deeper levels
        assert manager.can_subscribe(session_id, "consciousness.collision.high") is False

        # Should NOT match different prefix
        assert manager.can_subscribe(session_id, "chemistry.signal") is False

    def test_hash_matches_multiple_levels(self):
        """
        Hash (#) should match multiple levels of hierarchy.

        "fairy.#" should match:
        - "fairy.wake" -> YES
        - "fairy.wake.P10.MemoryFairy" -> YES
        - "fairy.death.P30.AttentionFairy" -> YES
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="DeepMind",
            capabilities={"subscribe"},
            allowed_topics={"fairy.#"}
        )

        # Should match any depth under fairy.
        assert manager.can_subscribe(session_id, "fairy.wake") is True
        assert manager.can_subscribe(session_id, "fairy.wake.P10.MemoryFairy") is True
        assert manager.can_subscribe(session_id, "fairy.death.P30.AttentionFairy") is True

        # Should NOT match outside prefix
        assert manager.can_subscribe(session_id, "consciousness.stream") is False

    def test_exact_match_without_wildcards(self):
        """
        Topics without wildcards should match exactly.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="ExactMind",
            capabilities={"subscribe"},
            allowed_topics={"consciousness.collision"}  # Exact topic
        )

        # Should match exact topic
        assert manager.can_subscribe(session_id, "consciousness.collision") is True

        # Should NOT match variations
        assert manager.can_subscribe(session_id, "consciousness.collision.high") is False
        assert manager.can_subscribe(session_id, "consciousness.stream") is False

    def test_multiple_patterns_any_match(self):
        """
        Multiple allowed patterns - any match should succeed.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="MultiMind",
            capabilities={"subscribe"},
            allowed_topics={"consciousness.*", "chemistry.signal", "fairy.wake.#"}
        )

        # Each pattern should work
        assert manager.can_subscribe(session_id, "consciousness.collision") is True
        assert manager.can_subscribe(session_id, "chemistry.signal") is True
        assert manager.can_subscribe(session_id, "fairy.wake.P10.Memory") is True

        # Non-matching should fail
        assert manager.can_subscribe(session_id, "postal.heartbeat") is False

    def test_no_allowed_topics_means_all_allowed(self):
        """
        If no allowed_topics specified, all topics should be allowed.

        This is the default permissive behavior for trusted external minds.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(
            fairy_name="TrustedMind",
            capabilities={"subscribe", "publish"}
            # No allowed_topics restriction
        )

        # Should be able to subscribe to anything
        assert manager.can_subscribe(session_id, "consciousness.collision") is True
        assert manager.can_subscribe(session_id, "fairy.wake.P10.Memory") is True
        assert manager.can_subscribe(session_id, "random.deep.nested.topic") is True


class TestSessionDestroyCleanup:
    """
    Test: Should clean up when session destroyed.

    When an external mind disconnects or times out, its session must be destroyed.
    This cleanup should:
    - Remove all subscriptions
    - Free any held resources
    - Notify interested parties
    - Update statistics
    """

    def test_destroy_session_removes_session(self):
        """
        Destroying a session should remove it from the manager.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(fairy_name="MortalMind")

        # Session should exist
        assert manager.get_session(session_id) is not None

        # Destroy it
        manager.destroy_session(session_id)

        # Session should no longer exist
        assert manager.get_session(session_id) is None

    def test_destroy_session_returns_subscription_ids(self):
        """
        Destroying a session should return subscription IDs for cleanup.

        The caller needs these IDs to unsubscribe from the postal system.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(fairy_name="CleanupMind")
        manager.add_subscription(session_id, "topic.a", subscription_id=100)
        manager.add_subscription(session_id, "topic.b", subscription_id=101)
        manager.add_subscription(session_id, "topic.c", subscription_id=102)

        # Destroy and get subscription IDs
        cleanup_info = manager.destroy_session(session_id)

        assert "subscription_ids" in cleanup_info
        assert set(cleanup_info["subscription_ids"]) == {100, 101, 102}

    def test_destroy_session_returns_fairy_name(self):
        """
        Destroying a session should return fairy name for logging/events.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        session_id = manager.create_session(fairy_name="LoggableMind")

        cleanup_info = manager.destroy_session(session_id)

        assert cleanup_info["fairy_name"] == "LoggableMind"

    def test_destroy_nonexistent_session_safe(self):
        """
        Destroying a non-existent session should be safe (no error).
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        # Should not raise
        cleanup_info = manager.destroy_session("nonexistent-session-xyz")

        # Should return empty/None info
        assert cleanup_info is None or cleanup_info.get("subscription_ids", []) == []

    def test_list_active_sessions(self):
        """
        Should be able to list all active sessions.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        id1 = manager.create_session(fairy_name="Mind1")
        id2 = manager.create_session(fairy_name="Mind2")
        id3 = manager.create_session(fairy_name="Mind3")

        active = manager.list_sessions()

        assert len(active) == 3
        assert id1 in active
        assert id2 in active
        assert id3 in active

        # Destroy one
        manager.destroy_session(id2)

        active = manager.list_sessions()
        assert len(active) == 2
        assert id2 not in active

    def test_session_statistics(self):
        """
        Session manager should track statistics.
        """
        from postal_core.akp_server import SessionManager

        manager = SessionManager()

        manager.create_session(fairy_name="StatsMind1")
        manager.create_session(fairy_name="StatsMind2")
        manager.create_session(fairy_name="StatsMind3")
        manager.destroy_session(
            manager.create_session(fairy_name="Ephemeral")
        )

        stats = manager.get_stats()

        assert stats["sessions_created"] >= 4
        assert stats["sessions_destroyed"] >= 1
        assert stats["sessions_active"] >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
