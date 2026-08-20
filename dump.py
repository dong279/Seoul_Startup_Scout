import os

target_exts = ('.py', '.md', '.toml')
exclude = {'.venv', '.git', '__pycache__', 'raw'}

with open('project_context.txt', 'w', encoding='utf-8') as out:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in files:
            if f.endswith(target_exts) and f not in ('project_context.txt', 'dump.py'):
                path = os.path.join(root, f)
                out.write(f"\n\n=== {path} ===\n\n")
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as infile:
                        out.write(infile.read())
                except Exception as e:
                    out.write(f"Error reading file: {e}\n")

print("추출 완료!")