import os

def create_project_dump(output_filename="project_code_dump.txt"):
    # Harte Blockade für alle unnötigen Ordner (inkl. .env und .obs)
    ignore_dirs = ['.git', '__pycache__', 'venv', 'env', '.venv', '.env', '.obs', '.idea', '.vscode']
    allowed_extensions = ['.py', '.json']

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        outfile.write("### IFPT CONTROLLING - CLEAN PROJECT DUMP ###\n\n")
        
        for root, dirs, files in os.walk('.'):
            # Ordner in-place filtern, damit os.walk sie gar nicht erst betritt
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if any(file.endswith(ext) for ext in allowed_extensions) and file != "dump_project.py":
                    filepath = os.path.join(root, file)
                    outfile.write(f"\n{'='*80}\n### FILE: {filepath} ###\n{'='*80}\n\n")
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"# Lese-Fehler: {e}\n")
                        
    print(f"✅ Sauberer Dump '{output_filename}' erfolgreich erstellt!")

if __name__ == "__main__":
    create_project_dump()