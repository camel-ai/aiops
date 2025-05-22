import threading
import time
import sys

def test_threading():
    """测试线程功能"""
    sys.stdout.write("开始测试线程功能\n")
    sys.stdout.flush()
    
    def thread_function(name):
        sys.stdout.write(f"线程 {name} 开始运行\n")
        sys.stdout.flush()
        time.sleep(2)
        sys.stdout.write(f"线程 {name} 完成\n")
        sys.stdout.flush()
    
    # 创建一个新线程
    t = threading.Thread(target=thread_function, args=("测试线程",))
    t.start()
    
    sys.stdout.write("主线程继续执行\n")
    sys.stdout.flush()
    t.join()
    sys.stdout.write("测试线程已完成\n")
    sys.stdout.flush()

if __name__ == "__main__":
    # 测试线程模块
    sys.stdout.write("开始执行测试脚本\n")
    sys.stdout.flush()
    test_threading()
    sys.stdout.write("测试脚本执行完毕\n")
    sys.stdout.flush() 