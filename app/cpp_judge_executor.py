import subprocess
import json
import os
from typing import Dict, Any

class CppJudgeExecutor:
    """
    一个通用的工具类，用于与一个通过标准输入输出进行JSON通信的
    C++可执行程序交互。这个类本身不关心JSON的内容和结构。
    """

    def __init__(self, executable_path: str):
        """
        使用C++可执行程序的路径初始化执行器。

        Args:
            executable_path: C++裁判程序的完整路径。
        
        Raises:
            FileNotFoundError: 如果在指定路径下找不到可执行文件。
        """
        self.executable_path = executable_path
        if not os.path.exists(self.executable_path):
            raise FileNotFoundError(
                f"C++ judge executable not found at: {self.executable_path}"
            )

    def run_raw_json(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行一次与C++程序的完整交互。

        它将输入的Python字典序列化为JSON字符串，通过管道传递给C++程序的
        标准输入，然后捕获C++程序的标准输出，并将其解析回Python字典。

        Args:
            input_data: 将被发送给C++程序的输入数据（Python字典）。

        Returns:
            从C++程序返回的输出数据（Python字典）。
        
        Raises:
            subprocess.CalledProcessError: 如果C++程序返回非零退出码。
            json.JSONDecodeError: 如果C++程序的输出不是有效的JSON。
            Exception: 其他在执行过程中发生的未知错误。
        """
        try:
            # 将输入的字典转换为JSON字符串
            input_json_str = json.dumps(input_data)

            # 运行C++可执行文件，并将JSON字符串传递给它的标准输入
            # text=True: 自动处理编码/解码
            # check=True: 如果进程返回非零退出码则抛出异常
            # capture_output=True: 捕获标准输出和标准错误
            result = subprocess.run(
                [self.executable_path],
                input=input_json_str,
                capture_output=True,
                text=True,
                check=True,
                timeout=2  # 设置一个超时时间防止程序卡死
            )

            # 解析C++程序从标准输出返回的JSON
            output_json = json.loads(result.stdout)
            return output_json

        except subprocess.CalledProcessError as e:
            # 如果C++程序崩溃，打印其标准错误流以方便调试
            print(f"Error executing C++ judge. Stderr:\n{e.stderr}")
            raise
        except json.JSONDecodeError as e:
            # 如果输出不是合法的JSON，打印出来以方便调试
            print(f"Failed to decode JSON from C++ judge output. Output was:\n{result.stdout}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred while running the C++ judge: {e}")
            raise