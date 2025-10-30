# 邦邦邦邦 真神来了 Frida

## 什么是frida

> frida 是一款基于 python+javascript 的 hook 框架，可运行在 android、ios、linux、win等各个平台，主要使用的动态二进制插桩技术。

[项目地址](https://github.com/frida/frida)

[官网及使用文档](https://frida.re/)

## 基础配置

1. 安装frida
    ```bash
    pip install frida-tools
    ```
2. 在目标设备配置对应版本的frida-server并运行
3. 测试frida正常连接
    ```bash
    frida-ps
    ```

## 基础使用

- frida使用python将javascript脚本注入到目标进程中运行，从而实现hook功能
- javascript基础语法较为简单，但是在frida中有大量自定义接口，需通过文档与脚本阅读理解学习