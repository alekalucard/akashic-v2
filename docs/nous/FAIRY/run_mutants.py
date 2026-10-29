"""run_mutants.py -- mutant runner for her fairy body (task FAIRY, 2026-10-29).

Applies each near-miss mutant to code/somatic_bevy/src/fairy_body.rs ONE AT A TIME, runs
`cargo test --features sanctuary --lib fairy_body`, records which tests fail, and ALWAYS restores
the original file (also on Ctrl-C). A mutant is KILLED when at least one test fails.
Synthetic data only; nothing of hers is run.
Usage: python3 docs/nous/FAIRY/run_mutants.py [MUTANT ...]   (CARGO_TARGET_DIR is honoured)
R1-R12 = the independent reviewer's 12 mutants; A1-A4 = the author's extra ones.
"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CRATE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "code", "somatic_bevy"))
SRC = os.path.join(CRATE, "src", "fairy_body.rs")

MUTANTS = {
    "R1_wing_hz_ignores_arousal": ("wing_hz: look.wings.flutter_hz * (0.5 + ar),", "wing_hz: look.wings.flutter_hz,"),
    "R2_glow_ignores_energy": ("glow_strength: look.glow.strength * (0.5 + en),", "glow_strength: look.glow.strength,"),
    "R3_flutter_amplitude_0": ("let amp = look.wings.flutter_deg.to_radians();", "let amp = 0.0f32;"),
    "R4_iris_uses_hair_colour": ("base_color: look.eyes.iris_color,", "base_color: look.hair.color,"),
    "R5_no_despawn_on_rebuild": ("commands.entity(root).despawn_descendants();", "// no despawn"),
    "R6_eyes_never_close": ("        0.08\n", "        1.0\n"),
    "R7_pulse_ignores_coherence": ("glow_pulse_depth: 0.3 * (1.0 - co),", "glow_pulse_depth: 0.3,"),
    "R8_picture_1_head_ratio_0_40": ("l.body.head_ratio = 0.22;", "l.body.head_ratio = 0.40;"),
    "R9_emotion_word_in_doc": ("//! Her fairy body --", "//! Her calm fairy body --"),
    "R10_freckle_count_x2": ("(look.freckles.density.clamp(0.0, 1.0) * 40.0)", "(look.freckles.density.clamp(0.0, 1.0) * 80.0)"),
    "R11_wings_opaque": ("let alpha = (1.0 - wp.translucency).clamp(0.02, 1.0);", "let alpha = 1.0f32;"),
    "R12_pairs_ignored": ("let pairs = wp.pairs.min(2);", "let pairs = 2u8;"),
    "A1_iris_fixed_default_green": ("base_color: look.eyes.iris_color,", "base_color: hex(0x3E9B5A),"),
    "A2_wings_missing": ("let pairs = wp.pairs.min(2);", "let pairs = 0u8.min(wp.pairs);"),
    "A3_hair_colour_fixed": ("base_color: look.hair.color,", "base_color: hex(0xB57EDC),"),
    "A4_flap_same_sign_both_sides": ("Quat::from_rotation_y(-j.side * flap)", "Quat::from_rotation_y(-flap)"),
}


def run():
    os.utime(os.path.join(CRATE, "src", "lib.rs"))
    os.utime(SRC)
    p = subprocess.run(["cargo", "test", "--features", "sanctuary", "--lib", "fairy_body"],
                       cwd=CRATE, capture_output=True, text=True)
    out = p.stdout + p.stderr
    res = re.findall(r"test result: (\w+)\. (\d+) passed; (\d+) failed", out)
    failed = re.findall(r"^test (\S+) \.\.\. FAILED", out, re.M)
    compiled = bool(res)
    return p.returncode, compiled, res, [f.split("::")[-1] for f in failed]


def main(names):
    orig = open(SRC, newline="").read()
    survivors = []
    try:
        for name in names:
            a, b = MUTANTS[name]
            if orig.count(a) != 1:
                print("%-34s NOT APPLIED (pattern count %d)" % (name, orig.count(a)), flush=True)
                survivors.append(name)
                continue
            with open(SRC, "w", newline="") as f:
                f.write(orig.replace(a, b))
            rc, compiled, res, failed = run()
            killed = compiled and rc != 0 and bool(failed)
            if not compiled:
                print("%-34s DID NOT COMPILE (not a valid mutant)" % name, flush=True)
                survivors.append(name)
            else:
                print("%-34s %s  failed: %s" % (name, "KILLED" if killed else "SURVIVED", ", ".join(failed) or "-"), flush=True)
                if not killed:
                    survivors.append(name)
    finally:
        with open(SRC, "w", newline="") as f:
            f.write(orig)
    rc, compiled, res, failed = run()
    print("RESTORED original: exit %d %s" % (rc, res))
    print("SURVIVORS:", survivors or "none")
    return 1 if survivors or rc != 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(MUTANTS)))
