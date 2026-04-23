# Zygote 孵化流程

!!! note "相关链接"
    - [Linux 进程 fork 机制](../../../blog/posts/linux_fork.md#linux-fork)

## 1. System Server 请求 fork

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java" hl_lines="27 45"
// zygote 启动时请求的 forkSystemServer 方法 line 685:692
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:687:694"
// 配置 fork 相关参数 line 718:730
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:720:732"
// 调用 Zygote.forkSystemServer 方法 line 776:799
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:778:801"
```

## 2. Zygote 监听处理其他进程的 fork 请求

当别的应用需要孵化一个新的进程时，会通过本地套字节(socket)向 Zygote 发送请求，Zygote 收到请求后会执行 fork 来创建新的进程。

具体代码处理流程如下：

1.  **`ZygoteServer` 监听请求**
    </br>
    [上文](zygote_startup.md#3-zygoteinit)提到 `ZygoteInit` 启动了 `runSelectLoop` 方法负责监听和管理请求，代码中可以看出将具体的处理工作交给 `ZygoteConnection`。
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java" hl_lines="27 32"
    // runSelectLoop 方法 line 388:394
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java:388:394"
    // runSelectLoop 方法 line 508:521
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java:508:521"
    ```

2.  **`ZygoteConnection` 处理连接**
    </br>
    `ZygoteConnection` 负责解析请求参数，并调用 `Zygote.forkAndSpecialize` 来执行 `fork` 操作。
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java" hl_lines="2 21-22"
    // 可以看到调用 Native 层的 fork 逻辑 line 248:276
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java:248:276"
    ```

3.  **`Zygote` 执行 Fork**
    </br>
    `forkAndSpecialize` 方法会调用 `native` 方法 `nativeForkAndSpecialize` 来真正执行 `fork`。
    
    我们可以对比一下孵化普通应用进程 (`forkAndSpecialize`) 和孵化 `SystemServer` (`forkSystemServer`) 的代码，它们最终都依赖 `native` 方法。

    === "forkAndSpecialize (应用进程)"
        ```java title="/frameworks/base/core/java/com/android/internal/os/Zygote.java"
        // line 368:403
        --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/Zygote.java:368:403"
        ```

    === "forkSystemServer (系统服务)"
        ```java title="/frameworks/base/core/java/com/android/internal/os/Zygote.java"
        // line 501:517
        --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/Zygote.java:501:517"
        ```

## 3. Native 层：执行 Fork

Java 层的 `native` 方法最终会调用到 C++ 层的 `ForkCommon` 函数来完成进程的创建。

=== "nativeForkAndSpecialize"
    ```C++ title="/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp" hl_lines="44-45"
    // line 2530:2585
    --8<-- "docs/study/android/source/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp:2530:2585"
    ```
=== "nativeForkSystemServer"
    ```C++ title="/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp" hl_lines="22-25"
    // line 2587:2643
    --8<-- "docs/study/android/source/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp:2587:2643"
    ```

可以看到，它们都调用了 `ForkCommon` 方法。

我们来看 `ForkCommon` 的实现方法：

```C++ title="/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp" hl_lines="10"
// line 2421:2523
--8<-- "docs/study/android/source/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp:2421:2427"
//...
--8<-- "docs/study/android/source/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp:2477:2484"
//...
--8<-- "docs/study/android/source/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp:2522:2523"
```

ForkCommon 调用了底层的 `fork()` 方法，并且接受了返回的 pid。

!!! quote "参考资料"
    - [Linux 系统调用 —— fork 内核源码剖析](https://www.cnblogs.com/chenxinshuo/p/11968329.html){target="_blank" rel="noopener"}