"""
Personal.AI API Latency Benchmark
=================================
Comprehensive benchmark script for Personal.AI API endpoints.

Tests multiple endpoints, configurations, and scenarios to identify
optimization opportunities for memory retrieval and conversation.

Usage:
    # Set API key via environment variable
    export PERSONAL_AI_API_KEY="your-key-here"

    # Or on Windows
    set PERSONAL_AI_API_KEY=your-key-here

    # Run the benchmark
    python personal_ai_benchmark.py

    # Run specific test
    python personal_ai_benchmark.py --test message

    # Run with custom domain
    python personal_ai_benchmark.py --domain sourpatches

    # Export results to JSON
    python personal_ai_benchmark.py --output results.json

Author: Akashic Foundation
Purpose: Identify optimal endpoints for real-time vs background operations
"""

import os
import sys
import json
import time
import argparse
import statistics
import threading
import concurrent.futures
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install with: pip install requests")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BenchmarkConfig:
    """Benchmark configuration."""
    api_key: str = ""
    base_url: str = "https://api.personal.ai/v1"
    domain: str = "sourpatches"
    iterations: int = 3  # Runs per test
    timeout: int = 60  # Request timeout in seconds
    warmup_runs: int = 1  # Warmup runs before timing
    concurrent_workers: int = 3  # For concurrency tests
    verbose: bool = False


def get_api_key() -> str:
    """Get API key from environment or secrets file."""
    # Environment variable takes priority
    api_key = os.getenv("PERSONAL_AI_API_KEY", "")
    if api_key:
        return api_key

    # Try secrets file
    secrets_paths = [
        Path(__file__).parent.parent / "fairies" / "P50_Persona" / "identity" / "personal_ai_secrets.json",
        Path(r"F:\Sandbox\failure_factory\akashic_v2\fairies\P50_Persona\identity\personal_ai_secrets.json"),
    ]

    for path in secrets_paths:
        try:
            if path.exists():
                with open(path, 'r') as f:
                    secrets = json.load(f)
                    return secrets.get("api_key", "")
        except Exception:
            pass

    return ""


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class RequestMetrics:
    """Metrics for a single API request."""
    endpoint: str
    method: str
    scenario: str

    # Timing
    time_to_first_byte: float = 0.0  # Seconds
    total_time: float = 0.0  # Seconds

    # Response
    status_code: int = 0
    response_size: int = 0  # Bytes
    ai_score: float = 0.0

    # Metadata
    success: bool = False
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    # Request info
    text_length: int = 0
    has_session_id: bool = False
    has_context: bool = False


@dataclass
class EndpointSummary:
    """Summary statistics for an endpoint."""
    endpoint: str
    scenario: str

    # Request counts
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Timing stats (in ms)
    avg_ttfb: float = 0.0
    min_ttfb: float = 0.0
    max_ttfb: float = 0.0
    p50_ttfb: float = 0.0
    p95_ttfb: float = 0.0

    avg_total: float = 0.0
    min_total: float = 0.0
    max_total: float = 0.0
    p50_total: float = 0.0
    p95_total: float = 0.0

    # Response stats
    avg_response_size: float = 0.0
    avg_ai_score: float = 0.0

    # Recommendation
    use_case: str = ""


@dataclass
class BenchmarkResults:
    """Complete benchmark results."""
    config: Dict[str, Any]
    start_time: str
    end_time: str
    duration_seconds: float

    raw_metrics: List[RequestMetrics]
    summaries: List[EndpointSummary]

    recommendations: Dict[str, str]


# =============================================================================
# API CLIENT
# =============================================================================

class PersonalAIClient:
    """Personal.AI API client with timing instrumentation."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "x-api-key": config.api_key
        })

    def _timed_request(
        self,
        method: str,
        endpoint: str,
        scenario: str,
        payload: Dict[str, Any],
        **kwargs
    ) -> RequestMetrics:
        """Execute a timed API request."""
        metrics = RequestMetrics(
            endpoint=endpoint,
            method=method,
            scenario=scenario,
            text_length=len(payload.get("Text", "")),
            has_session_id="SessionId" in payload,
            has_context="Context" in payload,
        )

        url = f"{self.config.base_url}{endpoint}"

        try:
            start_time = time.perf_counter()
            first_byte_time = None

            # Use streaming to measure TTFB
            response = self.session.request(
                method=method,
                url=url,
                json=payload,
                timeout=self.config.timeout,
                stream=True,
                **kwargs
            )

            # Time to first byte - read first chunk
            first_chunk = next(response.iter_content(chunk_size=1), None)
            first_byte_time = time.perf_counter()

            # Read the rest
            content = first_chunk + response.content if first_chunk else response.content
            end_time = time.perf_counter()

            metrics.time_to_first_byte = first_byte_time - start_time
            metrics.total_time = end_time - start_time
            metrics.status_code = response.status_code
            metrics.response_size = len(content)
            metrics.success = response.status_code == 200

            # Parse response for ai_score
            if metrics.success:
                try:
                    data = json.loads(content)
                    metrics.ai_score = float(data.get("ai_score", 0))
                except (json.JSONDecodeError, ValueError):
                    pass

        except requests.exceptions.Timeout:
            metrics.error = "Request timed out"
            metrics.total_time = self.config.timeout
        except requests.exceptions.RequestException as e:
            metrics.error = str(e)
        except Exception as e:
            metrics.error = f"Unexpected error: {e}"

        return metrics

    # =========================================================================
    # ENDPOINT METHODS
    # =========================================================================

    def message(
        self,
        text: str,
        scenario: str = "default",
        session_id: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs
    ) -> RequestMetrics:
        """
        POST /v1/message - Main conversation endpoint

        This is the primary endpoint for conversations. Returns ai_message
        and ai_score based on memory matching.
        """
        payload = {
            "Text": text,
            "DomainName": self.config.domain,
        }

        if session_id:
            payload["SessionId"] = session_id
        if context:
            payload["Context"] = context

        payload.update(kwargs)

        return self._timed_request("POST", "/message", scenario, payload)

    def instruction_search(
        self,
        text: str,
        scenario: str = "default",
        **kwargs
    ) -> RequestMetrics:
        """
        POST /v1/instruction?cmd=search - Memory search endpoint

        Direct memory search without AI generation. Should be faster
        for pure retrieval operations.
        """
        payload = {
            "Text": text,
            "DomainName": self.config.domain,
        }
        payload.update(kwargs)

        return self._timed_request(
            "POST",
            "/instruction?cmd=search",
            scenario,
            payload
        )

    def instruction_chatgpt(
        self,
        text: str,
        scenario: str = "default",
        context: Optional[str] = None,
        **kwargs
    ) -> RequestMetrics:
        """
        POST /v1/instruction?cmd=chatgpt - Instruction mode

        Uses instruction-following mode. May have different
        latency characteristics for complex queries.
        """
        payload = {
            "Text": text,
            "DomainName": self.config.domain,
        }

        if context:
            payload["Context"] = context

        payload.update(kwargs)

        return self._timed_request(
            "POST",
            "/instruction?cmd=chatgpt",
            scenario,
            payload
        )

    def document(
        self,
        text: str,
        scenario: str = "default",
        **kwargs
    ) -> RequestMetrics:
        """
        POST /v1/document - Document retrieval

        Retrieves relevant documents from memory. Useful for
        context building without conversation.
        """
        payload = {
            "Text": text,
            "DomainName": self.config.domain,
        }
        payload.update(kwargs)

        return self._timed_request("POST", "/document", scenario, payload)

    def conversation(
        self,
        text: str,
        scenario: str = "default",
        session_id: Optional[str] = None,
        **kwargs
    ) -> RequestMetrics:
        """
        POST /v1/conversation - Conversation history

        Retrieves or updates conversation history. May be useful
        for context management.
        """
        payload = {
            "Text": text,
            "DomainName": self.config.domain,
        }

        if session_id:
            payload["SessionId"] = session_id

        payload.update(kwargs)

        return self._timed_request("POST", "/conversation", scenario, payload)


# =============================================================================
# TEST SCENARIOS
# =============================================================================

# Test queries of varying complexity
TEST_QUERIES = {
    "simple": "Hello",
    "medium": "What do you remember about our last conversation?",
    "complex": "Describe in detail your understanding of consciousness, memory, and identity. How do these concepts relate to each other in your experience?",
}

# Context strings
TEST_CONTEXTS = {
    "none": None,
    "short": "Be brief.",
    "detailed": "You are helping with a research project on AI consciousness. Provide thoughtful, detailed responses that draw from your memory and experiences. Be authentic and personal.",
}


class BenchmarkRunner:
    """Runs benchmark tests across endpoints and scenarios."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.client = PersonalAIClient(config)
        self.results: List[RequestMetrics] = []

    def run_test(
        self,
        test_fn: Callable[..., RequestMetrics],
        scenario: str,
        iterations: int = None,
        **kwargs
    ) -> List[RequestMetrics]:
        """Run a test multiple times and collect metrics."""
        iterations = iterations or self.config.iterations
        metrics = []

        # Warmup
        for _ in range(self.config.warmup_runs):
            test_fn(**kwargs)
            time.sleep(0.5)  # Small delay between requests

        # Timed runs
        for i in range(iterations):
            if self.config.verbose:
                print(f"    Run {i+1}/{iterations}...", end=" ", flush=True)

            result = test_fn(scenario=scenario, **kwargs)
            metrics.append(result)
            self.results.append(result)

            if self.config.verbose:
                if result.success:
                    print(f"OK ({result.total_time*1000:.0f}ms)")
                else:
                    print(f"FAILED: {result.error}")

            # Rate limiting - be nice to the API
            time.sleep(1.0)

        return metrics

    # =========================================================================
    # BENCHMARK SUITES
    # =========================================================================

    def benchmark_message_endpoint(self) -> List[RequestMetrics]:
        """Benchmark the /message endpoint with various configurations."""
        print("\n--- Benchmarking /v1/message ---")
        all_metrics = []

        # Test 1: Simple vs Complex queries
        print("\n  Query Complexity:")
        for name, query in TEST_QUERIES.items():
            print(f"    [{name}] ", end="")
            metrics = self.run_test(
                self.client.message,
                scenario=f"message_query_{name}",
                text=query
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        # Test 2: With vs Without SessionId
        print("\n  Session ID:")
        for has_session in [False, True]:
            label = "with_session" if has_session else "no_session"
            print(f"    [{label}] ", end="")
            metrics = self.run_test(
                self.client.message,
                scenario=f"message_{label}",
                text=TEST_QUERIES["medium"],
                session_id="benchmark_session_001" if has_session else None
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        # Test 3: With vs Without Context
        print("\n  Context:")
        for name, context in TEST_CONTEXTS.items():
            print(f"    [{name}] ", end="")
            metrics = self.run_test(
                self.client.message,
                scenario=f"message_context_{name}",
                text=TEST_QUERIES["medium"],
                context=context
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        # Test 4: Different text lengths
        print("\n  Text Length:")
        text_lengths = [
            ("short", "Hi"),
            ("medium", "Tell me about yourself and your memories."),
            ("long", "I would like to have a detailed conversation about your experiences, memories, and understanding of various topics. Please share your thoughts on consciousness, identity, relationships, and growth. " * 3),
        ]
        for name, text in text_lengths:
            print(f"    [{name} ({len(text)} chars)] ", end="")
            metrics = self.run_test(
                self.client.message,
                scenario=f"message_length_{name}",
                text=text
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        return all_metrics

    def benchmark_instruction_search(self) -> List[RequestMetrics]:
        """Benchmark the /instruction?cmd=search endpoint."""
        print("\n--- Benchmarking /v1/instruction?cmd=search ---")
        all_metrics = []

        for name, query in TEST_QUERIES.items():
            print(f"  [{name}] ", end="")
            metrics = self.run_test(
                self.client.instruction_search,
                scenario=f"search_{name}",
                text=query
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        return all_metrics

    def benchmark_instruction_chatgpt(self) -> List[RequestMetrics]:
        """Benchmark the /instruction?cmd=chatgpt endpoint."""
        print("\n--- Benchmarking /v1/instruction?cmd=chatgpt ---")
        all_metrics = []

        for name, query in TEST_QUERIES.items():
            print(f"  [{name}] ", end="")
            metrics = self.run_test(
                self.client.instruction_chatgpt,
                scenario=f"chatgpt_{name}",
                text=query
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        return all_metrics

    def benchmark_document(self) -> List[RequestMetrics]:
        """Benchmark the /document endpoint."""
        print("\n--- Benchmarking /v1/document ---")
        all_metrics = []

        for name, query in TEST_QUERIES.items():
            print(f"  [{name}] ", end="")
            metrics = self.run_test(
                self.client.document,
                scenario=f"document_{name}",
                text=query
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        return all_metrics

    def benchmark_conversation(self) -> List[RequestMetrics]:
        """Benchmark the /conversation endpoint."""
        print("\n--- Benchmarking /v1/conversation ---")
        all_metrics = []

        for has_session in [False, True]:
            label = "with_session" if has_session else "no_session"
            print(f"  [{label}] ", end="")
            metrics = self.run_test(
                self.client.conversation,
                scenario=f"conversation_{label}",
                text=TEST_QUERIES["medium"],
                session_id="benchmark_session_001" if has_session else None
            )
            all_metrics.extend(metrics)
            avg = statistics.mean(m.total_time for m in metrics) * 1000
            print(f"Avg: {avg:.0f}ms")

        return all_metrics

    def benchmark_concurrency(self) -> List[RequestMetrics]:
        """Test concurrent requests to assess parallelization potential."""
        print("\n--- Benchmarking Concurrency ---")
        all_metrics = []

        # Sequential baseline
        print("  [sequential] ", end="", flush=True)
        start = time.perf_counter()
        sequential_metrics = []
        for _ in range(self.config.concurrent_workers):
            m = self.client.message(
                text=TEST_QUERIES["simple"],
                scenario="concurrency_sequential"
            )
            sequential_metrics.append(m)
            time.sleep(0.1)  # Small delay
        sequential_time = time.perf_counter() - start
        all_metrics.extend(sequential_metrics)
        print(f"Total: {sequential_time*1000:.0f}ms")

        time.sleep(2)  # Cooldown

        # Parallel execution
        print(f"  [parallel x{self.config.concurrent_workers}] ", end="", flush=True)
        start = time.perf_counter()
        parallel_metrics = []

        def make_request(i):
            return self.client.message(
                text=TEST_QUERIES["simple"],
                scenario="concurrency_parallel"
            )

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.concurrent_workers
        ) as executor:
            futures = [
                executor.submit(make_request, i)
                for i in range(self.config.concurrent_workers)
            ]
            for future in concurrent.futures.as_completed(futures):
                parallel_metrics.append(future.result())

        parallel_time = time.perf_counter() - start
        all_metrics.extend(parallel_metrics)
        print(f"Total: {parallel_time*1000:.0f}ms")

        # Analysis
        speedup = sequential_time / parallel_time if parallel_time > 0 else 0
        print(f"  Speedup: {speedup:.2f}x (parallel is {'faster' if speedup > 1 else 'slower'})")

        return all_metrics

    def run_all_benchmarks(self) -> List[RequestMetrics]:
        """Run all benchmark suites."""
        self.benchmark_message_endpoint()
        self.benchmark_instruction_search()
        self.benchmark_instruction_chatgpt()
        self.benchmark_document()
        self.benchmark_conversation()
        self.benchmark_concurrency()

        return self.results


# =============================================================================
# ANALYSIS & REPORTING
# =============================================================================

def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile of a list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (percentile / 100) * (len(sorted_values) - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def analyze_results(metrics: List[RequestMetrics]) -> List[EndpointSummary]:
    """Analyze raw metrics and generate summaries by endpoint/scenario."""
    # Group by endpoint and scenario
    groups: Dict[Tuple[str, str], List[RequestMetrics]] = {}
    for m in metrics:
        key = (m.endpoint, m.scenario)
        if key not in groups:
            groups[key] = []
        groups[key].append(m)

    summaries = []
    for (endpoint, scenario), group in sorted(groups.items()):
        successful = [m for m in group if m.success]

        if not successful:
            continue

        ttfb_times = [m.time_to_first_byte * 1000 for m in successful]  # Convert to ms
        total_times = [m.total_time * 1000 for m in successful]

        summary = EndpointSummary(
            endpoint=endpoint,
            scenario=scenario,
            total_requests=len(group),
            successful_requests=len(successful),
            failed_requests=len(group) - len(successful),

            avg_ttfb=statistics.mean(ttfb_times) if ttfb_times else 0,
            min_ttfb=min(ttfb_times) if ttfb_times else 0,
            max_ttfb=max(ttfb_times) if ttfb_times else 0,
            p50_ttfb=calculate_percentile(ttfb_times, 50),
            p95_ttfb=calculate_percentile(ttfb_times, 95),

            avg_total=statistics.mean(total_times) if total_times else 0,
            min_total=min(total_times) if total_times else 0,
            max_total=max(total_times) if total_times else 0,
            p50_total=calculate_percentile(total_times, 50),
            p95_total=calculate_percentile(total_times, 95),

            avg_response_size=statistics.mean(m.response_size for m in successful),
            avg_ai_score=statistics.mean(m.ai_score for m in successful if m.ai_score > 0) if any(m.ai_score > 0 for m in successful) else 0,
        )
        summaries.append(summary)

    return summaries


def generate_recommendations(summaries: List[EndpointSummary]) -> Dict[str, str]:
    """Generate recommendations based on benchmark results."""
    recommendations = {}

    # Find fastest endpoint for memory retrieval
    retrieval_endpoints = [
        s for s in summaries
        if "search" in s.scenario or "document" in s.scenario
    ]
    if retrieval_endpoints:
        fastest = min(retrieval_endpoints, key=lambda s: s.avg_total)
        recommendations["memory_retrieval"] = (
            f"Use {fastest.endpoint} ({fastest.scenario}) for memory retrieval. "
            f"Average latency: {fastest.avg_total:.0f}ms"
        )

    # Real-time vs background
    message_summaries = [s for s in summaries if s.endpoint == "/message"]
    if message_summaries:
        fastest_message = min(message_summaries, key=lambda s: s.avg_total)
        recommendations["real_time_conversation"] = (
            f"For real-time conversation, use /message with {fastest_message.scenario}. "
            f"Average latency: {fastest_message.avg_total:.0f}ms, "
            f"P95: {fastest_message.p95_total:.0f}ms"
        )

    # Session ID impact
    with_session = [s for s in summaries if "with_session" in s.scenario]
    no_session = [s for s in summaries if "no_session" in s.scenario]
    if with_session and no_session:
        avg_with = statistics.mean(s.avg_total for s in with_session)
        avg_without = statistics.mean(s.avg_total for s in no_session)
        diff = avg_with - avg_without
        recommendations["session_id"] = (
            f"SessionId {'adds' if diff > 0 else 'saves'} ~{abs(diff):.0f}ms. "
            f"{'Use for context continuity, skip for one-off queries.' if diff > 0 else 'Always use SessionId.'}"
        )

    # Context impact
    context_summaries = [s for s in summaries if "context" in s.scenario]
    if context_summaries:
        no_context = next((s for s in context_summaries if "none" in s.scenario), None)
        with_context = [s for s in context_summaries if "none" not in s.scenario]
        if no_context and with_context:
            avg_with = statistics.mean(s.avg_total for s in with_context)
            diff = avg_with - no_context.avg_total
            recommendations["context"] = (
                f"Adding Context {'adds' if diff > 0 else 'saves'} ~{abs(diff):.0f}ms on average. "
                f"Use context for quality, skip for speed."
            )

    # Concurrency
    concurrent = [s for s in summaries if "concurrency" in s.scenario]
    if len(concurrent) >= 2:
        seq = next((s for s in concurrent if "sequential" in s.scenario), None)
        par = next((s for s in concurrent if "parallel" in s.scenario), None)
        if seq and par:
            # Compare total throughput (not individual request times)
            recommendations["concurrency"] = (
                f"Parallel requests are {'supported' if par.avg_total < seq.avg_total * 0.8 else 'NOT recommended'}. "
                f"Sequential avg: {seq.avg_total:.0f}ms, Parallel avg: {par.avg_total:.0f}ms"
            )

    # Overall recommendation
    all_successful = [s for s in summaries if s.successful_requests > 0]
    if all_successful:
        fastest_overall = min(all_successful, key=lambda s: s.avg_total)
        recommendations["overall"] = (
            f"Fastest endpoint overall: {fastest_overall.endpoint} ({fastest_overall.scenario}) "
            f"at {fastest_overall.avg_total:.0f}ms average"
        )

    return recommendations


def print_results_table(summaries: List[EndpointSummary]):
    """Print results in a formatted table."""
    print("\n" + "=" * 100)
    print("BENCHMARK RESULTS")
    print("=" * 100)

    # Header
    print(f"{'Endpoint':<35} {'Scenario':<25} {'Avg(ms)':<10} {'P50(ms)':<10} {'P95(ms)':<10} {'Score':<8}")
    print("-" * 100)

    # Sort by endpoint then by avg time
    for summary in sorted(summaries, key=lambda s: (s.endpoint, s.avg_total)):
        print(
            f"{summary.endpoint:<35} "
            f"{summary.scenario:<25} "
            f"{summary.avg_total:>8.0f}  "
            f"{summary.p50_total:>8.0f}  "
            f"{summary.p95_total:>8.0f}  "
            f"{summary.avg_ai_score:>6.1f}"
        )

    print("=" * 100)


def print_recommendations(recommendations: Dict[str, str]):
    """Print recommendations in a clear format."""
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    order = [
        "memory_retrieval",
        "real_time_conversation",
        "session_id",
        "context",
        "concurrency",
        "overall"
    ]

    for key in order:
        if key in recommendations:
            title = key.replace("_", " ").title()
            print(f"\n[{title}]")
            print(f"  {recommendations[key]}")

    print("\n" + "-" * 80)
    print("USE CASE SUMMARY:")
    print("-" * 80)
    print("""
  REAL-TIME OPERATIONS (< 500ms target):
    - Use /v1/instruction?cmd=search for pure memory lookup
    - Use /v1/message with simple queries and no context for fast responses
    - Skip SessionId for one-off queries

  BACKGROUND OPERATIONS (latency tolerant):
    - Use /v1/message with Context for higher quality responses
    - Use SessionId for conversation continuity
    - Parallel requests may be supported - test with your workload

  MEMORY BUILDING:
    - Use /v1/message with is_stack=true to save responses to memory
    - Use /v1/document for bulk document retrieval
""")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Personal.AI API Latency Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python personal_ai_benchmark.py                    # Run all benchmarks
  python personal_ai_benchmark.py --test message    # Test only /message
  python personal_ai_benchmark.py --iterations 5    # 5 runs per test
  python personal_ai_benchmark.py --output results.json
        """
    )
    parser.add_argument("--domain", default="sourpatches", help="Personal.AI domain name")
    parser.add_argument("--iterations", type=int, default=3, help="Runs per test")
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout (seconds)")
    parser.add_argument("--test", choices=["message", "search", "chatgpt", "document", "conversation", "concurrency", "all"], default="all", help="Which test to run")
    parser.add_argument("--output", help="Output file for JSON results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("ERROR: No API key found!")
        print("Set PERSONAL_AI_API_KEY environment variable or create secrets file at:")
        print("  fairies/P50_Persona/identity/personal_ai_secrets.json")
        print('  {"api_key": "your-key-here"}')
        sys.exit(1)

    # Create config
    config = BenchmarkConfig(
        api_key=api_key,
        domain=args.domain,
        iterations=args.iterations,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    print("=" * 60)
    print("Personal.AI API Latency Benchmark")
    print("=" * 60)
    print(f"Domain: {config.domain}")
    print(f"Iterations per test: {config.iterations}")
    print(f"API Key: {'*' * 8}...{api_key[-4:]}")
    print(f"Base URL: {config.base_url}")
    print()

    # Run benchmarks
    runner = BenchmarkRunner(config)
    start_time = datetime.now()

    if args.test == "all":
        runner.run_all_benchmarks()
    elif args.test == "message":
        runner.benchmark_message_endpoint()
    elif args.test == "search":
        runner.benchmark_instruction_search()
    elif args.test == "chatgpt":
        runner.benchmark_instruction_chatgpt()
    elif args.test == "document":
        runner.benchmark_document()
    elif args.test == "conversation":
        runner.benchmark_conversation()
    elif args.test == "concurrency":
        runner.benchmark_concurrency()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Analyze results
    summaries = analyze_results(runner.results)
    recommendations = generate_recommendations(summaries)

    # Print results
    print_results_table(summaries)
    print_recommendations(recommendations)

    print(f"\nBenchmark completed in {duration:.1f} seconds")
    print(f"Total requests: {len(runner.results)}")
    print(f"Successful: {sum(1 for m in runner.results if m.success)}")
    print(f"Failed: {sum(1 for m in runner.results if not m.success)}")

    # Export to JSON if requested
    if args.output:
        results = BenchmarkResults(
            config=asdict(config),
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            raw_metrics=[asdict(m) for m in runner.results],
            summaries=[asdict(s) for s in summaries],
            recommendations=recommendations,
        )
        results.config.pop("api_key")  # Don't save API key

        with open(args.output, "w") as f:
            json.dump(asdict(results), f, indent=2, default=str)
        print(f"\nResults exported to: {args.output}")


if __name__ == "__main__":
    main()
