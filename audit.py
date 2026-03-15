import ast
import glob
import os
import sys

def audit_directory(directory):
    for filepath in glob.glob(os.path.join(directory, '**/*.py'), recursive=True):
        if 'venv' in filepath or '.env' in filepath or '.venv' in filepath: continue
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except Exception as e:
                print(f"Error parsing {filepath}: {e}")
                continue
            
            # This is a naive AST walker just to look for issues if we wanted to
            # But the best way is to print out the functions and classes and see if they are used elsewhere
            # Given the complexity of a proper linter, we will just use regex/ast combination or rely on manual review.

if __name__ == '__main__':
    audit_directory('src')
    audit_directory('scripts')
