# 邦邦邦邦 真神来了 Frida

!!! warning "注意"
    本文档内容基于frida 17 版本，有部分破坏性更新，请注意版本区别
    </br>本文大部分场景是 android 平台下的场景，windows 等平台有相同之处，但也有区别，需自行查阅文档

## 什么是frida

> frida 是一款基于 python+javascript 的 hook 框架，可运行在 android、ios、linux、win等各个平台，主要使用的动态二进制插桩技术。

[项目地址](https://github.com/frida/frida)

[官网及使用文档](https://frida.re/)

## 基础配置

1. 安装frida
    ```bash
    pip install frida-tools
    ```
   
2. 如果在本机注入，则可以直接使用，例如：
    ```bash
    frida -p <pid> -l <script.js>
    frida -n <process_name> -l <script.js>
    ```

3. 在目标设备配置对应版本的frida-server并运行
    > 通过远程连接方式，端口转发方式连接，详见[绕过端口检测](#_8)
   
    ```bash
    chmod 777 frida-server
    ./frida-server
    ```
    
    ```bash
    # 客户端通过 USB 连接设备，-n 是可以省略的
    frida -U -n <package_name> -l hook.js
    ```


    ```python
    import frida

    # 获取 USB 设备（等同于 -U）
    device = frida.get_usb_device()
    
    # 附加到指定应用（包名）
    session = device.attach("com.example.app")
    
    # 注入脚本
    script = session.create_script("""
    console.log("Hello from Frida script!");
    """)

    script.load()
    ```

4. 测试frida正常连接
    ```bash
    frida-ps
    ```

## 基础使用

- frida使用python将javascript脚本注入到目标进程中运行，从而实现hook功能
- javascript基础语法较为简单，但是在frida中有大量自定义接口，需通过文档与脚本阅读理解学习，我将会在本帖按照随心而定的顺序介绍一些常用的接口。

### 注入模式
- attach 附加到正在运行的进程
- spawn 重启进程在运行开头注入，即加入-f参数

### 脚本参数
```bash hl_lines="1-3 17 27"
-h, --help            显示帮助信息并退出
-D ID, --device ID    连接到指定ID的设备
-U, --usb             连接到USB设备
-R, --remote          连接到远程frida-server
-H HOST, --host HOST  连接到指定主机的远程frida-server
--certificate CERTIFICATE 与主机建立TLS连接,期望证书为CERTIFICATE
--origin ORIGIN       连接到远程服务器时将"Origin"头设置为ORIGIN
--token TOKEN         使用TOKEN对主机进行身份验证
--keepalive-interval INTERVAL 设置keepalive间隔(秒),或设为0禁用(默认为-1,根据传输方式自动选择)
--p2p                 与目标建立点对点连接
--stun-server ADDRESS 设置与--p2p一起使用的STUN服务器地址
--relay address,username,password,turn-{udp,tcp,tls} 添加与--p2p一起使用的中继
-f TARGET, --file TARGET 启动文件
-F, --attach-frontmost 附加到前台应用程序
-n NAME, --attach-name NAME 附加到指定名称的进程
-N IDENTIFIER, --attach-identifier IDENTIFIER 附加到指定标识符的进程
-p PID, --attach-pid PID 附加到指定PID的进程
-W PATTERN, --await PATTERN 等待匹配PATTERN的进程启动
--stdio {inherit,pipe} 启动时的stdio行为(默认为"inherit")
--aux option          启动时设置辅助选项,如"uid=(int)42"(支持的类型有：string, bool, int)
--realm {native,emulated} 附加的运行环境
--runtime {qjs,v8}    使用的脚本运行时
--debug               启用Node.js兼容的脚本调试器
--squelch-crash       如果启用,将不在控制台输出崩溃报告
-O FILE, --options-file FILE 包含额外命令行选项的文本文件
--version             显示程序版本号并退出
-l SCRIPT, --load SCRIPT 加载脚本
-P PARAMETERS_JSON, --parameters PARAMETERS_JSON 以JSON格式传递参数,与Gadget相同
-C USER_CMODULE, --cmodule USER_CMODULE 加载C模块
--toolchain {any,internal,external} 编译源代码时使用的CModule工具链
-c CODESHARE_URI, --codeshare CODESHARE_URI 加载代码共享URI
-e CODE, --eval CODE  执行代码
-q                    静默模式(无提示符),执行-l和-e后退出
-t TIMEOUT, --timeout TIMEOUT 静默模式下等待退出的秒数
--pause               启动程序后保持主线程暂停
-o LOGFILE, --output LOGFILE 输出到日志文件
--eternalize          退出前永久化脚本
--exit-on-error       脚本中遇到异常时以代码1退出
--kill-on-exit        Frida退出时杀死启动的程序
--auto-perform        用Java.perform包装输入的代码
--auto-reload         启用提供的脚本和C模块的自动重载(默认启用,将来将成为必需)
--no-auto-reload      禁用提供的脚本和C模块的自动重载
```
### 获取进程信息

### 插桩

1. Interceptor.attach(target, callbacks[, data])
    - target: 需要hook的函数地址
    - callbacks: 回调函数对象
    - data: 可选数据对象



## frida 检测隐藏

### 文件名检测
- 检测：frida-server 文件名
- 绕过：修改frida-server的文件名

### 端口检测
- 检测：frida 默认 27042 和 27043 端口，通过检测这两个端口可以检测frida的存在
- 绕过：修改frida-server的端口号
    ```bash
    ./frida-server -l 127.0.0.1:<port>
    adb forward tcp:<port> tcp:<port>
    ```
  
    ??? note "为什么需要端口转发"
        USB 连接不是 TCP/IP 网络连接 虽然你通过 USB 连接了 Android 设备，但 USB 并不自动暴露设备上的 TCP 端口给你的电脑。
        你的电脑无法直接访问设备上的 127.0.0.1:1234 或 0.0.0.0:1234。
        </br>./frida-server在 Android 设备上监听一个 TCP 端口。但你的电脑无法直接访问这个端口，除非你通过网络或端口转发建立桥梁。
        </br>adb forward 通过端口转发告诉 ADB：把你电脑上的 localhost:1234 映射到 Android 设备上的 localhost:1234。
        这样你就可以在电脑上通过 127.0.0.1:1234 访问设备上的 frida-server。
    
    此时不能使用 -U 自动连接，应该：
    ```hash
    frida -H 127.0.0.1:<port> -n 进程名 -l hook.js
    ```
    而如果需要 python 脚本连接，则为：


    ```python
    import frida

    # 添加远程设备（通过 adb 转发到本地端口）
    device_manager = frida.get_device_manager()
    device = device_manager.add_remote_device("127.0.0.1:<port>")
    
    # 附加到目标进程（包名）
    session = device.attach("com.example.app")
    
    # 创建并加载脚本
    script = session.create_script("""
    console.log("Hello from Frida via port forwarding!");
    """)
    
    script.load()
    ```
### 双进程保护
- 检测：进程自己调试自己，使无法被 frida 附加
- 绕过：使用 spwn 方式启动程序
    ```bash
    frida -U -f 进程名 -l hook.js
    ```
