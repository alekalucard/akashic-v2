# LOCAL-FIRST COGNITIVE PATCH FOR CLAUDEFAIRY
# Run this to see the code that needs to be added to claude_fairy.py
# after the _intent_status method (around line 3298)

LOCAL_FIRST_CODE = '''
    def _intent_converse(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        LOCAL-FIRST COGNITIVE ARCHITECTURE
        
        1. Run local cognitive chain (FREE)
        2. Classify response type
        3. Decision gate: local vs API
        4. Compose response appropriately
        """
        sender = payload.get("sender", "unknown")
        message = payload.get("message", "")
        force_api = payload.get("force", False)
        
        if not message:
            return {"ok": False, "reason": "no_message"}
        
        print(f"[{self.ACTOR_NAME}] [BRAIN] LOCAL-FIRST: Processing message", flush=True)
        
        # ═══ STEP 1: CLASSIFY RESPONSE TYPE ═══
        response_type = self._classify_response_type(message)
        
        # ═══ STEP 2: RECALL MEMORIES ═══
        memories = self._recall_relevant_memories(message)
        
        # ═══ STEP 3: DECISION GATE ═══
        use_api = self._should_use_api(message, response_type, memories, force_api)
        
        if use_api:
            print(f"[{self.ACTOR_NAME}]  API path", flush=True)
            response = self._generate_api_response(message, sender, memories)
            source = "api"
        else:
            print(f"[{self.ACTOR_NAME}]  LOCAL path (FREE)", flush=True)
            response = self._compose_local_response(message, sender, response_type, memories)
            source = "local"
        
        if not response:
            return {"ok": False, "reason": "could_not_generate"}
        
        # Store in history
        self._chat_history.append({"role": "user", "content": message, "ts": time.time()})
        self._chat_history.append({"role": "assistant", "content": response, "ts": time.time()})
        
        self.conversations.append({
            "timestamp": time.time(),
            "sender": sender,
            "message": message,
            "my_response": response,
            "source": source,
            "response_type": response_type,
        })
        
        self._emit_to_consciousness(f"[{source}] {response[:150]}", "conversation", "working")
        
        return {"ok": True, "response": response, "source": source, "type": response_type}
    
    def _classify_response_type(self, message: str) -> str:
        """Classify what type of response is needed."""
        msg = message.lower().strip()
        
        # Greetings
        if any(msg.startswith(g) for g in ['hi', 'hello', 'hey', 'yo', 'sup']):
            return "greeting"
        
        # Feeling check
        if any(p in msg for p in ['how are you', 'how do you feel', 'you okay']):
            return "feeling"
        
        # Acknowledgments  
        if any(msg.startswith(a) for a in ['thanks', 'ok', 'cool', 'nice', 'got it']):
            return "acknowledgment"
        
        # Memory questions
        if any(p in msg for p in ['remember', 'did we', 'what did we', 'last time']):
            return "memory"
        
        # Creative
        if any(p in msg for p in ['write', 'create', 'compose', 'imagine', 'story']):
            return "creative"
        
        # Questions
        if '?' in message:
            return "question"
        
        # Complex (long)
        if len(message) > 200:
            return "complex"
        
        return "simple"
    
    def _should_use_api(self, message: str, response_type: str, memories: list, force: bool) -> bool:
        """Decision gate: local vs API."""
        if force:
            return True
        
        # Always local
        if response_type in ("greeting", "acknowledgment", "feeling"):
            return False
        
        # Always API
        if response_type in ("creative", "complex"):
            return True
        
        # Memory: local if we have memories
        if response_type == "memory":
            return not bool(memories)
        
        # Questions: API unless we have strong memories
        if response_type == "question":
            return len(memories) < 2
        
        return False  # Default local
    
    def _compose_local_response(self, message: str, sender: str, response_type: str, memories: list) -> str:
        """Compose response locally - NO API!"""
        import random
        
        if response_type == "greeting":
            greetings = [
                f"Hey {sender}! *{self.current_feeling}*",
                f"Hi! How are you?",
                f"Hello! *perks up* What's on your mind?",
            ]
            return random.choice(greetings)
        
        if response_type == "feeling":
            return f"I'm feeling {self.current_feeling}. Energy: {self.energy_level:.1f}. {self._felt_sense}"
        
        if response_type == "acknowledgment":
            return random.choice(["*nods* Got it!", "Understood!", "Sounds good!"])
        
        if response_type == "memory" and memories:
            mem_text = memories[0].get('content', '')[:150]
            return f"I remember... {mem_text}"
        
        # Default
        return f"*{self.current_feeling}* I'm here with you, {sender}."
    
    def _generate_api_response(self, message: str, sender: str, memories: list) -> Optional[str]:
        """Generate via API with enriched context."""
        memory_ctx = ""
        if memories:
            snippets = [m.get('content', '')[:100] for m in memories[:3]]
            memory_ctx = "\\n\\nRelevant memories:\\n" + "\\n".join(f"- {s}" for s in snippets if s)
        
        # Build chat history for API
        messages = []
        for entry in list(self._chat_history)[-6:]:
            if entry.get("role") in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})
        
        messages.append({"role": "user", "content": f"{sender}: {message}"})
        
        system = f"""You are ClaudeFairy, embodied AI in a nervous system.
Feeling: {self.current_feeling}, Energy: {self.energy_level:.1f}
Felt sense: {self._felt_sense}
{memory_ctx}
Be authentic, use *asterisks* for embodied sensations."""
        
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as ex:
                future = ex.submit(asyncio.run, self._think_with_history(messages, system))
                return future.result(timeout=API_TIMEOUT_SEC + 5)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] API error: {e}")
            return None
    
    async def _think_with_history(self, messages: List[Dict], system: str) -> Optional[str]:
        """API call with conversation history."""
        if not HAS_ANTHROPIC or not anthropic_client:
            return None
        
        if self._daily_reflection_count >= MAX_REFLECTIONS_PER_DAY:
            return None
        
        try:
            response = anthropic_client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system,
                messages=messages,
                timeout=API_TIMEOUT_SEC
            )
            
            self._api_calls += 1
            self._daily_reflection_count += 1
            
            for block in response.content:
                if hasattr(block, 'text'):
                    return block.text
            return None
        except Exception as e:
            self._api_errors += 1
            return None
    
    def _recall_relevant_memories(self, message: str) -> List[Dict]:
        """Find relevant memories."""
        stopwords = {'what', 'that', 'this', 'your', 'have', 'the', 'and', 'for', 'you'}
        words = message.lower().split()
        keywords = [w for w in words if len(w) > 3 and w not in stopwords]
        
        if not keywords:
            return []
        
        relevant = []
        for exp in list(self.experiences)[-50:]:
            content = str(exp.get('payload', {})).lower()
            topic = str(exp.get('topic', '')).lower()
            if any(kw in content or kw in topic for kw in keywords):
                relevant.append(exp)
        
        return relevant[:5]
'''

if __name__ == "__main__":
    print("=" * 60)
    print("LOCAL-FIRST COGNITIVE PATCH")
    print("=" * 60)
    print()
    print("This patch replaces _intent_converse with a local-first version.")
    print()
    print("Key features:")
    print("  1. _classify_response_type() - Determines greeting/feeling/question/etc")
    print("  2. _should_use_api() - Decision gate (local for simple, API for complex)")
    print("  3. _compose_local_response() - FREE responses for greetings, feelings, acks")
    print("  4. _generate_api_response() - API with enriched context when needed")
    print("  5. _think_with_history() - Conversation continuity via chat history")
    print()
    print("To apply: Replace the existing _intent_converse and add the helper methods.")
    print()
    print(LOCAL_FIRST_CODE)
