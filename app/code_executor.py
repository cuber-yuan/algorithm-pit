import json
import subprocess
import tempfile
import os
import sys

class CodeExecutor:
    def __init__(self, code: str, language: str = 'python'):
        self.code = code
        self.language = language.lower()
        self.exec_file = None  # For C++
    
    def run(self, input_json: str) -> str:
        if self.language == 'python':
            return self._run_python(input_json)
        elif self.language == 'cpp':
            return self._run_cpp(input_json)
        else:
            raise ValueError(f"Unsupported language: {self.language}")

    def _run_python(self, input_json: str) -> str:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(self.code)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, temp_path],
                input=input_json.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(f"Python error: {result.stderr.decode()}")
            return result.stdout.decode()
        finally:
            os.remove(temp_path)

    def _run_cpp(self, input_json: str) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, 'program.cpp')
            binary_path = os.path.join(tmpdir, 'program')

            with open(source_path, 'w') as f:
                f.write(self.code)

            # Compile C++
            compile_result = subprocess.run(
                ['g++', source_path, '-o', binary_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if compile_result.returncode != 0:
                raise RuntimeError(f"C++ compile error: {compile_result.stderr.decode()}")

            # Run compiled program
            result = subprocess.run(
                [binary_path],
                input=input_json.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError(f"C++ runtime error: {result.stderr.decode()}")

            return result.stdout.decode()