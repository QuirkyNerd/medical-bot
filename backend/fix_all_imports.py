import os
import re

TARGET_DIR = "."

# Regex replacements to strip 'backend.' prefix
replacements = [
    # from backend.core ... -> from core ...
    (re.compile(r"^(from\s+)backend\.(agents|core|services|api|scripts)(\s+)"), r"\1\2\3"),
    # from backend.core.something ... -> from core.something ...
    (re.compile(r"^(from\s+)backend\.(agents|core|services|api|scripts)\."), r"\1\2."),
    # import backend.core -> import core
    (re.compile(r"^(import\s+)backend\.(agents|core|services|api|scripts)(\s+|$)"), r"\1\2\3"),
    # import backend.core.something -> import core.something
    (re.compile(r"^(import\s+)backend\.(agents|core|services|api|scripts)\."), r"\1\2.")
]

print(f"Scanning '{TARGET_DIR}' modules to strip 'backend.' prefix...")
files_modified = []

for root, dirs, files in os.walk(TARGET_DIR):
    if ".venv" in root or "__pycache__" in root:
        continue
    for file in files:
        if file.endswith(".py") and file != "fix_all_imports.py":
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            modified = False
            new_lines = []
            
            for line in lines:
                new_line = line
                for pattern, replacement in replacements:
                    if pattern.match(new_line.lstrip()):
                        new_line = pattern.sub(replacement, new_line.lstrip())
                        # Restore leading whitespace if any
                        leading_space = len(line) - len(line.lstrip())
                        new_line = (" " * leading_space) + new_line
                        break # Only apply one fix per line
                
                if new_line != line:
                    modified = True
                new_lines.append(new_line)
            
            if modified:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                files_modified.append(filepath)

if files_modified:
    print(f"Fixed imports in {len(files_modified)} files:")
    for f in files_modified:
        print(f"  - {f}")
else:
    print("All imports are already corrected.")
