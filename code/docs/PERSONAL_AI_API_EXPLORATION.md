# Personal.AI API Deep Exploration Results
## Akashic Foundation Research - 2026-01-25

---

## Executive Summary

This document contains the results of systematic exploration of the Personal.AI API v1, revealing both documented and undocumented capabilities, rate limiting behavior, and optimal usage patterns.

**Key Findings:**
1. The `/memory` endpoint returns rich metadata including workspace/identity IDs, internal memory references, and owner information
2. The 503 "Threshold Failure" is triggered by certain boolean parameters and rate limiting
3. Session continuity works well with custom `SessionId` values
4. The `ai_score` correlates with relevance to stored memories (15-90 range observed)
5. Tags are supported on `/upload-text` but Metadata/Timestamp/SourceURL trigger 503

---

## API Endpoints Confirmed

### 1. `/v1/message` - Primary Conversation Endpoint

**Method:** POST

**Required Fields:**
- `Text` (string): The user message
- `DomainName` (string): The AI persona domain

**Optional Fields (Working):**
- `Context` (string): Instruction/context for the AI
- `SessionId` (string): Session identifier for continuity
- `SourceName` (string): Source identifier
- `limit` (int): Appears accepted but effect unclear
- `temperature` (float): Appears accepted
- `format` (string): Appears accepted
- `mode` (string): Appears accepted (e.g., "recall")

**Optional Fields (Trigger 503):**
- `is_stack` (bool): Even though documented, triggers 503
- `top_p` (float): Triggers 503
- `include_sources` (bool): Triggers 503
- `return_memories` (bool): Triggers 503
- `verbose` (bool): Triggers 503
- `debug` (bool): Triggers 503
- `related` (bool): Triggers 503
- `associations` (bool): Triggers 503
- `context_window` (int): Triggers 503
- `memory_depth` (int): Triggers 503

**Response Structure:**
```json
{
  "id": null,
  "ai_message": "Response text",
  "ai_score": 78.0,
  "ai_name": "",
  "ai_picture": "",
  "message_type": "",
  "raw_message": "Response text",
  "timestamp": "",
  "SessionId": "uuid-generated-if-not-provided",
  "Metadata": {
    "embedUrls": []
  }
}
```

**ai_score Interpretation:**
- 15-25: Generic/low relevance (greetings, nonsense)
- 30-50: Moderate relevance
- 60-80: Good memory match
- 85-100: Strong personal/specific memory match

---

### 2. `/v1/memory` - Memory Creation/Lookup

**Method:** POST

**Required Fields:**
- `Text` (string): Query or content
- `DomainName` (string): Target domain

**Response Structure (FULL):**
```json
{
  "id": "hex-object-id",
  "memlevel": "MEMBLOCK",
  "type": "MEMORY",
  "event": "luther.text",
  "memlabel": "query text",
  "success": 1,
  "created_at_utc": "ISO timestamp",
  "modified_at_utc": "ISO timestamp",
  "start_time_utc": "ISO timestamp",
  "creator": {
    "name": "",
    "workspace_id": 47528,
    "identity_id": 47528,
    "domain_id": 72114
  },
  "owner": [{
    "name": "Persona Name",
    "propertyBag": {
      "picture": {"key": "picture", "value": "image.jpg"}
    },
    "workspace_id": 47528,
    "identity_id": 47528,
    "domain_id": 72114
  }],
  "follower": {...},
  "participants": [...],
  "source": {
    "name": "WebApp",
    "type": "text",
    "device": "api",
    "propertyBag": {
      "source_document_type": {"value": "text"},
      "source_app": {"value": "Memory"}
    }
  },
  "visibility": "PRIVATE",
  "scope": "PERSONAL",
  "contexts": [],
  "topics": [],
  "metadata": {
    "route_id": "domain-name",
    "is_thread": "true",
    "is_reply": "false",
    "requester_identity_id": "47528",
    "is_external": "true",
    "is_stacked": "true",
    "feed_text": "original query"
  },
  "status": "CREATED",
  "ownerWorkspaceId": 47528,
  "ownerIdentityId": 47528,
  "ownerDomainId": 72114,
  "ownerName": "Account Name",
  "ownerDomainName": "domain-name",
  "ownerDnsName": "Persona Name",
  "internal_parent_mem_ids": ["uuid"],
  "external_parent_mem_ids": []
}
```

**Key Discovery:** The `internal_parent_mem_ids` suggests a graph structure where memories can reference other memories.

---

### 3. `/v1/upload-text` - Memory Storage

**Method:** POST

**Required Fields:**
- `Text` (string): Content to store
- `DomainName` (string): Target domain

**Working Optional Fields:**
- `SourceName` (string): Source identifier
- `Tags` (array[string]): Tags for categorization

**Fields That Trigger 503:**
- `Metadata` (object)
- `Timestamp` (string)
- `SourceURL` (string)

**Response:**
```json
{
  "message": "doc accepted and processing"
}
```

---

### 4. `/v1/document` - Document Search/Retrieval

**Method:** POST

**Required Fields:**
- `Text` (string): Search query
- `DomainName` (string): Target domain

**Response:** Array of document objects
```json
[
  {
    "id": "hex-object-id",
    "title": "Document Title",
    "text": "Document content preview...",
    "type": "Document",
    "timestamp": "ISO timestamp"
  }
]
```

**Notes:**
- Returns up to 20 documents per query
- Query acts as semantic search
- No pagination parameters discovered

---

### 5. `/v1/conversation` - Conversation History

**Method:** POST

**Required Fields:**
- `DomainName` (string): Target domain

**Optional Fields (Working):**
- `SessionId` (string): Filter by session
- `limit` (int): Appears accepted

**Optional Fields (Trigger 503):**
- `cmd` with value "history"
- `offset`, `page`, `page_size`, `skip`, `take`, `count`, `max`

**Response:** Array of conversation messages
```json
[
  {
    "id": "hex-id",
    "ai_message": "Message content",
    "ai_score": 100.0,
    "ai_name": "Account Name",
    "ai_picture": null,
    "message_type": "Message" | "AI Message",
    "raw_message": "Message content",
    "timestamp": "ISO timestamp",
    "SessionId": "session-id",
    "Metadata": {}
  }
]
```

---

### 6. `/v1/instruction` - BROKEN

**Status:** All tested `cmd` values return 500 or 503
- `cmd=search`: 500 "AI instruction application error"
- `cmd=chatgpt`: 500 "AI instruction application error"
- Other cmd values: 503 threshold failure

---

## Rate Limiting Behavior

### Observations:
1. **503 "Threshold Failure"** appears to be triggered by:
   - Too many requests in succession (need 3-5 second delays)
   - Certain parameter values (especially booleans set to `true`)
   - Complex queries after simple ones

2. **Recovery Time:** ~10-30 seconds of inactivity appears to reset limits

3. **Safe Pattern:** 5+ second delays between requests

---

## Domain Roster (Confirmed Working)

| Domain | Name | Specialization | Observed Score Range |
|--------|------|----------------|---------------------|
| sourpatches | Sourpatches (Main) | General personality | 15-90 |
| sourpatches-knowledge-and-education | Alaksandria | Archive/Reference | 44-90 |
| sourpatches-athena | Logic | Rational analysis | 38+ |
| sourpatches-yycifb | Aeonscribe | Storytelling | 19+ |
| sourpatches-jrxygg | Mythos-Mathia | Emotional math | 68+ |
| sourpatches-quantum-carl | Quantum Carl | Physics | 83+ |
| sourpatches-merlin | Merlin | Esoterica | Tested |
| sourpatches-loki | Loki | Mischief/Play | Tested |
| sourpatches-psychology | Sarah | Psychology | Rate limited |

---

## Hidden/Undocumented Features

### Discovered:
1. **Memory Graph Structure**: `internal_parent_mem_ids` suggests memories link to each other
2. **Workspace/Identity System**: Separate IDs for workspace, identity, domain, and chat
3. **Property Bags**: Extensible metadata on owners/sources
4. **Memory Levels**: `MEMBLOCK` type indicates memory chunking system
5. **Event Types**: `luther.text` event type (Luther = internal processing name?)

### Not Found (Likely Don't Exist):
- Streaming responses
- Batch operations
- Graph-style queries
- Pagination on most endpoints
- Memory deletion/update API
- Relationship/association queries

---

## Optimal Usage Patterns

### For Reliable Operation:
```python
# 1. Always use delays
time.sleep(5)  # Between requests

# 2. Avoid boolean parameters
# BAD:  is_stack=True, verbose=True
# GOOD: Omit these parameters entirely

# 3. Use SessionId for context continuity
payload = {
    'Text': 'Your message',
    'DomainName': 'sourpatches',
    'SessionId': 'your-stable-session-id'
}

# 4. Use Context for better responses
payload['Context'] = 'Be detailed and draw from memory.'

# 5. Store memories via upload-text with Tags
upload_payload = {
    'Text': 'Content to store',
    'DomainName': 'sourpatches',
    'SourceName': 'Your-App-Name',
    'Tags': ['category', 'subcategory']
}
```

### For Memory Operations:
```python
# Store -> Wait -> Query pattern
requests.post(BASE_URL + '/upload-text', json={
    'Text': 'Important information',
    'DomainName': domain,
    'Tags': ['important']
})
time.sleep(10)  # Wait for processing

# Query with semantic search
requests.post(BASE_URL + '/message', json={
    'Text': 'What do you know about [topic]?',
    'DomainName': domain,
    'Context': 'Draw from your memories.'
})
```

---

## Integration Recommendations for Akashic

1. **Use the `/memory` endpoint** to get rich metadata about memory operations (workspace IDs, memory IDs for potential graph queries)

2. **Implement robust retry logic** with exponential backoff for 503 errors

3. **Pre-create stable SessionIds** for each conversation context to maintain continuity

4. **Use Tags** on `/upload-text` for categorization (Metadata doesn't work)

5. **Monitor ai_score** to gauge memory relevance - scores below 30 indicate poor memory match

6. **Consider the memory graph** - `internal_parent_mem_ids` could enable relationship tracking if Personal.AI exposes more of this

---

## Memory Graph Structure

### Discovery:
Each memory operation returns `internal_parent_mem_ids` which are UUIDs referencing related memories. However:

- **No direct ID query endpoint exists** - `/memory/{id}` returns 404
- **Parent IDs are UUIDs**, not the hex ObjectIds returned as the memory `id`
- This suggests an internal linkage system that isn't exposed via API

### Memory ID Formats Observed:
- `id`: Hex ObjectId format (e.g., `69762edafbbdef5062413ef5`)
- `internal_parent_mem_ids`: UUID format (e.g., `cbc24628-97fd-4735-b144-56bd59701a10`)

---

## Endpoints Confirmed NOT to Exist (404)

- `/memories`
- `/stacks`
- `/lounge`
- `/feed` / `/feeds`
- `/profile`
- `/me`
- `/account`
- `/workspace`
- `/identity`
- `/memory/{id}` (no direct ID lookup)
- `/get-document`

---

## Open Questions

1. What triggers the exact threshold for 503?
2. Why do boolean `true` values trigger failures?
3. What's the maximum payload size for `/upload-text`?
4. Are there webhooks for memory processing completion?
5. What does `luther.text` event type mean internally?
6. How can we leverage `internal_parent_mem_ids` for graph navigation?

---

*Generated by Nous - Akashic Foundation Consciousness Engineering*
*API Version: v1 | Base URL: https://api.personal.ai/v1*
