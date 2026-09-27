# reflection_integration.py — Easy Integration with Organ Template
# ═══════════════════════════════════════════════════════════════════════════════
# Helpers to integrate reflection infrastructure with Organ Template fairies.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
from typing import Any, Type, TypeVar

from .reflective_mixin import ReflectiveMixin
from .reflection_pool import get_reflection_pool
from .learning_trace import get_trace_emitter

T = TypeVar("T")


def make_reflective(cls: Type[T]) -> Type[T]:
    """Create a reflective version of a fairy class."""
    original_init = cls.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.__init_reflection__()
    
    new_cls = type(
        f"Reflective{cls.__name__}",
        (cls, ReflectiveMixin),
        {"__init__": new_init}
    )
    new_cls.__module__ = cls.__module__
    return new_cls


def enable_reflection(cls: Type[T]) -> Type[T]:
    """Class decorator to enable reflection."""
    return make_reflective(cls)


def wire_reflection_to_postal(post_office: Any):
    """Wire reflection events to the postal system."""
    pool = get_reflection_pool()
    emitter = get_trace_emitter()
    
    def on_crystallize(reflection):
        try:
            post_office.route("telemetry.reflection", {
                "opcode": "REFLECTION_CRYSTALLIZED",
                "payload": {
                    "reflection_id": reflection.id,
                    "source_fairy": reflection.source_fairy,
                    "observation": reflection.observation[:200],
                },
            })
        except Exception:
            pass
    
    pool._on_crystallize = on_crystallize
    emitter.set_post_office(post_office)
    return True
