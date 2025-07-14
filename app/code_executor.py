import json
import subprocess
import tempfile
import os
import sys
import shutil

class CodeExecutor:
    def __init__(self, code: str, language: str = 'python3'):
        self.code = code
        self.language = language.lower()
        self.exec_file = None  # For C++
    
    def run(self, input_str: str) -> str:
        if self.language == 'python3':
            # 将 self.code 作为参数直接传递
            return self._run_python(self.code, input_str)
        elif self.language == 'cpp':
            # C++ 部分逻辑不变
            return self._run_cpp(self.code, input_str)
        else:
            raise ValueError(f"Unsupported language: {self.language}")

    # 修改方法签名，接收 code_to_run 参数
    def _run_python(self, code_to_run: str, input_str: str) -> str:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            # 直接使用传入的参数进行写入
            f.write(code_to_run)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-u", temp_path],
                input=input_str.encode('utf-8'),
                capture_output=True,
                timeout=10, # 5-second timeout
                check=True # This will raise CalledProcessError on non-zero exit codes
            )
            return result.stdout.decode('utf-8')
        except subprocess.CalledProcessError as e:
            # 修改这里，打印更详细的错误信息到服务器控制台
            error_message = f"Bot code exited with error code {e.returncode}.\n" \
                            f"--- STDOUT ---\n{e.stdout.decode('utf-8')}\n" \
                            f"--- STDERR ---\n{e.stderr.decode('utf-8')}"
            print(error_message) # 在服务器后台打印详细错误
            raise RuntimeError(f"Bot execution failed. See server logs for details.")
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Python code execution timed out")
        finally:
            os.remove(temp_path)

    # 修改方法签名以保持一致性（虽然逻辑不变）
    def _run_cpp(self, code_to_run: str, input_json: str) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, 'program.cpp')
            binary_path = os.path.join(tmpdir, 'program')

            # 写入主程序
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(code_to_run)

            # 复制 jsoncpp.cpp 和 jsoncpp 文件夹到临时目录
            base_dir = os.path.dirname(os.path.abspath(__file__))
            jsoncpp_cpp = os.path.join(base_dir, 'jsoncpp.cpp')
            jsoncpp_dir = os.path.join(base_dir, 'jsoncpp')
            shutil.copy(jsoncpp_cpp, os.path.join(tmpdir, 'jsoncpp.cpp'))
            shutil.copytree(jsoncpp_dir, os.path.join(tmpdir, 'jsoncpp'))

            # 编译
            compile_result = subprocess.run(
                ['g++', 'program.cpp', 'jsoncpp.cpp', '-Ijsoncpp', '-o', 'program'],
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if compile_result.returncode != 0:
                raise RuntimeError(f"C++ compile error: {compile_result.stderr.decode()}")

            # 运行
            result = subprocess.run(
                [os.path.join(tmpdir, 'program')],
                input=input_json.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError(f"C++ runtime error: {result.stderr.decode()}")

            return result.stdout.decode()