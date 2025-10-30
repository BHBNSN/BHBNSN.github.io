# Android 基础知识

本文档收集一些理论性知识，较为零碎，但是最终编织成一张大网。

最后更新与 2025-10-29 by N0rth5ea in CAUC

---

>实践固然能极快的获得成就感，但唯有理论的积累才能让你走得更远。

## Android 系统分层架构与启动流程
??? quote "参考资料"
    - [Android启动系列之一：init进程和Zygote进程](https://cloud.tencent.com/developer/article/2415718){target="_blank" rel="noopener"}

!!! note "相关链接"
    - [Zygote](#zygote)
    - [System Server](#system-server)

Android 是一个基于 Linux 内核的复杂操作系统。其启动过程是一个从硬件加电到显示应用界面的分层、接力过程。

### 1. 系统启动层

* **Boot ROM (引导只读存储器)**
    * 当按下电源键时，CPU 首先会执行固化在 ROM 中的一小段代码。
    * 它会进行基本的硬件检查，然后找到并加载下一阶段的引导程序（Bootloader）到 RAM 中。

* **Bootloader (引导加载程序)**
    * Bootloader 负责初始化更多的硬件（如内存、闪存）。
    * 最重要的是将 Android 的核心**Linux Kernel**从闪存加载到 RAM 中，然后跳转到内核代码开始执行。

### 2. 内核层

* **Linux Kernel (Linux 内核)**
    * 这是 Android 系统的核心。内核启动后，它会接管 CPU，并开始初始化各种驱动程序（如显示、键盘、Wi-Fi）和核心系统功能（如进程管理、内存管理）。
    * 内核启动的最后一步，是在用户空间（User Space）中启动第一个进程，即 **`init` 进程**。

### 3. 原生用户空间 (Native User Space)

* **`init` 进程**
    * `init` 是 Android 系统中的第一个进程（PID 1），是所有其他用户空间进程的“祖先”。
    * 它会解析 `.rc` 结尾的初始化脚本文件（例如 `init.rc`）。
    * 根据这些脚本，`init` 进程会启动系统运行所需的各种原生服务（Daemons），例如 `logd` (日志服务)、`vold` (卷管理服务)等。
    * 启动了至关重要的进程：**`Zygote`**。

### 4. Java 框架层 (Framework)

* **`Zygote` (受精卵) 进程**
    * **核心功能：** 启动 Java 虚拟机 (JVM/ART)，预加载 Android 框架的核心 Java 类库和系统资源。
    * 通过`fork`自身来创建新的进程。由于核心类库已预加载，可以直接继承给App，这使得 App 的启动速度极快。这个过程又称为“孵化”。
    * `Zygote` 启动后首先会孵化出 **`System Server`** 进程。

* **`System Server` (系统服务进程)**
    * `System Server` 是 Android 框架的核心。这是系统中第一个运行的 Java 进程。
    * 它负责启动和管理所有核心的系统服务。
    * `System Server` 启动完成后，Android 系统真正“准备就绪”，并会发送 `BOOT_COMPLETED` 广播，同时启动 Launcher（桌面应用）。

### 5. 应用层 (App)

* **App (应用程序) 进程**
    * 当点击一个应用时，Launcher 会通知 `Activity Manager Service` (在 `System Server` 进程中)。
    * `AMS` 会检查该应用是否已有进程，如果没有，它会请求 `Zygote` 进程。
    * `Zygote` 收到请求后，会孵化出一个继承了 `Zygote` 预加载的虚拟机和核心资源的子进程，即为该应用进程，然后加载应用代码，启动应用的 `Activity`。

## Android 系统交互机制

* **SysCall (System Call - 系统调用)**
    * 这是用户空间（包括 `init`、`Zygote`、App）与 **Linux 内核** 交互的唯一桥梁。
    * 当 App 需要访问硬件（如读写文件、打开摄像头、发送网络数据）时，它不能直接操作，必须通过 SysCall 向内核发出请求，由内核代为完成，以保证系统安全和稳定。

* **JNI (Java Native Interface - Java 本地接口)**
    * 这是 Android 中 Java 代码与 C/C++（Native）代码交互的桥梁。
    * Android 的框架层（如 `System Server`）和应用（App）主要是用 Java 编写的，但它们需要调用底层的系统功能（例如图形渲染、硬件访问），这些功能通常由 C/C++ 实现。
    * **流程：** Java 代码 (App) → JNI → C/C++ (Native 库) → SysCall → Linux 内核。

* **Binder (进程间通信)**
    * 这是 Android 特有的高性能进程间通信（IPC）机制。
    * 它在 Android 中无处不在：
        * App 与 `System Server`（AMS, PMS 等）之间的通信。
        * App 与 App 之间的通信。

## Zygote

??? quote "参考资料"
    - [Zygote 进程简介](https://source.android.google.cn/docs/core/runtime/zygote?hl=zh-cn){target="_blank" rel="noopener"}
    - [谈谈对Android中Zygote的理解](https://zhuanlan.zhihu.com/p/260414370){target="_blank" rel="noopener"}
    - [Android启动系列之一：init进程和Zygote进程](https://cloud.tencent.com/developer/article/2415718){target="_blank" rel="noopener"}
    - [Android 9.0.0_r45 源码分析](https://github.com/lulululbj/android_9.0.0_r45/tree/master){target="_blank" rel="noopener"}
    - [zygote 进程启动分析一](https://juejin.cn/post/7504582519733485604){target="_blank" rel="noopener"}
    - [AOSPXRef](http://aospxref.com/){target="_blank" rel="noopener"}

!!! note "相关链接"
    - [Android 启动流程](#android_1)
    - [Xposed](#xposed)
    - [System Server](#system-server)

> 在 Android 启动流程中，我们已经简要介绍了 Zygote 进程的作用。大名鼎鼎的 Xposed 框架正是通过 Hook Zygote 来实现对所有 App 的代码注入。
> 因此我们来从代码仔细深入了解下 Zygote 的工作原理。

!!! note "无特殊说明，以下源码均基于 [Android 16.0.0_r2 源码](http://aospxref.com/android-16.0.0_r2/){target="_blank" rel="noopener"} 分析"

按照我们[之前的介绍](#3-native-user-space)，Zygote 是由 init 进程启动的。我们可以在 init.rc 中找到对应启动：

```bash title="/system/core/rootdir/init.rc"
#line 526:528
--8<-- "docs/study/android/source/init.rc:526:528"
#line 1087:1095
--8<-- "docs/study/android/source/init.rc:1087:1095"
```
系统会启动 zygote 和 zygote_secondary 服务。这两个服务声明于以下配置文件中： 

=== "init.zygote32"
    ```bash title="/system/core/rootdir/init.zygote32.rc"
    --8<-- "docs/study/android/source/init.zygote32.rc"
    ```
=== "init.zygote64"
    ```bash title="/system/core/rootdir/init.zygote64.rc"
    --8<-- "docs/study/android/source/init.zygote64.rc"
    ```
=== "init.zygote64_secondary"
    ```bash title="/system/core/rootdir/init.zygote64_32.rc"
    --8<-- "docs/study/android/source/init.zygote64_32.rc"
    ```

可以看出，zygote 服务会启动 `/system/bin/app_process(64)` 进程。

源码网站上并没有这个文件，我从 Android 9 的实体机中提取了这个文件，是一个 ELF 文件，IDA 启动。

```C title="/system/bin/app_process64 main()"
  if ( (v55 & 0x100000000LL) != 0 )
  {
    p_com.android.internal.os.RuntimeInit = "com.android.internal.os.ZygoteInit";
    v42 = 1;
  }
  // ...
  android::AndroidRuntime::start(v61, p_com.android.internal.os.RuntimeInit, v58, v42);
```
在经过一系列参数比对后，启动了java层`com.android.internal.os.ZygoteInit`，我们回到Android 16.0.0_r2源码中查看这个类：

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
// 检查参数 line 848:860
--8<-- "docs/study/android/source/ZygoteInit.java:848:860"
// 预加载资源供后续孵化用 line 879:889
--8<-- "docs/study/android/source/ZygoteInit.java:879:889"
// 孵化 SystemServer line 984:913
--8<-- "docs/study/android/source/ZygoteInit.java:904:913"
// 循环等待创建请求 line 917:919
--8<-- "docs/study/android/source/ZygoteInit.java:917:919"
```

??? qutoe "ZygoteInit.java完整文件"
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
    --8<-- "docs/study/android/source/ZygoteInit.java"
    ```

我们看看 ZygoteInit 最后启动 zygoteServer.runSelectLoop 方法:

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java" hl_lines="27 32"
// runSelectLoop 方法 line 173:263
--8<-- "docs/study/android/source/ZygoteServer.java:173:206"
//...
--8<-- "docs/study/android/source/ZygoteServer.java:228:229"
//...
--8<-- "docs/study/android/source/ZygoteServer.java:252:263"
```

??? qutoe "ZygoteServer.java完整文件"
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java"
    --8<-- "docs/study/android/source/ZygoteServer.java"
    ```

可以看出 runSelectLoop 方法负责监听和管理请求，具体 fork 逻辑在 ZygoteConnection 方法中：

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java"
// 可以看到调用 Native 层的 fork 逻辑 line 234:237 hl_lines="234-237"
--8<-- "docs/study/android/source/ZygoteConnection.java:234:237"
```

??? qutoe "ZygoteConnection.java完整文件"
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java"
    --8<-- "docs/study/android/source/ZygoteConnection.java"
    ```

比对一下可以发现，这里和 SystemServer 的孵化十分相似

=== "ZygoteConnection"
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java"
    --8<-- "docs/study/android/source/ZygoteConnection.java:234:257"
    ```
=== "ZygoteInit"
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
    --8<-- "docs/study/android/source/ZygoteInit.java:779:799"
    ```

而在调用的 forkAndSpecialize 和 forkSystemServer 更为相似
=== "forkAndSpecialize"
    ```java title="/frameworks/base/core/java/com/android/internal/os/Zygote.java"
    --8<-- "docs/study/android/source/Zygote.java:133:155"
    ```

=== "forkSystemServer"
    ```java title="/frameworks/base/core/java/com/android/internal/os/Zygote.java"
    --8<-- "docs/study/android/source/Zygote.java:185:201"
    ```

在 Native 层中则是直接调用了 ForkAndSpecializeCommon

```C++ title="/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp" hl_lines="5-9"
--8<-- "docs/study/android/source/com_android_internal_os_Zygote.cpp:870:901"
```

至此我们可以全心投入常规进程的孵化分析，而 SystemServer 的差异我们放在后续讨论。

```C++ title="/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp"
--8<-- "docs/study/android/source/com_android_internal_os_Zygote.cpp:538:780"
```

## System Server


## Xposed

??? quote "参考资料"
    - [Lsposed 技术原理探讨 && 基本安装使用 ](https://bbs.kanxue.com/thread-274572.htm#msg_header_h3_0){target="_blank" rel="noopener"}
