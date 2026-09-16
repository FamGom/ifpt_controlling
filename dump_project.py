import os

def create_project_dump(output_filename="project_code_dump.txt"):
    # Ordner und Dateien, die ignoriert werden sollen (wichtig, um Token-Limit nicht zu sprengen!)
    ignore_dirs = ['.git', '__pycache__', 'venv', 'env', '.idea', '.vscode']
    allowed_extensions = ['.py', '.json']

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        outfile.write("### IFPT CONTROLLING - FULL PROJECT DUMP ###\n\n")
        
        for root, dirs, files in os.walk('.'):
            # Ignoriere bestimmte Ordner
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if any(file.endswith(ext) for ext in allowed_extensions) and file != "dump_project.py":
                    filepath = os.path.join(root, file)
                    
                    outfile.write(f"\n{'='*80}\n")
                    outfile.write(f"### FILE: {filepath} ###\n")
                    outfile.write(f"{'='*80}\n\n")
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"# Konnte nicht gelesen werden: {e}\n")
                        
    print(f"✅ Erfolgreich! Datei '{output_filename}' wurde erstellt.")

if __name__ == "__main__":
    create_project_dump()