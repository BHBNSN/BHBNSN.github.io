# Unicorn Engine

Unicorn Engine 是一个基于 qemu 的轻量级多平台、多架构的反汇编引擎，支持 x86、x86_64、ARM、AArch64、MIPS、PowerPC、SPARC 等多种架构。它提供了一个简单的 API，可以用于模拟和调试二进制代码。

Unicorn 只负责模拟 CPU 的指令执行，因此在学习使用时候需要手动模拟操作系统为 cpu 使用。

!!! quote "相关链接"
    * [Unicorn Engine 官方文档](https://www.unicorn-engine.org/docs/){target="_blank" rel="noopener"}
    * [Unicorn Engine GitHub 仓库](https://github.com/unicorn-engine/unicorn){target="_blank" rel="noopener"}
    * [看雪-深入浅出 Unicorn 框架学习](https://bbs.kanxue.com/thread-289502.htm){target="_blank" rel="noopener"}

## 安装
最简单的方法就是通过 pip 安装 Unicorn Engine

```bash
pip install unicorn
```

Unicorn 还有两个同源项目，分别是 Keystone Engine（一个汇编引擎）和 Capstone Engine（一个反汇编引擎），它们也可以通过 pip 安装：

```bash
pip install keystone-engine
pip install capstone
```

当然还以上都可以自己编译，官方文档里有详细的说明。

## 基础使用

### 示例代码
很多博客还有官方文档都使用的下面这段代码介绍基础使用

```python
#!/usr/bin/python

from __future__ import print_function
from unicorn import *
from unicorn.x86_const import *

# code to be emulated
X86_CODE32 = b"\x41\x4a" # INC ecx; DEC edx

# memory address where emulation starts
ADDRESS = 0x1000000

print("Emulate i386 code")
try:
    # Initialize emulator in X86-32bit mode
    mu = Uc(UC_ARCH_X86, UC_MODE_32)

    # map 2MB memory for this emulation
    mu.mem_map(ADDRESS, 2 * 1024 * 1024)

    # write machine code to be emulated to memory
    mu.mem_write(ADDRESS, X86_CODE32)

    # initialize machine registers
    mu.reg_write(UC_X86_REG_ECX, 0x1234)
    mu.reg_write(UC_X86_REG_EDX, 0x7890)

    # emulate code in infinite time & unlimited instructions
    mu.emu_start(ADDRESS, ADDRESS + len(X86_CODE32))

    # now print out some registers
    print("Emulation done. Below is the CPU context")

    r_ecx = mu.reg_read(UC_X86_REG_ECX)
    r_edx = mu.reg_read(UC_X86_REG_EDX)
    print(">>> ECX = 0x%x" %r_ecx)
    print(">>> EDX = 0x%x" %r_edx)

except UcError as e:
    print("ERROR: %s" % e)
```
这段代码可以很简单且直观的大致看出 unicorn 的使用框架和能处理的任务：

1. 初始化模拟器，指定架构和模式
2. 分配内存大小和地址并写入要模拟的机器码
3. 初始化寄存器
4. 开始模拟
5. 读取最终结果寄存器的值

我们很直观的感受到 Unicorn 就是一个可以模拟执行机器码的 cpu 模拟器。

### 模拟构建流程
当我们希望使用 Unicorn 来构建一个模拟器来模拟一段机器码时，正常来说，我们应该完成以下这些步骤：

#### 1. 模拟器初始化
使用 `Uc()` 可以初始化一个模拟器，此时我们需要选择我们需要的 cpu 架构，比如我们需要使用 32bit 的 x86 架构，那么我们构建模拟器时就应该选择 `mu = Uc(UC_ARCH_X86, UC_MODE_32)` 来初始化模拟器。
#### 2. 内存分配与写入
- 我们需要手动为模拟器分配内存空间 `mu.mem_map(ADDRESS, 2 * 1024 * 1024)` 这个接口会为第一个参数的地址分配第二个参数大小的内存空间，当我们需要额外开辟堆栈在其他起始地址的内存空间时，我们可以多次调用 `mu.mem_map()` 来往其他多个起始地址出分配内存。

- 使用 `mu.mem_write(ADDRESS, X86_CODE32)` 可以往第一个参数所代表的地址写入第二个参数的值。
#### 3. 寄存器初始化
使用 `mu.reg_write()` 可以初始化寄存器的值，比如 `mu.reg_write(UC_X86_REG_ECX, 0x1234)`。
#### 4. 开始模拟
使用 `mu.emu_start()` 可以开始模拟代码的执行，第一个参数传入起始地址，第二个参数传入最终地址。
#### 5. 读取最终结果寄存器的值
使用 `mu.reg_read()` 可以读取寄存器的值，比如 `r_ecx = mu.reg_read(UC_X86_REG_ECX)`。

## 进阶使用

### 汇编转机器码
在上述范例中我们需要手写机器码，其实 Unicorn 有一个同源兄弟专门可以将汇编代码转换成机器码的引擎 Keystone Engine，我们可以使用它来生成机器码：

```python
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN

CODE_ADDR  = 0x100000

ASM_CODE = r"""
start:
    cbz     x1, done

loop:
    ldrb    w2, [x0]
    add     w2, w2, #1
    strb    w2, [x0], #1
    subs    x1, x1, #1
    b.ne    loop

done:
    ret
"""


def assemble_arm64(asm_code: str, base_addr: int) -> bytes:
    """用 Keystone 组装 ARM64 汇编"""
    ks = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
    encoding, _ = ks.asm(asm_code, addr=base_addr)
    return bytes(encoding)

code = assemble_arm64(ASM_CODE, CODE_ADDR)
```
这里生成的 code 就可以直接像上面 `mu.mem_write(CODE_ADDR, code)` 一样作为机器码写入内存中进行模拟了。

### 反汇编机器码
在运行时，我们从内存中读取到机器码时，我们可以使用同源兄弟 Capstone Engine 来将机器码反汇编成汇编指令：

```python
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

def disasm_one(md: Cs, code: bytes, address: int) -> str:
    """反汇编单条指令"""
    insns = list(md.disasm(code, address))
    if not insns:
        return f"0x{address:x}: <invalid>"
    insn = insns[0]
    return f"0x{insn.address:016x}: {insn.mnemonic:<8} {insn.op_str}"

md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
raw = bytes(mu.mem_read(address, size))
line = disasm_one(md, raw, address)
print(line)
```

### HOOK
Unicorn 还提供了一些 hook 接口，可以在模拟过程中 hook 指令执行、内存读写等事件。

```python
    # ========= hook：代码执行 =========
    def hook_code(uc: Uc, address: int, size: int, user_data) -> None:
        raw = bytes(uc.mem_read(address, size))
        line = disasm_one(md, raw, address)

        x0 = uc.reg_read(UC_ARM64_REG_X0)
        x1 = uc.reg_read(UC_ARM64_REG_X1)
        x2 = uc.reg_read(UC_ARM64_REG_X2)

        print(f"{line}    | X0=0x{x0:x} X1=0x{x1:x} X2=0x{x2:x}")

    # ========= hook：内存读 =========
    def hook_mem_read(uc: Uc, access: int, address: int, size: int, value: int, user_data) -> None:
        print(f"    [mem] READ  addr=0x{address:x}, size={size}")

    # ========= hook：内存写 =========
    def hook_mem_write(uc: Uc, access: int, address: int, size: int, value: int, user_data) -> None:
        print(f"    [mem] WRITE addr=0x{address:x}, size={size}, value=0x{value:x}")

    mu.hook_add(UC_HOOK_CODE, hook_code)
    mu.hook_add(UC_HOOK_MEM_READ, hook_mem_read)
    mu.hook_add(UC_HOOK_MEM_WRITE, hook_mem_write)
```
上面这段代码展示了如何使用 Unicorn 的 hook 接口来 hook 代码执行、内存读写事件，在 hook 函数中我们可以获取当前指令的地址、大小、寄存器值等信息，并且在代码执行到特定地址时停止模拟。
