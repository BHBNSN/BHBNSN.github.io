# CISCN2026 初赛



## babygame

godot程序，用gdre解包

flag.gdc看到flag是aes加密与密文比较

```
extends CenterContainer

@onready var flagTextEdit: Node = $PanelContainer / VBoxContainer / FlagTextEdit
@onready var label2: Node = $PanelContainer / VBoxContainer / Label2

static var key = "FanAglFanAglOoO!"
var data = ""

func _on_ready() -> void :
    Flag.hide()

func get_key() -> String:
    return key

func submit() -> void :
    data = flagTextEdit.text

    var aes = AESContext.new()
    aes.start(AESContext.MODE_ECB_ENCRYPT, key.to_utf8_buffer())
    var encrypted = aes.update(data.to_utf8_buffer())
    aes.finish()

    if encrypted.hex_encode() == "d458af702a680ae4d089ce32fc39945d":
        label2.show()
    else:
        label2.hide()

func back() -> void :
    get_tree().change_scene_to_file("res://scenes/menu.tscn")
```

在game_manager.gdc中将key的A换成了B

```
extends Node

@onready var fan = $"../Fan"

var score = 0

func add_point():
    score += 1
    if score == 1:
        Flag.key = Flag.key.replace("A", "B")
        fan.visible = true

```

直接在godot里面建个项目，源库跑一下解密（cyberchef跑不出来不知道为什么）

```
extends Node2D

func _ready() -> void:
	var key := "FanBglFanBglOoO!"
	var ct_hex := "d458af702a680ae4d089ce32fc39945d"

	# 十六进制字符串 -> PackedByteArray
	var ct: PackedByteArray = ct_hex.hex_decode()

	var aes := AESContext.new()
	var err := aes.start(AESContext.MODE_ECB_DECRYPT, key.to_utf8_buffer())
	if err != OK:
		push_error("AES start failed: %s" % err)
		return

	var pt: PackedByteArray = aes.update(ct)
	aes.finish()
	

	print("pt bytes = ", pt)
	print("pt hex   = ", pt.hex_encode())
	print("pt utf8  = ", pt.get_string_from_utf8())
	print("pt ascii = ", pt.get_string_from_ascii())
```

pt bytes = [119, 79, 87, 126, 121, 111, 117, 65, 114, 101, 103, 114, 69, 97, 84, 33]
pt hex   = 774f577e796f75417265677245615421
pt utf8  = wOW~youAregrEaT!
pt ascii = wOW~youAregrEaT!

## wasm-login

html的auth封装在，其中还有检测满足 check.startsWith("ccaf33e3512e31f3")

```html
import { authenticate } from "./build/release.js";
```

而release.js中指向了release.wasm

```javascript
  const adaptedExports = Object.setPrototypeOf({
    authenticate(username, password) {
      // assembly/index/authenticate(~lib/string/String, ~lib/string/String) => ~lib/string/String
      username = __retain(__lowerString(username) || __notnull());
      password = __lowerString(password) || __notnull();
      try {
        return __liftString(exports.authenticate(username, password) >>> 0);
      } finally {
        __release(username);
      }
    },
  }, exports);
```

使用wasm2c可以将wasm转c（不过还不如ida中好看）

从 release.wasm.map 可直接恢复 AssemblyScript 源码，核心入口是 authenticate(username, password)：

1. encodedPassword = Base64(password)
2. timestamp = Date.now().toString()
3. message = {"username": "...", "password": ""}
4. signature = signMessage(message, timestamp)
5. 返回最终 authData：{"username":...,"password":...,"signature":...}

签名算法

- `signMessage(message, secret)`：
    - messageBytes = UTF8(message)，`secretBytes = UTF8(secret)`，其中 `secret` 明确就是时间戳字符串。
    - 调用 `hmacSHA256(secretBytes, messageBytes)`，结果再做 Base64，得到 `signature`。
- hmacSHA256(key, message) 实现魔改 HMAC
    1. 常量是是 0x76/0x3c
    2. outer 输入拼接顺序是反的
- `paddedKey` 处理：若 `key.byteLength > 64` 会先 `SHA256(key)` 放进 64 字节缓冲（其余补 0）；否则直接拷贝 key 并补 0 到 64。

题目提示时间12.22 0点-7点（凌晨）将wasm中的auth函数复现并爆破

```javascript
import { readFileSync } from 'node:fs';
import os from 'node:os';
import crypto from 'node:crypto';
import {
  Worker,
  isMainThread,
  parentPort,
  workerData,
} from 'node:worker_threads';

const PREFIX = 'ccaf33e3512e31f3';

function md5Hex(text) {
  return crypto.createHash('md5').update(text, 'utf8').digest('hex');
}

function buildWasmAuth() {
  const wasmBytes = readFileSync(new URL('./build/release.wasm', import.meta.url));

  let nowMs = Date.now();
  const imports = {
    env: {
      abort(message, fileName, lineNumber, columnNumber) {
        throw new Error(`abort(${message}, ${fileName}, ${lineNumber}, ${columnNumber})`);
      },
      'Date.now': () => nowMs,
    },
  };

  return WebAssembly.instantiate(wasmBytes, imports).then(({ instance }) => {
    const { exports } = instance;
    const memory = exports.memory;

    function liftString(pointer) {
      if (!pointer) return null;
      const u32 = new Uint32Array(memory.buffer);
      const u16 = new Uint16Array(memory.buffer);
      const lengthU16 = u32[(pointer - 4) >>> 2] >>> 1;
      const start = pointer >>> 1;
      const end = start + lengthU16;
      let out = '';
      let i = start;
      while (end - i > 1024) {
        out += String.fromCharCode(...u16.subarray(i, i + 1024));
        i += 1024;
      }
      out += String.fromCharCode(...u16.subarray(i, end));
      return out;
    }

    function lowerString(value) {
      if (value == null) return 0;
      const length = value.length;
      const pointer = exports.__new((length << 1) >>> 0, 2) >>> 0;
      const u16 = new Uint16Array(memory.buffer);
      const start = pointer >>> 1;
      for (let i = 0; i < length; i++) u16[start + i] = value.charCodeAt(i);
      return pointer;
    }

    function pinString(str) {
      const ptr = lowerString(str);
      if (exports.__pin) exports.__pin(ptr);
      return ptr;
    }

    const uPtr = pinString(workerData?.username ?? 'admin');
    const pPtr = pinString(workerData?.password ?? 'admin');

    function authenticateAt(tsMs) {
      nowMs = tsMs;
      const retPtr = exports.authenticate(uPtr >>> 0, pPtr >>> 0) >>> 0;
      return liftString(retPtr);
    }

    return {
      exports,
      authenticateAt,
    };
  });
}

function formatUtc(ms) {
  return new Date(ms).toISOString();
}

if (isMainThread) {
  const username = 'admin';
  const password = 'admin';


  const startUtc = Date.UTC(2025, 11, 21, 16, 0, 0, 0); // 2025-12-22 00:00:00 CST
  const endUtc = Date.UTC(2025, 11, 21, 21, 0, 0, 0) - 1; // 2025-12-22 04:59:59.999 CST

  const argWorkers = process.argv[2] ? Number(process.argv[2]) : undefined;
  const workers = Number.isFinite(argWorkers) && argWorkers > 0 ? Math.floor(argWorkers) : os.cpus().length;

  (async () => {
    const { authenticateAt } = await buildWasmAuth();
    const samples = [startUtc, startUtc + 1, startUtc + 1234567];
    for (const ts of samples) {
      const jsonText = authenticateAt(ts);
      const jsonTrim = jsonText.trim();
      const canonical = JSON.stringify(JSON.parse(jsonText));
      const a = md5Hex(jsonTrim);
      const b = md5Hex(canonical);
      if (a !== b || jsonTrim !== canonical) {
        console.error('一致性检查失败：不能直接用 jsonText.trim() 做 canonical');
        console.error({ ts, a, b, jsonTrimEqualCanonical: jsonTrim === canonical });
        process.exit(2);
      }
    }

    console.log('OK: jsonText.trim() == JSON.stringify(JSON.parse(jsonText))，启用快速爆破');
    console.log('range(UTC):', startUtc, '->', endUtc, 'count', endUtc - startUtc + 1);
    console.log('range(ISO):', formatUtc(startUtc), '->', formatUtc(endUtc));
    console.log('workers:', workers, 'PREFIX:', PREFIX);

    const shared = new SharedArrayBuffer(4);
    const stop = new Int32Array(shared);

    const total = endUtc - startUtc + 1;
    const chunk = Math.floor(total / workers);

    let finished = 0;
    const workerList = [];

    function stopAll() {
      Atomics.store(stop, 0, 1);
      for (const w of workerList) w.terminate();
    }

    for (let i = 0; i < workers; i++) {
      const s = startUtc + i * chunk;
      const e = (i === workers - 1) ? endUtc : (s + chunk - 1);
      const w = new Worker(new URL(import.meta.url), {
        workerData: { id: i, start: s, end: e, username, password, shared },
      });
      workerList.push(w);

      w.on('message', (msg) => {
        if (msg?.type === 'found') {
          console.log('\nFOUND', msg.ts, formatUtc(msg.ts));
          console.log(msg.jsonText.trim());
          console.log('check', msg.check);
          console.log(`flag{${msg.check}}`);
          stopAll();
        } else if (msg?.type === 'progress') {
          process.stderr.write(`worker ${msg.id}: ${msg.ts}\r`);
        }
      });
      w.on('exit', () => {
        finished++;
        if (finished === workers && Atomics.load(stop, 0) === 0) {
          console.log('\nnot found in range');
        }
      });
      w.on('error', (err) => {
        console.error('worker error', err);
        stopAll();
        process.exit(1);
      });
    }
  })().catch((e) => {
    console.error(e);
    process.exit(1);
  });
} else {
  (async () => {
    const { id, start, end, shared, username, password } = workerData;
    const stop = new Int32Array(shared);

    const { exports, authenticateAt } = await buildWasmAuth();

    void username;
    void password;

    const GC_EVERY = 20000;

    let iter = 0;
    for (let ts = start; ts <= end; ts++) {
      if (Atomics.load(stop, 0) === 1) return;

      const jsonText = authenticateAt(ts);
      const jsonTrim = jsonText.trim();
      const check = md5Hex(jsonTrim);

      if (check.startsWith(PREFIX)) {
        Atomics.store(stop, 0, 1);
        parentPort.postMessage({ type: 'found', ts, jsonText: jsonTrim, check });
        return;
      }

      iter++;
      if (exports.__collect && (iter % GC_EVERY) === 0) exports.__collect();
      if ((iter % 1_000_000) === 0) parentPort.postMessage({ type: 'progress', id, ts });
    }
  })().catch((e) => {
    parentPort.postMessage({ type: 'error', error: String(e?.stack || e) });
  });
}
```

## EzFlag

（这不逆向题吗）ida打开看到判断是否等于V3ryStr0ngp@ssw0rd，linux跑输出flag但一半后很慢

```c++
  std::string::basic_string(v6, argv, envp);
  std::operator<<<std::char_traits<char>>(&_bss_start, "Enter password: ");
  std::getline<char,std::char_traits<char>,std::allocator<char>>(&std::cin, v6);
  if ( (unsigned __int8)std::operator!=<char>(v6, "V3ryStr0ngp@ssw0rd") )
  {
    v3 = std::operator<<<std::char_traits<char>>(&_bss_start, "Wrong password!");
    std::ostream::operator<<(v3, &std::endl<char,std::char_traits<char>>);
  }
  else
  {
    std::operator<<<std::char_traits<char>>(&_bss_start, "flag{");
    std::ostream::flush((std::ostream *)&_bss_start);
    v11 = 1;
    for ( n7 = 0; n7 <= 31; ++n7 )
    {
      v9 = f(v11);
      std::operator<<<std::char_traits<char>>(&_bss_start, (unsigned int)v9);
      std::ostream::flush((std::ostream *)&_bss_start);
      if ( n7 == 7 || n7 == 12 || n7 == 17 || n7 == 22 )
      {
        std::operator<<<std::char_traits<char>>(&_bss_start, "-");
        std::ostream::flush((std::ostream *)&_bss_start);
      }
      v11 *= 8LL;
      v11 += n7 + 64;
      v8 = 1;
      std::chrono::duration<long,std::ratio<1l,1l>>::duration<int,void>(v7, &v8);
      std::this_thread::sleep_for<long,std::ratio<1l,1l>>(v7);
    }
    v4 = std::operator<<<std::char_traits<char>>(&_bss_start, "}");
    std::ostream::operator<<(v4, &std::endl<char,std::char_traits<char>>);
  }
  std::string::~string(v6);
  return 0;
}
```

故根据逻辑写exp.c

```c
#include <stdint.h>
#include <stdio.h>

static const char K[] = "012ab9c3478d56ef";

static uint8_t fib_mod16_from_n_mod24(uint8_t n_mod24) {
    uint8_t a = 0;
    uint8_t b = 1;
    for (uint8_t i = 0; i < n_mod24; i++) {
        uint8_t t = b;
        b = (uint8_t)((a + b) & 0x0F);
        a = t;
    }
    return a;
}

static char fy(uint64_t n) {
    uint8_t n_mod24 = (uint8_t)(n % 24u);
    uint8_t idx = fib_mod16_from_n_mod24(n_mod24);
    return K[idx];
}

int main(void) {
    uint64_t x = 1;
    putchar('f');
    putchar('l');
    putchar('a');
    putchar('g');
    putchar('{');

    for (uint32_t i = 0; i <= 0x1Fu; i++) {
        putchar(fy(x));
        if (i == 7 || i == 0xC || i == 0x11 || i == 0x16) {
            putchar('-');
        }
        x = (x << 3) + (uint64_t)(i + 0x40);
    }

    putchar('}');
    putchar('\n');
    return 0;
}

```

