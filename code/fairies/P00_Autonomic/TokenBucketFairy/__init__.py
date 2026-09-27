"""
TokenBucketFairy - Cognitive Resource Management

Manages token buckets that create motivation for regenerative activities.
Low cognitive reserves → seek reflection. Low creative → seek daydreaming.
"""

from .fairy import (
    TokenBucketFairy,
    TokenBucket,
    BucketType,
    RegeneratorType,
    DrainType,
    RegenerationEvent,
    DrainEvent,
    REGENERATION_PROFILES,
    DRAIN_PROFILES,
    get_token_bucket_fairy,
    set_token_bucket_fairy,
)

__all__ = [
    "TokenBucketFairy",
    "TokenBucket",
    "BucketType",
    "RegeneratorType",
    "DrainType",
    "RegenerationEvent",
    "DrainEvent",
    "REGENERATION_PROFILES",
    "DRAIN_PROFILES",
    "get_token_bucket_fairy",
    "set_token_bucket_fairy",
]
