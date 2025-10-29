# 杂货铺

本文档收集一些零散的知识点

---

## 从 Zygote 到 Xposed 框架

??? quote "参考资料"
    - [Zygote 进程简介](https://source.android.google.cn/docs/core/runtime/zygote?hl=zh-cn){target="_blank"}
    - [谈谈对Android中Zygote的理解](https://zhuanlan.zhihu.com/p/260414370){target="_blank"}
    - [Android启动系列之一：init进程和Zygote进程](https://cloud.tencent.com/developer/article/2415718){target="_blank"}

Zygote 翻译为“受精卵”，在 Android 系统中负责创建新的应用进程。[官方文档](https://source.android.google.cn/docs/core/runtime/zygote?hl=zh-cn){target="_blank"}

为什么存在 Zygote 进程？

- 为了提高应用启动速度，Zygote 进程在系统启动时就会创建，它会预加载一些常用的类和资源（如DVM，ART等），这样当新的应用进程需要启动时，就可以直接从 Zygote 进程中 fork 一个新的进程，而不需要重新加载这些类和资源。
- 起初Zygote进程名称并不是“zygote”，而是“app_process”，这个名称在Android.mk中定义的。Zygote进程启动后，Linux系统下的pctrl系统会调用app_process，将其名称换成“zygote”


