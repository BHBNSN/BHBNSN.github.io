# Android 基础知识

本文档收集一些理论性知识，较为零碎，但是最终编织成一张大网。

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

Zygote 是一个重要的进程，它预加载了大量的资源和类库，使得新进程能够快速启动。Zygote 通过 `fork` 自身来创建新的进程，这些新进程继承了 Zygote 预加载的资源，从而大大加快了应用的启动速度。关于 Zygote 的详细启动流程和实现细节，可以参考 aosp 解读文章中的 [Zygote 启动流程](aosp/zygote_startup.md) 和 [zygote 孵化流程](aosp/zygote_fork.md)。

在某些双架构系统中，会生成两个 Zygote 进程（一个 64 位，一个 32 位），一般我们称 64 位的为主要 Zygote（primary zygote），32 位的为次要 Zygote（secondary zygote）。它们的启动流程基本相同。


## Xposed

??? quote "参考资料"
    - [Lsposed 技术原理探讨 && 基本安装使用 ](https://bbs.kanxue.com/thread-274572.htm#msg_header_h3_0){target="_blank" rel="noopener"}
