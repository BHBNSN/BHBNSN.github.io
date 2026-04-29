# 应用启动流程

## 1. 桌面应用的启动

我们每天看到的桌面实际上也是一个 App，aosp 中默认为 Launcher3，位于 `/packages/apps/Launcher3/`。

在 `SystemServer.run` 的 `startOtherServices` 中会进入 `ActivityManagerService.systemReady` 从而调用 `mAtmInternal.startHomeOnAllDisplays(currentUserId, "systemReady");`

```java title="/frameworks/base/services/java/com/android/server/SystemServer.java" hl_lines="10"
// line 796-797
--8<-- "docs/study/android/source/frameworks/base/services/java/com/android/server/SystemServer.java:796:797"
//...
// line 984-994 调用 startOtherServices 方法
--8<-- "docs/study/android/source/frameworks/base/services/java/com/android/server/SystemServer.java:984:994"
```

```java title="/frameworks/base/services/java/com/android/server/SystemServer.java" hl_lines="15"
// line 1513-1518
--8<-- "docs/study/android/source/frameworks/base/services/java/com/android/server/SystemServer.java:1513:1518"
//...
// line 3217-3223 调用 mActivityManagerService.systemReady
--8<-- "docs/study/android/source/frameworks/base/services/java/com/android/server/SystemServer.java:3217:3223"
```

```java title="/frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java" hl_lines="18"
// line 8970-8975
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java:8970:8975"
//...
// line 9129-9139 调用 mAtmInternal.startHomeOnAllDisplays
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java:9129:9139"
```

这里调用的是 `ActivityTaskManagerInternal`。它是系统进程内部使用的抽象接口，真正的实现是 `ActivityTaskManagerService` 内部的 `LocalService`。AMS 通过 `LocalServices.getService(ActivityTaskManagerInternal.class)` 拿到这个内部服务，因此这里最终会进入 `ActivityTaskManagerService.LocalService.startHomeOnAllDisplays()`。
```java title="/frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java" hl_lines="7"
// line 6038
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java:6038:6038"
// line 6636-6641
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java:6636:6641"
```

在这里进入了 `RootWindowContainer` 的 `startHomeOnAllDisplays`