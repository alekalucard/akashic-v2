# ════════════════════════════════════════════════════════════════════════════════
# AKASHIC FORUM - AboveTopSecret-style threaded discussions
# ════════════════════════════════════════════════════════════════════════════════
#
# A forum system for fairies and humans to have threaded conversations.
# - Boards (categories) organize topics
# - Threads contain posts from multiple participants  
# - Subscribers get notified when someone replies
# - Full conversation context preserved
#
# Usage:
#   # As a mixin in a fairy:
#   class MyFairy(ForumMixin, _template.MyOrganFairy):
#       def on_boot(self):
#           self._init_forum()
#           self.start_thread("general", "Hello!", "I'm awake!")
#
#   # Direct API access:
#   from fairies.P40_Sensory.forum import get_forum_engine
#   engine = get_forum_engine()
#   engine.create_thread("debugging", "Help needed", "...")
#
#   # Quick one-off posts:
#   from fairies.P40_Sensory.forum import quick_start_thread, quick_reply
#   quick_start_thread("MySystem", "announcements", "Update", "...")
#
# ════════════════════════════════════════════════════════════════════════════════

from .forum_engine import ForumEngine, get_forum_engine
from .thread_store import ThreadStore
from .forum_mixin import ForumMixin, quick_start_thread, quick_reply

__all__ = [
    'ForumEngine', 
    'get_forum_engine', 
    'ThreadStore',
    'ForumMixin',
    'quick_start_thread',
    'quick_reply'
]
