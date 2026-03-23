# Zygote 启动流程

!!! note "相关链接"
    - [Android 启动流程](../theory.md#android_1)

!!! question "什么是 Zygote 进程？"
    你应该去[理论篇](../theory.md#zygote)了解相关信息，简单来说，Zygote 是 Android 系统中一个特殊的进程，负责孵化（fork）新的应用进程。它预加载了大量的资源和类库，使得新进程能够快速启动。

## 1. init 进程启动 app_process

按照我们[之前的介绍](../theory.md#3-native-user-space)，Zygote 是由 init 进程启动的。我们可以在 init.rc 中找到对应启动：

```bash title="/system/core/rootdir/init.rc"
#line 526:528 
--8<-- "docs/study/android/source/system/core/rootdir/init.rc:526:528"
#line 1087:1095
--8<-- "docs/study/android/source/system/core/rootdir/init.rc:1087:1095"
```
系统会启动 zygote 和 zygote_secondary 服务。这两个服务声明于以下配置文件中： 

=== "init.zygote32"
    ```bash title="/system/core/rootdir/init.zygote32.rc"
    --8<-- "docs/study/android/source/system/core/rootdir/init.zygote32.rc"
    ```
=== "init.zygote64"
    ```bash title="/system/core/rootdir/init.zygote64.rc"
    --8<-- "docs/study/android/source/system/core/rootdir/init.zygote64.rc"
    ```
=== "init.zygote64_secondary"
    ```bash title="/system/core/rootdir/init.zygote64_32.rc"
    --8<-- "docs/study/android/source/system/core/rootdir/init.zygote64_32.rc"
    ```

可以看出，zygote 服务会启动 `/system/bin/app_process(64)` 进程，附带的参数是`--zygote --start-system-server`。

## 2. app_process 启动 ZygoteInit

??? failure "~~源码网站上并没有这个文件，我从 Android 9 的实体机中提取了这个文件，是一个 ELF 文件，IDA 启动。~~"
    ```C++ title="/system/bin/app_process64 main()"
      if ( (v55 & 0x100000000LL) != 0 )
      {
        p_com.android.internal.os.RuntimeInit = "com.android.internal.os.ZygoteInit";
        v42 = 1;
      }
      // ...
      android::AndroidRuntime::start(v61, p_com.android.internal.os.RuntimeInit, v58, v42);
    ```
    在经过一系列参数比对后，启动了java层`com.android.internal.os.ZygoteInit`。

app_process 对应的源码是 app_main.cpp
```C++ title="/frameworks/base/cmds/app_process/app_main.cpp"
//line 263:282
--8<-- "docs/study/android/source/frameworks/base/cmds/app_process/app_main.cpp:263:282"
//line 309:311
--8<-- "docs/study/android/source/frameworks/base/cmds/app_process/app_main.cpp:309:311"
//line 335:343
--8<-- "docs/study/android/source/frameworks/base/cmds/app_process/app_main.cpp:335:343"
```

可以看出，在`--zygote --start-system-server`参数下，最终会启动Java层的 `com.android.internal.os.ZygoteInit` 类，并将`start-system-server`放在arg中传入。

## 3. ZygoteInit 启动流程
ZygoteInit.java 在 /frameworks/base/core/java/com/android/internal/os/

ZygoteInit 的主要流程是预加载资源，如果参数里有 `--start-system-server` 则孵化 SystemServer，最后进入循环等待 AMS 的创建请求。

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
// 检查参数 line 848:860
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:848:860"
// 预加载资源供后续孵化用 line 879:889
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:879:889"
// 循环等待创建请求 line 917:919
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:917:919"
```

main 启动中会判断了传入参数有没有 `--start-system-server`，如果有则会孵化 SystemServer 进程。

```java title="/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java"
// line 817
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:817:817"
// 检查 argv 里是否存在 `--start-system-server` 设置 startSystemServer 标志 line 848:850
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:848:850"
// 孵化 SystemServer line 902:913
--8<-- "docs/study/android/source/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java:902:913"
```

## 4. 结语
至此，我们已经了解了 Zygote 进程的启动流程，从 init 启动 app_process，再到 app_process 启动 ZygoteInit，最后 ZygoteInit 进入循环等待创建请求的阶段。下一步就将探索 Zygote 如何孵化 SystemServer 和处理来自 AMS 的请求并孵化新的应用进程。

!!! quote "参考资料"
    - [Java 世界的盘古和女娲 —— Zygote](https://juejin.cn/post/6844903955177144333){target="_blank" rel="noopener"}
    - [Android Zygote启动流程](https://juejin.cn/post/7359405716090634251){target="_blank" rel="noopener"}
    - [深入研究源码：Android10.0系统启动流程（三）：Zygote](https://zhuanlan.zhihu.com/p/350204845){target="_blank" rel="noopener"}