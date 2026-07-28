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

我们先只看主屏幕的链路：

```java title="/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java" hl_lines="6 12 21 29"
// line 1296-1303
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1296:1303"
// line 1315-1321
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1315:1321"
// line 1328-1333
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1328:1333"
// line 1346-1347
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1346:1347"
// line 1402-1403
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1402:1403"
```

`ActivityStartController.startHomeActivity()` 的参数 `homeIntent` 是由 `ActivityTaskManagerService` 构造，再经过 PackageManager 解析后补充成显式 Intent。

在 `startHomeOnTaskDisplayArea` 会先调用 `getHomeIntent()` 拿到一个 `homeIntent` 再传入 `resolveHomeActivity()` 拿到 `aInfo`：

```java title="/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java" hl_lines="10 11"
// line 1346-1347
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1346:1347"
// line 1363-1370
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1363:1370"
```

首先来看 `getHomeIntent()` ：

```java title="/frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java" hl_lines="4 8"
// line 564-567
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java:564:567"
// line 5609-5617
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java:5609:5617"
```

构建了一个带有 Home 匹配条件的**隐式 Intent**：

```text
Intent {
    action    = android.intent.action.MAIN
    category  = android.intent.category.HOME
    component = null
}
```

然后来看 `resolveHomeActivity()`：

```java title="/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java" hl_lines="4 13 16 29 30 31"
// line 1413-1443
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1413:1443"

--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1439:1443"
```

前面 `getHomeIntent()` 没有指定 Component，所以会进入隐式 Intent 的解析分支 `resolveIntent()`，这是一个通用的 Activity Intent 解析入口。它根据 Intent 中的 action、category、data、MIME type、package、component 等约束，在指定用户下找出候选 Activity，并最终返回一个“最佳匹配”的 `ResolveInfo`，具体细节就不在此深入了。

aosp 中默认桌面是 Launcher3，那么解析结果应该对应为 `aInfo.applicationInfo.packageName = com.android.launcher3` `aInfo.name = com.android.launcher3.Launcher`

在正式调用 `startHomeActivity()` 之前，`startHomeOnTaskDisplayArea()` 会把解析到的 Launcher 组件写回同一个 Intent：

```java title="/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java" hl_lines="6 18 19"
// line 1346-1347
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1346:1347"
// line 1389-1403
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java:1389:1403"
```

此时 `homeIntent` 从隐式 Intent 变成了显式 Intent：

```text
Intent {
    action    = android.intent.action.MAIN
    category  = android.intent.category.HOME
    component = com.android.launcher3/.Launcher
}
```

得到显式的 Home Intent 后，进入 `ActivityStartController`：

```java title="/frameworks/base/services/core/java/com/android/server/wm/ActivityStartController.java" hl_lines="10 15 18-20 35-41"
// line 167-185
--8<-- "docs/study/android/source/frameworks/base/services/core/java/com/android/server/wm/ActivityStartController.java:167:206"
```

这里为启动设定了一些参数，然后通过 `obtainStarter().execute()` 进入通用的应用启动流程

这里我们先不继续深入，而是假装桌面已经启动完毕，我们先来看看桌面是如何处理用户点击，系统又是如何再一次的走到这里，最后我们在随着普通应用的启动流程再深入这套通用流程后续操作

## 2. 从点击到应用启动



