"""Test import."""
print("Starting import test...")
try:
    from postal_core import PostalCore, USING_RUST
    print(f"Import successful. USING_RUST={USING_RUST}")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
print("Done.")
