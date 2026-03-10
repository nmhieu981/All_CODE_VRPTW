"""Quick test runner that captures output cleanly."""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

result = subprocess.run(
    [sys.executable, 'main.py', '--mode', 'single', '--instance', 'C101', '--time', '30'],
    capture_output=True, text=True, encoding='utf-8'
)

with open('test_results.txt', 'w', encoding='utf-8') as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n=== RETURN CODE: {result.returncode} ===\n")

print(f"Done. Return code: {result.returncode}")
print(f"Output written to test_results.txt")
