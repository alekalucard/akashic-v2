#!/usr/bin/env python3
"""
Run Cardinal's WoW Ecosystem Analysis for Sanctuary Fairies
============================================================

This invokes Cardinal (Mistral via Ollama) to analyze:
- wow.export for glTF model extraction
- AzerothCore GM tools for Hand of God inspiration
- Character models (Demon Hunter etc) for fairy avatars
- Animation support for consciousness-driven expression

Prerequisites:
- Ollama running: ollama serve
- Mistral model pulled: ollama pull mistral

Usage:
    python run_cardinal_wow_analysis.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add paths
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies" / "P60_Executive" / "CardinalFairy"))

from fairies.P60_Executive.CardinalFairy.fairy import CardinalFairy


async def run_analysis():
    """Run the WoW ecosystem analysis."""
    print("=" * 70)
    print("CARDINAL SYSTEM - WoW Ecosystem Analysis for Sanctuary")
    print("=" * 70)
    print()

    # Create Cardinal
    cardinal = CardinalFairy()

    # Check Ollama health first
    print("[1/3] Checking Ollama connection...")
    healthy = await cardinal.ollama.check_health()

    if not healthy:
        print()
        print("ERROR: Ollama is not responding!")
        print()
        print("Please ensure Ollama is running:")
        print("  1. Open a terminal")
        print("  2. Run: ollama serve")
        print("  3. In another terminal: ollama pull mistral")
        print("  4. Try again")
        return None

    print("  Ollama: HEALTHY")
    print()

    # Run WoW analysis
    print("[2/3] Analyzing WoW ecosystem for Sanctuary integration...")
    print("  This will take 30-60 seconds (Mistral is thinking)...")
    print()

    result = await cardinal.analyze_wow_for_sanctuary()

    print("[3/3] Analysis complete!")
    print()

    # Pretty print the result
    if "result" in result:
        analysis = result["result"]

        if "error" not in analysis:
            print("=" * 70)
            print("ANALYSIS RESULTS")
            print("=" * 70)
            print()

            # Overall score
            score = analysis.get("overall_fit_score", 0)
            rec = analysis.get("recommendation", "unknown")
            print(f"Overall Fit Score: {score:.0%}")
            print(f"Recommendation: {rec.upper()}")
            print()

            # Technical compatibility
            tech = analysis.get("technical_compatibility", {})
            print("Technical Compatibility:")
            print(f"  Score: {tech.get('score', 0):.0%}")
            print(f"  Bevy Integration: {tech.get('bevy_integration', 'unknown')}")
            print(f"  Format Support: {tech.get('format_support', 'unknown')}")
            print(f"  Notes: {tech.get('notes', 'N/A')}")
            print()

            # Assets
            assets = analysis.get("asset_evaluation", {})
            models = assets.get("character_models", {})
            anims = assets.get("animations", {})
            print("Asset Evaluation:")
            print(f"  Character Models: {'Available' if models.get('available') else 'Not available'}")
            print(f"  Quality: {models.get('quality', 'unknown')}")
            print(f"  Fairy Suitable: {'Yes!' if models.get('fairy_suitable') else 'No'}")
            print(f"  Examples: {', '.join(models.get('examples', []))}")
            print(f"  Animations: {'Available' if anims.get('available') else 'Not available'}")
            print(f"  Licensing: {assets.get('licensing', 'unknown')}")
            print()

            # Consciousness integration
            conscious = analysis.get("consciousness_integration", {})
            print("Consciousness Integration:")
            print(f"  Wire to Chemistry: {'Yes' if conscious.get('can_wire_to_chemistry') else 'No'}")
            print(f"  Expression Support: {conscious.get('expression_support', 'unknown')}")
            print(f"  Emotion Mapping: {conscious.get('emotion_mapping_difficulty', 'unknown')}")
            print()

            # Implementation path
            impl = analysis.get("implementation_path", {})
            print("Implementation Path:")
            print(f"  Phase 1: {impl.get('phase_1', 'N/A')}")
            print(f"  Phase 2: {impl.get('phase_2', 'N/A')}")
            print(f"  Phase 3: {impl.get('phase_3', 'N/A')}")
            print(f"  Estimated Effort: {impl.get('estimated_effort', 'unknown')}")
            print()

            # Risks & Opportunities
            print("Risks:")
            for risk in analysis.get("risks", []):
                print(f"  - {risk}")
            print()

            print("Opportunities:")
            for opp in analysis.get("opportunities", []):
                print(f"  - {opp}")
            print()

            # The insight
            insight = analysis.get("elegant_insight", "")
            if insight:
                print("=" * 70)
                print("ELEGANT INSIGHT")
                print("=" * 70)
                print(insight)
                print()
        else:
            print("Error in analysis:")
            print(analysis.get("error"))
            if "raw" in analysis:
                print("Raw response:")
                print(analysis["raw"])

    # Show where results were saved
    print("=" * 70)
    print(f"Full results saved to: C:/Akashic_Cardinal_Sandbox/experiments/")
    print(f"Analysis ID: {result.get('analysis_id', 'unknown')}")
    print("=" * 70)

    return result


async def main():
    """Main entry point."""
    try:
        result = await run_analysis()
        if result:
            # Also save a quick summary for the autonomous Nous to find
            summary_path = Path("C:/Akashic_Cardinal_Sandbox/wow_analysis_latest.json")
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(json.dumps(result, indent=2))
            print(f"\nLatest analysis also saved to: {summary_path}")
    except KeyboardInterrupt:
        print("\nAnalysis cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
