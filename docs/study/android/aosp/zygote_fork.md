# Zygote 孵化流程

!!! note "相关链接"
    - [Linux 进程 fork 机制](../../../blog/posts/linux_fork.md#linux-fork)

!!! warning "本文暂未考虑 fork child zygote 的情况"

## 1. ZygoteInit 初始化
ZygoteInit.java 在 /frameworks/base/core/java/com/android/internal/os/

ZygoteInit 的主要流程是预加载资源，如果参数里有 `--start-system-server` 则孵化 SystemServer，最后启动 `runSelectLoop` 进入循环等待的创建请求。

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
// 检查参数 line 848:860
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:848:860"
// 预加载资源供后续孵化用 line 879:889
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:879:889"
// 启动 runSelectLoop 循环等待创建请求 line 917:933
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:917:933"
```

`ZygoteInit` 的 main 启动中会判断了传入参数有没有 `--start-system-server`，如果有则会孵化 SystemServer 进程。

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
// line 817
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:817:817"
// 检查 argv 里是否存在 `--start-system-server` 设置 startSystemServer 标志 line 848:850
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:848:850"
// 孵化 SystemServer line 902:913
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:902:913"
```

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java" hl_lines="27 45"
// zygote 启动时请求的 forkSystemServer 方法 line 685:692
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:687:694"
// 配置 fork 相关参数 line 718:730
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:720:732"
// 调用 Zygote.forkSystemServer 方法 line 776:799
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:778:801"
```

## 2. Zygote 监听处理其他进程的 fork 请求

当别的应用需要孵化一个新的进程时，会通过本地 socket 向 Zygote 发送请求，Zygote 收到请求后会执行 fork 来创建新的进程。

具体流程如下：

1.  **`ZygoteServer` 监听请求**
    </br>
    上文提到 `ZygoteInit` 启动了 `runSelectLoop` 方法负责监听和管理请求，代码中可以看出将具体的处理工作交给 `ZygoteConnection`。
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java" hl_lines="52 83 86-87"
    // line 388:434
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java:388:434"
    // ...
    // line 485:548
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteServer.java:485:548"
    ```
    上面通过 `Os.poll` 来监听套接字的事件，当有新的连接时，创建一个 `ZygoteConnection` 来处理这个连接。
2.  **`ZygoteConnection` 处理连接**
    </br>
    `ZygoteConnection` 负责解析请求参数，并调用 `Zygote.forkAndSpecialize` 来执行 `fork` 操作。
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java" hl_lines="32 51-52"
    // line 111:138
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java:111:138"
    // ...
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

## 4. Fork 完成到应用进程启动
上文中在 fork 完成后，在子进程中会走进 `handleChildProc` 或 `handleSystemServerProcess` 我们来看这两个方法

=== "handleChildProc"
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java"
    // line 504:536
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java:504:536"
    ```
=== "handleSystemServerProcess"
    ```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
    // line 484:563
    --8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:484:563"
    ```

可以看出它们都会先设置
1. 进程的名字

而 `system server` 还会额外设置
1. 设置 umask，限制 system_server 创建文件时的默认权限
2. 处理 SYSTEMSERVERCLASSPATH 提前准备自己的 classpath
3. 创建 system_server 使用的 ClassLoader 用于加载 `SYSTEMSERVERCLASSPATH` 中的 jar
4. 处理 system server / boot classpath profile，用于 profile 采集和启动优化

最后它们都会进入 `ZygoteInit.zygoteInit`

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
// line 962:989
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:962:989"
// ...
// line 1001
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:1001:1001"
```

在这里，可以看出先走进了 jni 方法 `nativeZygoteInit` 通过调用当前 `AndroidRuntime` 对象的 `onZygoteInit()`启动了 `binder` 线程池

```java title="/frameworks/base/core/jni/AndroidRuntime.cpp"
// line 275:278
--8<-- "docs/study/android/source/frameworks/base/core/jni/AndroidRuntime.cpp:275:278"
```

调用了当前 AndroidRuntime 对象的 onZygoteInit()，这实际是一个虚函数，在 `frameworks/base/cmds/app_process/app_main.cpp` 中实现了这个函数：

```C++ title="/frameworks/base/cmds/app_process/app_main.cpp"
// line 343:344
--8<-- "docs/study/android/source/frameworks/base/cmds/app_process/app_main.cpp:92:97"
```

执行完后，进入 `RuntimeInit.zygoteInit` 来启动应用的 main 方法

```java title="frameworks/base/core/java/com/android/internal/os/RuntimeInit.java"
// line 376:395
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/RuntimeInit.java:376:395"
```

`zygoteInit` 先配置 sdk 等环境，然后调用 `findStaticMain`

```java title="frameworks/base/core/java/com/android/internal/os/RuntimeInit.java"
// line 308:353
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/RuntimeInit.java:308:353"
```

通过 ClassLoader 加载目标类，然后反射找到它的 public static main(String[] args)

```java title="frameworks/base/core/java/com/android/internal/os/RuntimeInit.java"
// line 575:606
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/RuntimeInit.java:575:606"
```

这里将目标类的 main 方法保存到 `Runnable` `MethodAndArgsCaller` 中了，并且在 run 中能通过 `Method.invoke` 来调用这个 main 方法

这里的 `Runnable` 会一直返回到开头的 `ZygoteInit` 的 `main` 中调用 `run` 方法来启动

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java" hl_lines="10 32"
// line 902:933
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:902:933"
```

!!! quote "参考资料"
    - [Linux 系统调用 —— fork 内核源码剖析](https://www.cnblogs.com/chenxinshuo/p/11968329.html){target="_blank" rel="noopener"}