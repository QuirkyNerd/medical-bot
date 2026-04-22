import os
import re

TARGET_DIR = "backend"

# Regex replacements for bad imports
replacements = [
    # from agents ... -> from backend.agents ...
    (re.compile(r"^(from\s+)(agents|core|services)(\s+)"), r"\1backend.\2\3"),
    # from agents.something ... -> from backend.agents.something ...
    (re.compile(r"^(from\s+)(agents|core|services)\."), r"\1backend.\2."),
    # import agents -> import backend.agents
    (re.compile(r"^(import\s+)(agents|core|services)(\s+|$)"), r"\1backend.\2\3"),
    # import agents.something -> import backend.agents.something
    (re.compile(r"^(import\s+)(agents|core|services)\."), r"\1backend.\2.")
]

print(f"Scanning '{TARGET_DIR}' modules to enforce ABSOLUTE IMPORTS (backend.*)...")
files_modified = []

for root, _, files in os.walk(TARGET_DIR):
    for file in files:
        if file.endswith(".py"):
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
    print("All imports are already using absolute paths.")
