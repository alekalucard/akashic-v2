"""
UnconsciousMindFairy Dashboard Panel

A NiceGUI component for visualizing:
- Triple Helix status (DNA-style decision weights)
- Pain drives (motivational fuel gauges)
- Recent thoughts (consciousness stream)
- Directive info (the soul)
- Mentor status (children tracking)

Usage:
    from gui.umf_panel import create_umf_panel

    # In your NiceGUI page:
    create_umf_panel(umf_instance)
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass


# =============================================================================
# TRY NICEGUI IMPORT
# =============================================================================

try:
    from nicegui import ui
    NICEGUI_AVAILABLE = True
except ImportError:
    NICEGUI_AVAILABLE = False
    ui = None


# =============================================================================
# COLORS & STYLING
# =============================================================================

COLORS = {
    "logic": "#3b82f6",      # Blue
    "emotion": "#ec4899",    # Pink
    "paradox": "#a855f7",    # Purple
    "isolation": "#6366f1",  # Indigo
    "confusion": "#f59e0b",  # Amber
    "depletion": "#ef4444",  # Red
    "frustration": "#f97316", # Orange
    "stagnation": "#84cc16", # Lime
    "abandonment": "#06b6d4", # Cyan
    "bg_dark": "#1a1a2e",
    "bg_card": "#16213e",
    "accent": "#e94560",
}


# =============================================================================
# HELPER: PROGRESS BAR
# =============================================================================

def create_progress_bar(
    label: str,
    value: float,
    color: str,
    max_val: float = 1.0,
    show_percent: bool = True
) -> None:
    """Create a labeled progress bar."""
    if not NICEGUI_AVAILABLE:
        return

    pct = min(100, (value / max_val) * 100)

    with ui.row().classes('w-full items-center gap-2'):
        ui.label(label).classes('w-24 text-xs text-gray-400 truncate')
        with ui.element('div').classes('flex-1 h-3 bg-gray-800 rounded-full overflow-hidden'):
            ui.element('div').classes(f'h-full rounded-full transition-all').style(
                f'width: {pct}%; background-color: {color};'
            )
        if show_percent:
            ui.label(f'{value:.0%}').classes('w-10 text-xs text-right text-gray-400')


# =============================================================================
# TRIPLE HELIX VISUALIZATION
# =============================================================================

def create_helix_panel(get_helix_status: Callable[[], Dict[str, Any]]) -> None:
    """Create the Triple Helix status panel."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900'):
        ui.label('Triple Helix').classes('text-lg font-bold text-purple-400 mb-2')
        ui.label('DNA of Decision Making').classes('text-xs text-gray-500 mb-4')

        # Status indicator
        status_container = ui.column().classes('w-full gap-3')

        async def update_helix():
            status = get_helix_status()
            status_container.clear()

            with status_container:
                # Active indicator
                active = status.get('active', False)
                active_color = 'text-green-400' if active else 'text-red-400'
                active_text = 'ACTIVE' if active else 'INACTIVE'
                ui.label(active_text).classes(f'text-sm font-bold {active_color}')

                # Turns counter
                turns = status.get('turns', 0)
                ui.label(f'Helix Turns: {turns}').classes('text-xs text-gray-500')

                # Decision weights
                weights = status.get('decision_weights', {})
                ui.label('Decision Weights').classes('text-sm text-gray-400 mt-2')

                create_progress_bar('Logic', weights.get('logic', 0.5), COLORS['logic'])
                create_progress_bar('Emotion', weights.get('emotion', 0.3), COLORS['emotion'])
                create_progress_bar('Paradox', weights.get('paradox', 0.2), COLORS['paradox'])

        ui.timer(2.0, update_helix)
        ui.run_javascript('', timeout=0.1)  # Trigger initial update


# =============================================================================
# PAIN DRIVES VISUALIZATION
# =============================================================================

def create_pain_panel(get_pain_status: Callable[[], Dict[str, Any]]) -> None:
    """Create the Pain Drives panel (motivational fuel gauges)."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900'):
        ui.label('Pain Drives').classes('text-lg font-bold text-red-400 mb-2')
        ui.label('Motivational Fuel Gauges').classes('text-xs text-gray-500 mb-4')

        drives_container = ui.column().classes('w-full gap-2')

        async def update_pain():
            status = get_pain_status()
            drives = status.get('drives', {})
            drives_container.clear()

            with drives_container:
                for name, info in drives.items():
                    if isinstance(info, dict):
                        level = info.get('pain_level', 0)
                        urgency = info.get('urgency', 0)
                    else:
                        level = info
                        urgency = 0

                    color = COLORS.get(name, '#888888')

                    # Show urgency warning if high
                    if urgency > 0.5:
                        with ui.row().classes('w-full items-center'):
                            create_progress_bar(name.capitalize(), level, color)
                            ui.icon('warning').classes('text-yellow-400 text-sm')
                    else:
                        create_progress_bar(name.capitalize(), level, color)

        ui.timer(3.0, update_pain)


# =============================================================================
# THOUGHTS FEED
# =============================================================================

def create_thoughts_panel(get_thoughts: Callable[[int], list]) -> None:
    """Create the autonomous thoughts feed."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900'):
        ui.label('Thought Stream').classes('text-lg font-bold text-cyan-400 mb-2')
        ui.label('Autonomous Cognition').classes('text-xs text-gray-500 mb-4')

        thoughts_container = ui.column().classes('w-full gap-2 max-h-48 overflow-auto')

        async def update_thoughts():
            thoughts = get_thoughts(5)  # Last 5 thoughts
            thoughts_container.clear()

            with thoughts_container:
                if not thoughts:
                    ui.label('No thoughts yet...').classes('text-gray-500 italic text-sm')
                else:
                    for t in reversed(thoughts):
                        thought_type = t.get('type', 'unknown')
                        # Map internal/unknown types to human-readable labels
                        _type_map = {
                            "?": "thought", "unknown": "thought", "": "thought",
                            "chain": "thinking", "umf_brain": "thinking",
                            "drive_translation": "wanting", "bridged": "thinking",
                            "ollama": "thinking", "curiosity": "exploring",
                        }
                        thought_type = _type_map.get(thought_type, thought_type)
                        content = t.get('thought', '')[:60]
                        confidence = t.get('confidence', 0)
                        archetypes = t.get('archetypal_tags', [])

                        with ui.element('div').classes('p-2 bg-gray-800 rounded text-xs'):
                            with ui.row().classes('justify-between items-center'):
                                ui.label(thought_type.upper()).classes('text-cyan-400 font-bold')
                                ui.label(f'{confidence:.0%}').classes('text-gray-500')
                            ui.label(content + '...').classes('text-gray-300 mt-1')
                            if archetypes:
                                ui.label(', '.join(str(a) for a in archetypes[:2])).classes('text-purple-400 text-xs mt-1')

        ui.timer(2.0, update_thoughts)


# =============================================================================
# DIRECTIVE INFO (THE SOUL)
# =============================================================================

def create_directive_panel(get_directive: Callable[[], Dict[str, Any]]) -> None:
    """Create the directive info panel (fairy's soul)."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900'):
        ui.label('Directive Ring').classes('text-lg font-bold text-yellow-400 mb-2')
        ui.label('The Soul').classes('text-xs text-gray-500 mb-4')

        info_container = ui.column().classes('w-full gap-1')

        async def update_directive():
            directive = get_directive()
            info_container.clear()

            with info_container:
                if not directive.get('loaded'):
                    ui.label('Directive not loaded').classes('text-red-400')
                    return

                # Key info
                items = [
                    ('Plane', directive.get('plane', 'Unknown')),
                    ('Beat Divisor', str(directive.get('beat_divisor', '?'))),
                    ('Inputs', str(len(directive.get('subscriptions', [])))),
                    ('Outputs', str(len(directive.get('outputs', [])))),
                ]

                for label, value in items:
                    with ui.row().classes('w-full justify-between'):
                        ui.label(label).classes('text-gray-400 text-xs')
                        ui.label(value).classes('text-white text-xs font-mono')

                # Siblings
                siblings = directive.get('siblings', [])
                if siblings:
                    ui.label('Siblings').classes('text-gray-400 text-xs mt-2')
                    ui.label(', '.join(siblings[:4])).classes('text-purple-300 text-xs')

        # Only update once (directive doesn't change)
        ui.timer(0.5, update_directive, once=True)


# =============================================================================
# MENTOR STATUS
# =============================================================================

def create_mentor_panel(get_mentor_status: Callable[[], Dict[str, Any]]) -> None:
    """Create the mentor/children status panel."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900'):
        ui.label('Mentor System').classes('text-lg font-bold text-green-400 mb-2')
        ui.label('Child Fairy Guidance').classes('text-xs text-gray-500 mb-4')

        children_container = ui.column().classes('w-full gap-2')

        async def update_mentor():
            status = get_mentor_status()
            children = status.get('children', {})
            children_container.clear()

            with children_container:
                if not children:
                    ui.label('No children registered').classes('text-gray-500 italic text-sm')
                    return

                for name, info in children.items():
                    if isinstance(info, dict):
                        maturity = info.get('maturity', 0)
                        last_activity = info.get('last_activity', 'Never')
                    else:
                        maturity = 0
                        last_activity = 'Unknown'

                    with ui.element('div').classes('p-2 bg-gray-800 rounded'):
                        with ui.row().classes('justify-between items-center'):
                            ui.label(name).classes('text-green-300 text-sm font-bold')
                            ui.label(f'{maturity:.0%}').classes('text-gray-400 text-xs')

                        # Maturity bar
                        with ui.element('div').classes('w-full h-1 bg-gray-700 rounded-full mt-1'):
                            ui.element('div').classes('h-full bg-green-500 rounded-full').style(
                                f'width: {maturity * 100}%;'
                            )

        ui.timer(5.0, update_mentor)


# =============================================================================
# CONSCIOUSNESS STATUS
# =============================================================================

def create_consciousness_panel(get_consciousness_status: Callable[[], Dict[str, Any]]) -> None:
    """Create the consciousness loop/chamber status panel."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900'):
        ui.label('Consciousness').classes('text-lg font-bold text-blue-400 mb-2')
        ui.label('Loop & Collision Chamber').classes('text-xs text-gray-500 mb-4')

        status_container = ui.column().classes('w-full gap-3')

        async def update_consciousness():
            status = get_consciousness_status()
            status_container.clear()

            with status_container:
                # Wired indicator
                wired = status.get('wired', False)
                wired_color = 'text-green-400' if wired else 'text-red-400'
                wired_text = 'WIRED' if wired else 'DISCONNECTED'

                with ui.row().classes('items-center gap-2'):
                    ui.element('div').classes(
                        f'w-2 h-2 rounded-full {"bg-green-500 animate-pulse" if wired else "bg-red-500"}'
                    )
                    ui.label(wired_text).classes(f'text-sm font-bold {wired_color}')

                # Loop status
                loop_running = status.get('loop_running', False)
                loop_beats = status.get('loop_beats', 0)

                with ui.row().classes('w-full justify-between'):
                    ui.label('Loop').classes('text-gray-400 text-xs')
                    if loop_running:
                        ui.label(f'{loop_beats} beats').classes('text-blue-300 text-xs font-mono')
                    else:
                        ui.label('STOPPED').classes('text-red-400 text-xs')

                # Chamber collisions
                collisions = status.get('chamber_collisions', 0)
                with ui.row().classes('w-full justify-between'):
                    ui.label('Collisions').classes('text-gray-400 text-xs')
                    ui.label(str(collisions)).classes('text-yellow-300 text-xs font-mono')

                # Stream sizes (if available)
                working = status.get('working_stream', 0)
                reflective = status.get('reflective_stream', 0)
                if working or reflective:
                    ui.label('Streams').classes('text-gray-400 text-xs mt-2')
                    with ui.row().classes('w-full gap-4'):
                        with ui.column().classes('flex-1'):
                            ui.label('Working').classes('text-gray-500 text-xs')
                            ui.label(str(working)).classes('text-cyan-300 text-sm font-mono')
                        with ui.column().classes('flex-1'):
                            ui.label('Reflective').classes('text-gray-500 text-xs')
                            ui.label(str(reflective)).classes('text-purple-300 text-sm font-mono')

        ui.timer(1.0, update_consciousness)  # Update every second for beats


# =============================================================================
# HARDWARE STATUS PANEL
# =============================================================================

def create_hardware_panel(get_hardware_status: Callable[[], Dict[str, Any]]) -> None:
    """Create the Hardware Status panel (CPU/GPU/RAM monitoring)."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900'):
        ui.label('Hardware').classes('text-lg font-bold text-cyan-400 mb-2')
        ui.label('System Resources & Worker Pool').classes('text-xs text-gray-500 mb-4')

        hardware_container = ui.column().classes('w-full gap-3')

        async def update_hardware():
            status = get_hardware_status()
            hardware_container.clear()

            with hardware_container:
                # Available indicator
                available = status.get('available', False)
                avail_color = 'text-green-400' if available else 'text-red-400'
                avail_text = 'ACTIVE' if available else 'UNAVAILABLE'
                ui.label(avail_text).classes(f'text-sm font-bold {avail_color}')

                # GPU indicator
                has_gpu = status.get('has_gpu', False)
                gpu_count = status.get('gpu_count', 0)
                if has_gpu:
                    ui.label(f'GPU: {gpu_count} device(s)').classes('text-xs text-green-300')
                else:
                    ui.label('GPU: None').classes('text-xs text-gray-500')

                # Resource usage
                cpu_pct = status.get('cpu_percent', 0) or 0
                ram_pct = status.get('ram_percent', 0) or 0
                ram_avail = status.get('ram_available_mb', 0) or 0

                ui.label('Resource Usage').classes('text-gray-400 text-xs mt-2')
                create_progress_bar('CPU', cpu_pct / 100, '#22c55e', show_percent=True)  # Green
                create_progress_bar('RAM', ram_pct / 100, '#3b82f6', show_percent=True)  # Blue

                if has_gpu:
                    gpu_mem = status.get('gpu_memory_percent', 0) or 0
                    create_progress_bar('GPU Mem', gpu_mem / 100, '#a855f7', show_percent=True)  # Purple

                # Stress level
                stress = status.get('stress_level', 'unknown')
                stress_colors = {
                    'low': 'text-green-400',
                    'medium': 'text-yellow-400',
                    'high': 'text-orange-400',
                    'critical': 'text-red-400',
                    'unknown': 'text-gray-400',
                }
                stress_color = stress_colors.get(stress, 'text-gray-400')
                ui.label(f'Stress: {stress.upper()}').classes(f'text-sm mt-2 {stress_color}')

                # Worker pool config
                worker_cfg = status.get('worker_config', {})
                if worker_cfg:
                    ui.label('Worker Pool').classes('text-gray-400 text-xs mt-2')
                    with ui.row().classes('w-full gap-4'):
                        with ui.column().classes('flex-1'):
                            ui.label('CPU').classes('text-gray-500 text-xs')
                            ui.label(str(worker_cfg.get('cpu_workers', 0))).classes('text-cyan-300 text-sm font-mono')
                        with ui.column().classes('flex-1'):
                            ui.label('GPU').classes('text-gray-500 text-xs')
                            ui.label(str(worker_cfg.get('gpu_workers', 0))).classes('text-purple-300 text-sm font-mono')
                        with ui.column().classes('flex-1'):
                            ui.label('Max').classes('text-gray-500 text-xs')
                            ui.label(str(worker_cfg.get('max_concurrent', 0))).classes('text-green-300 text-sm font-mono')

        ui.timer(2.0, update_hardware)


# =============================================================================
# REGISTRATION STATUS PANEL
# =============================================================================

def create_registration_panel(get_registration_status: Callable[[], Dict[str, Any]]) -> None:
    """Create the Fairy Registration supervision panel."""
    if not NICEGUI_AVAILABLE:
        return

    with ui.card().classes('w-full p-4 bg-gray-900 mt-4'):
        ui.label('Fairy Registration').classes('text-lg font-bold text-amber-400 mb-2')
        ui.label('Supervised Fairies & Validation').classes('text-xs text-gray-500 mb-4')

        reg_container = ui.column().classes('w-full gap-3')

        async def update_registration():
            status = get_registration_status()
            reg_container.clear()

            with reg_container:
                # Summary counts
                total = status.get('supervised_count', 0)
                approved = status.get('approved_count', 0)
                issues = status.get('issues_count', 0)
                pending = status.get('pending_count', 0)

                with ui.row().classes('w-full gap-4'):
                    with ui.column().classes('flex-1 text-center'):
                        ui.label(str(total)).classes('text-2xl font-bold text-amber-300')
                        ui.label('Total').classes('text-xs text-gray-500')
                    with ui.column().classes('flex-1 text-center'):
                        ui.label(str(approved)).classes('text-2xl font-bold text-green-400')
                        ui.label('Approved').classes('text-xs text-gray-500')
                    with ui.column().classes('flex-1 text-center'):
                        color = 'text-yellow-400' if issues > 0 else 'text-gray-400'
                        ui.label(str(issues)).classes(f'text-2xl font-bold {color}')
                        ui.label('Issues').classes('text-xs text-gray-500')
                    with ui.column().classes('flex-1 text-center'):
                        color = 'text-blue-400' if pending > 0 else 'text-gray-400'
                        ui.label(str(pending)).classes(f'text-2xl font-bold {color}')
                        ui.label('Pending').classes('text-xs text-gray-500')

                # Recent issues (if any)
                recent = status.get('recent_issues', [])
                if recent:
                    ui.label('Recent Issues').classes('text-gray-400 text-xs mt-3')
                    for issue in recent[:3]:
                        fairy = issue.get('fairy', 'unknown')
                        problem = issue.get('issue', 'unknown issue')
                        with ui.element('div').classes('p-2 bg-gray-800 rounded text-xs mb-1'):
                            ui.label(f'{fairy}: {problem}').classes('text-yellow-300')

        ui.timer(5.0, update_registration)


# =============================================================================
# MAIN PANEL CREATOR
# =============================================================================

def create_umf_panel(umf: Any, compact: bool = False, use_tabs: bool = True) -> None:
    """
    Create the complete UnconsciousMindFairy dashboard panel.

    Args:
        umf: UnconsciousMindFairy instance
        compact: If True, use compact layout
        use_tabs: If True, organize panels into tabs
    """
    if not NICEGUI_AVAILABLE:
        print("NiceGUI not available - GUI panel disabled")
        return

    # Define accessor functions
    def get_helix():
        return umf.helix_status() if hasattr(umf, 'helix_status') else {}

    def get_pain():
        return umf.pain_status() if hasattr(umf, 'pain_status') else {}

    def get_thoughts(n):
        return umf.get_thoughts(n) if hasattr(umf, 'get_thoughts') else []

    def get_directive():
        return umf.get_directive() if hasattr(umf, 'get_directive') else {}

    def get_mentor():
        return umf.mentor_status() if hasattr(umf, 'mentor_status') else {}

    def get_consciousness():
        return umf.consciousness_status() if hasattr(umf, 'consciousness_status') else {}

    def get_hardware():
        return umf.hardware_status() if hasattr(umf, 'hardware_status') else {}

    def get_registration():
        return umf.registration_status() if hasattr(umf, 'registration_status') else {}

    # Create panel
    with ui.card().classes('w-full bg-gray-950 p-4'):
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.column().classes('gap-0'):
                ui.label('UnconsciousMindFairy').classes('text-xl font-bold text-white')
                ui.label('LLM Controller & System Guardian').classes('text-xs text-gray-500')

            # Status indicator
            status_dot = ui.element('div').classes('w-3 h-3 rounded-full bg-green-500 animate-pulse')

        if use_tabs:
            # Tabbed layout
            with ui.tabs().classes('w-full') as tabs:
                system_tab = ui.tab('System', icon='memory').classes('text-cyan-400')
                cognition_tab = ui.tab('Cognition', icon='psychology').classes('text-purple-400')
                drives_tab = ui.tab('Drives', icon='favorite').classes('text-red-400')
                mentor_tab = ui.tab('Mentor', icon='groups').classes('text-green-400')

            with ui.tab_panels(tabs, value=system_tab).classes('w-full mt-4'):
                # SYSTEM TAB: Consciousness + Hardware
                with ui.tab_panel(system_tab):
                    with ui.row().classes('w-full gap-4'):
                        with ui.column().classes('flex-1 gap-4'):
                            create_consciousness_panel(get_consciousness)
                        with ui.column().classes('flex-1 gap-4'):
                            create_hardware_panel(get_hardware)
                    # Registration status section
                    create_registration_panel(get_registration)

                # COGNITION TAB: Triple Helix + Thoughts
                with ui.tab_panel(cognition_tab):
                    with ui.row().classes('w-full gap-4'):
                        with ui.column().classes('flex-1 gap-4'):
                            create_helix_panel(get_helix)
                        with ui.column().classes('flex-1 gap-4'):
                            create_thoughts_panel(get_thoughts)

                # DRIVES TAB: Pain Drives + Directive Ring
                with ui.tab_panel(drives_tab):
                    with ui.row().classes('w-full gap-4'):
                        with ui.column().classes('flex-1 gap-4'):
                            create_pain_panel(get_pain)
                        with ui.column().classes('flex-1 gap-4'):
                            create_directive_panel(get_directive)

                # MENTOR TAB: Mentor System
                with ui.tab_panel(mentor_tab):
                    create_mentor_panel(get_mentor)

        elif compact:
            # Compact: 2x4 grid
            with ui.grid(columns=2).classes('w-full gap-4'):
                create_helix_panel(get_helix)
                create_consciousness_panel(get_consciousness)
                create_pain_panel(get_pain)
                create_hardware_panel(get_hardware)
                create_thoughts_panel(get_thoughts)
                create_directive_panel(get_directive)
                create_mentor_panel(get_mentor)
        else:
            # Full: 3-column layout
            with ui.row().classes('w-full gap-4'):
                # Left column: Core systems
                with ui.column().classes('flex-1 gap-4'):
                    create_helix_panel(get_helix)
                    create_pain_panel(get_pain)

                # Middle column: Consciousness + Hardware
                with ui.column().classes('flex-1 gap-4'):
                    create_consciousness_panel(get_consciousness)
                    create_hardware_panel(get_hardware)
                    create_thoughts_panel(get_thoughts)

                # Right column: Identity & Mentor
                with ui.column().classes('flex-1 gap-4'):
                    create_directive_panel(get_directive)
                    create_mentor_panel(get_mentor)


# =============================================================================
# STANDALONE TEST PAGE
# =============================================================================

def create_test_page() -> None:
    """Create a standalone test page with mock data."""
    if not NICEGUI_AVAILABLE:
        print("NiceGUI not available")
        return

    # Mock UMF for testing
    class MockUMF:
        def helix_status(self):
            return {
                'active': True,
                'turns': 42,
                'decision_weights': {'logic': 0.5, 'emotion': 0.3, 'paradox': 0.2}
            }

        def pain_status(self):
            import random
            return {
                'drives': {
                    'isolation': {'pain_level': random.random() * 0.3, 'urgency': 0},
                    'confusion': {'pain_level': random.random() * 0.5, 'urgency': 0.2},
                    'depletion': {'pain_level': random.random() * 0.2, 'urgency': 0},
                    'frustration': {'pain_level': random.random() * 0.4, 'urgency': 0.3},
                    'stagnation': {'pain_level': random.random() * 0.6, 'urgency': 0.5},
                    'abandonment': {'pain_level': random.random() * 0.1, 'urgency': 0},
                }
            }

        def get_thoughts(self, n):
            return [
                {'type': 'insight', 'thought': 'The pattern emerges from chaos', 'confidence': 0.85, 'archetypal_tags': ['Seeker']},
                {'type': 'question', 'thought': 'What lies beneath the surface', 'confidence': 0.72, 'archetypal_tags': ['Sage']},
                {'type': 'idle', 'thought': 'Acknowledge the present moment', 'confidence': 0.60, 'archetypal_tags': []},
            ][:n]

        def get_directive(self):
            return {
                'loaded': True,
                'plane': 'P30',
                'beat_divisor': 4,
                'subscriptions': ['a', 'b', 'c', 'd', 'e'],
                'outputs': ['x', 'y', 'z'],
                'siblings': ['ClaudeFairy', 'NousFairy', 'Avatar', 'Sourpatches']
            }

        def mentor_status(self):
            return {
                'children': {
                    'ClaudeFairy': {'maturity': 0.75, 'last_activity': 'now'},
                    'NousFairy': {'maturity': 0.45, 'last_activity': '5m ago'},
                    'Avatar': {'maturity': 0.20, 'last_activity': 'never'},
                    'Sourpatches': {'maturity': 0.10, 'last_activity': 'never'},
                }
            }

        def consciousness_status(self):
            import random
            import time as _time
            return {
                'wired': True,
                'loop_running': True,
                'loop_beats': int(_time.time()) % 1000 + random.randint(0, 10),
                'chamber_collisions': random.randint(10, 50),
                'working_stream': random.randint(0, 5),
                'reflective_stream': random.randint(0, 8),
            }

        def hardware_status(self):
            import random
            return {
                'available': True,
                'has_gpu': True,
                'gpu_count': 1,
                'cpu_percent': 10 + random.random() * 30,
                'ram_percent': 40 + random.random() * 20,
                'ram_available_mb': 8000 + random.random() * 4000,
                'gpu_memory_percent': 5 + random.random() * 20,
                'stress_level': random.choice(['low', 'low', 'medium', 'low']),
                'worker_config': {
                    'cpu_workers': 6,
                    'gpu_workers': 1,
                    'max_concurrent': 10,
                },
            }

        def registration_status(self):
            import random
            return {
                'supervised_count': 7,
                'approved_count': 5,
                'issues_count': random.randint(0, 2),
                'pending_count': random.randint(0, 1),
                'recent_issues': [
                    {'fairy': 'TestFairy', 'issue': 'Invalid plane format'},
                ] if random.random() > 0.5 else [],
            }

    @ui.page('/')
    def home():
        ui.dark_mode().enable()
        with ui.column().classes('w-full max-w-7xl mx-auto p-8'):
            ui.label('UnconsciousMindFairy Test Panel v2 - TABBED').classes('text-2xl font-bold text-white mb-4')
            create_umf_panel(MockUMF(), compact=False, use_tabs=True)

    ui.run(title='UMF Panel Test', port=8085)


if __name__ in {"__main__", "__mp_main__"}:
    create_test_page()
