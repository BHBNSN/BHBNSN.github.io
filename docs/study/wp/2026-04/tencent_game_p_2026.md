# 2026 腾讯游戏安全大赛 初赛

## android 赛道

### 1. 架构分析

解包 apk 后 lib 下面可以看到 `libgodot_android.so` 文件，因此可知是一个 godot 程序，使用 godot re 解包报错，发现提示 aes key 错误，因此第一反应就是提取 aes key。

### 2. 提取 godot 自定义 key（失败）

一般来说，aes key 位于 `libgodot_android.so` 内，需要定位 `FileAccessEncrypted::open_and_parse` 打断点取值，但是很可惜本题的字符串中没有这玩意，找到的 `.rodata:000000000094501A	00000012	C	15PackedSourcePCK` 也没有解析无法交叉引用过去，因此只能在运行时提取 key ，因为程序运行时要用这个 key 来解密游戏资源，因此可以在打开 `sparsepck` 时 hook 32 位的 `memcpy` 来尝试找到 key。

```javascript
'use strict';

const GODOT = "libgodot_android.so";
let armedUntil = 0;
let lastPrinted = "";

function log(s) {
    console.log("[key] " + s);
}

function hexOf(addr, n) {
    try {
        const buf = addr.readByteArray(n);
        const u8 = new Uint8Array(buf);
        let out = "";
        for (let i = 0; i < u8.length; i++) {
            out += ("0" + u8[i].toString(16)).slice(-2);
        }
        return out;
    } catch (e) {
        return "<read-failed>";
    }
}

function moduleNameByAddr(addr) {
    try {
        const m = Process.findModuleByAddress(addr);
        return m ? m.name : null;
    } catch (e) {
        return null;
    }
}

function moduleOff(addr) {
    try {
        const m = Process.findModuleByAddress(addr);
        if (!m) return addr.toString();
        return m.name + "+0x" + addr.sub(m.base).toString(16);
    } catch (e) {
        return addr.toString();
    }
}

function hookAssetOpen() {
    try {
        const libandroid = Process.getModuleByName("libandroid.so");
        const fn = libandroid.getExportByName("AAssetManager_open");

        Interceptor.attach(fn, {
            onEnter(args) {
                this.name = "";
                try {
                    this.name = args[1].readCString();
                } catch (e) {}
            },
            onLeave(retval) {
                if (this.name.indexOf("sparsepck") !== -1) {
                    armedUntil = Date.now() + 5000;
                    log("AAssetManager_open => " + this.name + " (armed 5s)");
                }
            }
        });

        log("hooked AAssetManager_open");
    } catch (e) {
        log("hookAssetOpen failed: " + e);
    }
}

function hookMemcpyFamily() {
    try {
        const libc = Process.getModuleByName("libc.so");

        ["memcpy", "memmove"].forEach(name => {
            const fn = libc.getExportByName(name);

            Interceptor.attach(fn, {
                onEnter(args) {
                    this.dst = args[0];
                    this.src = args[1];
                    this.n = args[2].toUInt32 ? args[2].toUInt32() : parseInt(args[2]);
                    this.ra = this.returnAddress;
                },
                onLeave(retval) {
                    if (Date.now() > armedUntil) return;
                    if (this.n !== 32) return;

                    const mod = moduleNameByAddr(this.ra);
                    if (mod !== GODOT) return;

                    const srcHex = hexOf(this.src, 32);
                    const dstHex = hexOf(this.dst, 32);
                    const sig = name + "|" + moduleOff(this.ra) + "|" + srcHex;

                    if (sig === lastPrinted) return;
                    lastPrinted = sig;

                    log(name + " n=32 ra=" + this.ra + " (" + moduleOff(this.ra) + ")");
                    log("src=" + srcHex);
                    log("dst=" + dstHex);
                }
            });

            log("hooked " + name);
        });
    } catch (e) {
        log("hookMemcpyFamily failed: " + e);
    }
}

hookAssetOpen();
hookMemcpyFamily();
log("ready");
```

得到结果

```
Spawning `com.tencent.ACE.gamesec2026.preliminary`...                   
[key] hooked AAssetManager_open
[key] hooked memcpy
[key] hooked memmove
[key] ready
Spawned `com.tencent.ACE.gamesec2026.preliminary`. Resuming main thread!
[NX563J::com.tencent.ACE.gamesec2026.preliminary ]-> [key] AAssetManager_open => assets.sparsepck (armed 5s)
[key] memcpy n=32 ra=0x786c502d10 (libgodot_android.so+0x107cd10)
[key] src=ce4df8753b59a5a39ade58ac07ef947a3da39f2af75e3284d51217c04d49a061
[key] dst=ce4df8753b59a5a39ade58ac07ef947a3da39f2af75e3284d51217c04d49a061
[key] memcpy n=32 ra=0x786ce04640 (libgodot_android.so+0x197e640)
[key] src=ce4df8753b59a5a39ade58ac07ef947a3da39f2af75e3284d51217c04d49a061
[key] dst=ce4df8753b59a5a39ade58ac07ef947a3da39f2af75e3284d51217c04d49a061
```

很可惜的是，godot re 并不认这个 key，手动用这个 key 解密 gdc 后发现如果异或当前位的话，前 16 字节能正确解密，但后面依然无法解密，至此此路堵死。

### 3. 直接让小车飞去绿块吧

既然没法直接静态分析 gd 脚本，那就通过 hook 来获取物品属性，直接让小车飞去绿块先把 flag 格式拿到手

首先我们需要确定场景是哪个（因为不知道为什么，就算等启动完成后已经是镇子了读取还是 `car_select`），godot 会把场景打包成 tscn [官方文档](https://docs.godotengine.org/zh-cn/4.5/getting_started/step_by_step/instancing.html#creating-instances){target="_blank" rel="noopener"} 我们可以看到有这几个场景

1. `car_base.tscn.remap`
2. `car_select.tscn.remap`
3. `tow_truck.tscn.remap`
4. `town_scene.tscn.remap`
5. `trailer_truck.tscn.remap`

很明显我们所在的场景应该是 `town_scene` （想切去其他几个场景看看但不知道为什么切不过去）

下一步我们需要确定场景里面有哪些东西，写一个 hook 脚本

```python
import argparse
import json
import sys
import time

import frida


PKG = "com.tencent.ACE.gamesec2026.preliminary"

JS_TEMPLATE = r"""
'use strict';

const SELECT_BUTTON = %SELECT_BUTTON%;
const CHANGE_SCENE = %CHANGE_SCENE%;

const state = {
  dlsymHooked: false,
  extInitHooked: false,
  resolverPtr: null,
  dumped: false,
  retries: 0,
  buttonPressed: false,
  sceneChanged: false,
};

function log(msg) {
  send({ type: 'log', msg: msg });
}

function resolveName(resolver, name) {
  const gp = new NativeFunction(resolver, 'pointer', ['pointer']);
  const p = gp(Memory.allocUtf8String(name));
  if (p.isNull()) {
    throw new Error('resolve failed: ' + name);
  }
  return p;
}

function readUtf32(ptrValue, len) {
  try {
    const ab = ptrValue.readByteArray(len * 4);
    const u8 = new Uint8Array(ab);
    let out = '';
    for (let i = 0; i < len; i++) {
      const ch = u8[i * 4];
      if (ch === 0) {
        break;
      }
      out += String.fromCharCode(ch);
    }
    return out;
  } catch (e) {
    return null;
  }
}

function variantToUtf8(api, variantPtr) {
  const strObj = Memory.alloc(0x10);
  api.variantStringify(variantPtr, strObj);
  const need = api.stringToUtf8(strObj, ptr(0), 0);
  const buf = Memory.alloc(Math.max(need + 4, 0x100));
  const got = api.stringToUtf8(strObj, buf, need + 1);
  try {
    return buf.readUtf8String(got);
  } catch (e) {
    return '<utf8-read-failed>';
  }
}

function stringName(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNameNew(mem, Memory.allocUtf8String(text));
  return mem;
}

function stringObj(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNewUtf8(mem, Memory.allocUtf8String(text));
  return mem;
}

function newVariantFromString(api, text) {
  const obj = stringObj(api, text);
  const variant = Memory.alloc(0x20);
  api.ctorString(variant, obj);
  return variant;
}

function newVariantFromBool(api, value) {
  const raw = Memory.alloc(8);
  raw.writeU8(value ? 1 : 0);
  const variant = Memory.alloc(0x20);
  api.ctorBool(variant, raw);
  return variant;
}

function newVariantFromInt(api, value) {
  const raw = Memory.alloc(8);
  raw.writeS64(value);
  const variant = Memory.alloc(0x20);
  api.ctorInt(variant, raw);
  return variant;
}

function newVariantFromObject(api, objectPtr) {
  const raw = Memory.alloc(Process.pointerSize);
  raw.writePointer(objectPtr);
  const variant = Memory.alloc(0x20);
  api.ctorObject(variant, raw);
  return variant;
}

function decodeCallError(errPtr) {
  try {
    const data = new Uint8Array(errPtr.readByteArray(0x20));
    let s = '';
    for (let i = 0; i < data.length; i++) {
      s += ('0' + data[i].toString(16)).slice(-2);
    }
    return s;
  } catch (e) {
    return '<call-error-read-failed>';
  }
}

function callVariant(api, selfVar, methodName, args) {
  const retVar = Memory.alloc(0x20);
  const err = Memory.alloc(0x20);
  const sn = stringName(api, methodName);
  let argsPtr = ptr(0);
  if (args.length > 0) {
    argsPtr = Memory.alloc(args.length * Process.pointerSize);
    for (let i = 0; i < args.length; i++) {
      argsPtr.add(i * Process.pointerSize).writePointer(args[i]);
    }
  }
  api.variantCall(selfVar, sn, argsPtr, args.length, retVar, err);
  return { retVar: retVar, errHex: decodeCallError(err) };
}

function arraySize(api, arrayVar) {
  const res = callVariant(api, arrayVar, 'size', []);
  const txt = variantToUtf8(api, res.retVar);
  const num = parseInt(txt, 10);
  if (Number.isNaN(num)) {
    throw new Error('array size parse failed: ' + txt);
  }
  return num;
}

function arrayGet(api, arrayVar, index) {
  return callVariant(api, arrayVar, 'get', [newVariantFromInt(api, index)]).retVar;
}

function dumpNamedNodes(api, sceneVar, className, label) {
  const result = callVariant(api, sceneVar, 'find_children', [
    newVariantFromString(api, '*'),
    newVariantFromString(api, className),
    newVariantFromBool(api, true),
    newVariantFromBool(api, false),
  ]);

  const count = arraySize(api, result.retVar);
  send({
    type: 'node_group',
    label: label,
    class_name: className,
    count: count,
    raw: variantToUtf8(api, result.retVar),
  });

  for (let i = 0; i < count; i++) {
    const nodeVar = arrayGet(api, result.retVar, i);
    const nameRes = callVariant(api, nodeVar, 'get_name', []);
    const classRes = callVariant(api, nodeVar, 'get_class', []);
    const pathRes = callVariant(api, nodeVar, 'get_path', []);
    send({
      type: 'node_info',
      label: label,
      index: i,
      name: variantToUtf8(api, nameRes.retVar),
      class_name: variantToUtf8(api, classRes.retVar),
      path: variantToUtf8(api, pathRes.retVar),
      self: variantToUtf8(api, nodeVar),
    });
    if (className === 'Button') {
      const connRes = callVariant(api, nodeVar, 'get_signal_connection_list', [newVariantFromString(api, 'pressed')]);
      send({
        type: 'button_connections',
        index: i,
        name: variantToUtf8(api, nameRes.retVar),
        raw: variantToUtf8(api, connRes.retVar),
      });
    }
  }
}

function findChild(api, sceneVar, name) {
  return callVariant(api, sceneVar, 'find_child', [
    newVariantFromString(api, name),
    newVariantFromBool(api, true),
    newVariantFromBool(api, false),
  ]).retVar;
}

function buttonHandlerName(buttonName) {
  if (buttonName === 'MiniVan') {
    return '_on_mini_van_pressed';
  }
  if (buttonName === 'TrailerTruck') {
    return '_on_trailer_truck_pressed';
  }
  if (buttonName === 'TowTruck') {
    return '_on_tow_truck_pressed';
  }
  return '';
}

function dumpScene(resolver) {
  const api = {
    stringNameNew: new NativeFunction(resolveName(resolver, 'string_name_new_with_latin1_chars'), 'void', ['pointer', 'pointer']),
    stringNewUtf8: new NativeFunction(resolveName(resolver, 'string_new_with_utf8_chars'), 'void', ['pointer', 'pointer']),
    getVarCtor: new NativeFunction(resolveName(resolver, 'get_variant_from_type_constructor'), 'pointer', ['int']),
    variantCall: new NativeFunction(resolveName(resolver, 'variant_call'), 'void', ['pointer', 'pointer', 'pointer', 'int', 'pointer', 'pointer']),
    variantStringify: new NativeFunction(resolveName(resolver, 'variant_stringify'), 'void', ['pointer', 'pointer']),
    stringToUtf8: new NativeFunction(resolveName(resolver, 'string_to_utf8_chars'), 'int', ['pointer', 'pointer', 'int']),
    globalGetSingleton: new NativeFunction(resolveName(resolver, 'global_get_singleton'), 'pointer', ['pointer']),
  };

  api.ctorBool = new NativeFunction(api.getVarCtor(1), 'void', ['pointer', 'pointer']);
  api.ctorInt = new NativeFunction(api.getVarCtor(2), 'void', ['pointer', 'pointer']);
  api.ctorString = new NativeFunction(api.getVarCtor(4), 'void', ['pointer', 'pointer']);
  api.ctorObject = new NativeFunction(api.getVarCtor(24), 'void', ['pointer', 'pointer']);

  const engineObj = api.globalGetSingleton(stringName(api, 'Engine'));
  if (engineObj.isNull()) {
    throw new Error('global_get_singleton(Engine) failed');
  }

  const engineVar = newVariantFromObject(api, engineObj);
  const mainLoopRes = callVariant(api, engineVar, 'get_main_loop', []);
  const sceneTreeVar = mainLoopRes.retVar;
  const rootRes = callVariant(api, sceneTreeVar, 'get_root', []);
  const rootVar = rootRes.retVar;
  const currentSceneRes = callVariant(api, sceneTreeVar, 'get_current_scene', []);
  const sceneVar = currentSceneRes.retVar;

  const rootText = variantToUtf8(api, rootVar);
  const sceneTreeText = variantToUtf8(api, sceneTreeVar);
  const currentSceneText = variantToUtf8(api, sceneVar);

  send({
    type: 'engine',
    engine: variantToUtf8(api, engineVar),
    scene_tree: sceneTreeText,
    root: rootText,
    current_scene: currentSceneText,
  });

  if (CHANGE_SCENE && currentSceneText.indexOf('CarSelect:') === 0 && !state.sceneChanged) {
    const changeRes = callVariant(api, sceneTreeVar, 'change_scene_to_file', [newVariantFromString(api, CHANGE_SCENE)]);
    send({
      type: 'change_scene',
      target: CHANGE_SCENE,
      result: variantToUtf8(api, changeRes.retVar),
      err_hex: changeRes.errHex,
    });
    state.sceneChanged = true;
    return false;
  }

  if (SELECT_BUTTON && currentSceneText.indexOf('CarSelect:') === 0) {
    if (!state.buttonPressed) {
      const buttonVar = findChild(api, sceneVar, SELECT_BUTTON);
      const handlerName = buttonHandlerName(SELECT_BUTTON);
      send({
        type: 'select_button',
        button: SELECT_BUTTON,
        target: variantToUtf8(api, buttonVar),
        handler: handlerName,
      });
      if (handlerName.length === 0) {
        throw new Error('no handler mapping for ' + SELECT_BUTTON);
      }
      callVariant(api, sceneVar, handlerName, []);
      state.buttonPressed = true;
    }
    return false;
  }

  if (sceneTreeText === '<Object#null>' || currentSceneText === '<null>' || currentSceneText === '<Object#null>') {
    return false;
  }

  const treeRes = callVariant(api, sceneVar, 'get_tree_string_pretty', []);
  send({
    type: 'tree',
    tree: variantToUtf8(api, treeRes.retVar),
    err_hex: treeRes.errHex,
  });

  const rootTreeRes = callVariant(api, rootVar, 'get_tree_string_pretty', []);
  send({
    type: 'root_tree',
    tree: variantToUtf8(api, rootTreeRes.retVar),
    err_hex: rootTreeRes.errHex,
  });

  dumpNamedNodes(api, sceneVar, 'Area3D', 'areas');
  dumpNamedNodes(api, sceneVar, 'Button', 'buttons');
  dumpNamedNodes(api, sceneVar, 'TextureButton', 'texture_buttons');
  dumpNamedNodes(api, sceneVar, 'Label', 'labels');
  dumpNamedNodes(api, sceneVar, 'Label3D', 'labels3d');
  dumpNamedNodes(api, sceneVar, 'VehicleBody3D', 'vehicles');
  dumpNamedNodes(api, sceneVar, 'RigidBody3D', 'rigids');
  dumpNamedNodes(api, sceneVar, 'Node3D', 'node3d');
  return true;
}

function tryDump() {
  if (state.dumped || state.resolverPtr === null) {
    return;
  }
  try {
    const ok = dumpScene(state.resolverPtr);
    if (ok) {
      state.dumped = true;
      send({ type: 'done' });
      return;
    }
    state.retries += 1;
    if (state.retries >= 20) {
      state.dumped = true;
      send({ type: 'error', err: 'scene tree never became ready', stack: '' });
      return;
    }
    setTimeout(tryDump, 500);
  } catch (e) {
    state.dumped = true;
    send({ type: 'error', err: String(e), stack: e.stack || '' });
  }
}

function hookResolver(ptrValue) {
  if (state.resolverPtr !== null) {
    return;
  }
  state.resolverPtr = ptrValue;
  log('[resolver] ' + ptrValue);
  setTimeout(tryDump, 2500);
}

function hookExtensionInit(ptrValue) {
  if (state.extInitHooked) {
    return;
  }
  state.extInitHooked = true;
  Interceptor.attach(ptrValue, {
    onEnter(args) {
      hookResolver(args[0]);
    }
  });
}

function hookDlsym() {
  if (state.dlsymHooked) {
    return;
  }
  state.dlsymHooked = true;
  let dlsymPtr = null;
  try {
    dlsymPtr = Module.getGlobalExportByName('dlsym');
  } catch (e) {
    try {
      dlsymPtr = Module.findGlobalExportByName('dlsym');
    } catch (e2) {
      dlsymPtr = null;
    }
  }
  if (!dlsymPtr) {
    throw new Error('dlsym not found');
  }
  Interceptor.attach(dlsymPtr, {
    onEnter(args) {
      this.name = '<bad>';
      try {
        this.name = args[1].readCString();
      } catch (e) {
      }
    },
    onLeave(retval) {
      if (this.name === 'extension_init' && !retval.isNull()) {
        hookExtensionInit(retval);
      }
    }
  });
}

setImmediate(function () {
  hookDlsym();
});
"""


def main():
    parser = argparse.ArgumentParser(description="Inspect Godot scene tree via GDExtension API")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--select-button", default="", help="Press a Button in CarSelect before dumping the next scene")
    parser.add_argument("--change-scene", default="", help="Call SceneTree.change_scene_to_file(path) before dumping")
    parser.add_argument("--attach", action="store_true", help="Attach to an already-running app instead of spawning")
    parser.add_argument("--pid", type=int, default=0, help="Attach to a specific running PID")
    args = parser.parse_args()

    js = JS_TEMPLATE.replace("%SELECT_BUTTON%", repr(args.select_button or ""))
    js = js.replace("%CHANGE_SCENE%", repr(args.change_scene or ""))

    device = frida.get_usb_device(timeout=10)
    if args.pid:
      session = device.attach(args.pid)
      print(f"[host] attached to pid={args.pid}")
    elif args.attach:
      session = device.attach(PKG)
      print("[host] attached to running process")
    else:
      pid = device.spawn([PKG])
      print(f"[host] spawn pid={pid}")
      session = device.attach(pid)
    script = session.create_script(js)

    done = {"ok": False}

    def on_message(message, data):
        if message["type"] != "send":
            print(message)
            return
        payload = message["payload"]
        sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8", "backslashreplace"))
        sys.stdout.flush()
        if payload.get("type") in {"done", "error"}:
            done["ok"] = True

    script.on("message", on_message)
    script.load()
    if not args.attach and not args.pid:
      device.resume(pid)

    deadline = time.time() + args.timeout
    while time.time() < deadline and not done["ok"]:
        time.sleep(0.25)


if __name__ == "__main__":
    main()

```

结果

```
\inspect_scene.py --change-scene res://town/town_scene.tscn --timeout 8
[host] spawn pid=25638
{"type": "log", "msg": "[resolver] 0x786f0e37bc"}
{"type": "engine", "engine": "<Engine#352321556>", "scene_tree": "<SceneTree#27430749507>", "root": "root:<Window#27447526724>", "current_scene": "<Object#null>"}
{"type": "engine", "engine": "<Engine#352321556>", "scene_tree": "<SceneTree#27430749507>", "root": "root:<Window#27447526724>", "current_scene": "CarSelect:<Control#36507223376>"}
{"type": "change_scene", "target": "res://town/town_scene.tscn", "result": "31", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000"}
{"type": "engine", "engine": "<Engine#352321556>", "scene_tree": "<SceneTree#27430749507>", "root": "root:<Window#27447526724>", "current_scene": "CarSelect:<Control#36507223376>"}
{"type": "tree", "tree": " ┖╴CarSelect
    ┠╴HBoxContainer
    ┃  ┠╴MiniVan
    ┃  ┠╴TrailerTruck
    ┃  ┖╴TowTruck
    ┖╴Label
", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000"}
{"type": "root_tree", "tree": " ┖╴root
    ┠╴CarSelect
    ┃  ┠╴HBoxContainer
    ┃  ┃  ┠╴MiniVan
    ┃  ┃  ┠╴TrailerTruck
    ┃  ┃  ┖╴TowTruck
    ┃  ┖╴Label
    ┖╴TownScene
       ┠╴WorldEnvironment
       ┠╴DirectionalLight3D
       ┠╴TruckTown
       ┃  ┠╴Road
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┠╴Grass
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┠╴House07
       ┃  ┃  ┠╴House07Door
       ┃  ┃  ┠╴House07Roof
       ┃  ┃  ┠╴House07Window00
       ┃  ┃  ┠╴省略一堆窗户
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┠╴省略一堆房子
       ┠╴InstancePos
       ┃  ┖╴car
       ┃     ┖╴Body
       ┃        ┠╴Wheel1
       ┃        ┃  ┖╴Wheel1
       ┃        ┠╴Wheel2
       ┃        ┃  ┖╴Wheel2
       ┃        ┠╴Wheel3
       ┃        ┃  ┖╴Wheel3
       ┃        ┠╴Wheel4
       ┃        ┃  ┖╴Wheel4
       ┃        ┠╴Body
       ┃        ┠╴CollisionShape3D
       ┃        ┠╴CameraBase
       ┃        ┃  ┖╴Camera3D
       ┃        ┠╴EngineSound
       ┃        ┠╴ImpactSound
       ┃        ┠╴CPUParticles3D
       ┃        ┠╴BlobShadow
       ┃        ┠╴AudioListener3D
       ┃        ┠╴InteriorCameraPosition
       ┃        ┖╴TopDownCameraPosition
       ┠╴Spedometer
       ┠╴Back
       ┠╴TouchTurnLeft
       ┃  ┖╴TurnLeft
       ┠╴TouchReverse
       ┃  ┖╴Reverse
       ┠╴TouchTurnRight
       ┃  ┖╴TurnRight
       ┠╴TouchAccelerate
       ┃  ┖╴Accelerate
       ┠╴Ground
       ┃  ┖╴StaticBody3D
       ┃     ┖╴CollisionShape3D
       ┠╴Ground2
       ┃  ┖╴StaticBody3D
       ┃     ┖╴CollisionShape3D
       ┠╴Ground3
       ┃  ┖╴StaticBody3D
       ┃     ┖╴CollisionShape3D
       ┠╴Ground4
       ┃  ┖╴StaticBody3D
       ┃     ┖╴CollisionShape3D
       ┠╴Racetrack
       ┃  ┠╴Path3D
       ┃  ┠╴HugeTire
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┠╴Ramp
       ┃  ┃  ┠╴RampStart
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┠╴Ramp2
       ┃  ┃  ┠╴RampStart
       ┃  ┃  ┃  ┖╴StaticBody3D
       ┃  ┃  ┃     ┖╴CollisionShape3D
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┠╴Ramp3
       ┃  ┃  ┠╴RampStart
       ┃  ┃  ┃  ┖╴StaticBody3D
       ┃  ┃  ┃     ┖╴CollisionShape3D
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┠╴Ramp4
       ┃  ┃  ┠╴RampStart
       ┃  ┃  ┃  ┖╴StaticBody3D
       ┃  ┃  ┃     ┖╴CollisionShape3D
       ┃  ┃  ┖╴StaticBody3D
       ┃  ┃     ┖╴CollisionShape3D
       ┃  ┖╴Ramp5
       ┃     ┠╴RampStart
       ┃     ┃  ┖╴StaticBody3D
       ┃     ┃     ┖╴CollisionShape3D
       ┃     ┖╴StaticBody3D
       ┃        ┖╴CollisionShape3D
       ┠╴Trigger1
       ┃  ┠╴CollisionShape3D
       ┃  ┖╴MeshInstance3D
       ┠╴Trigger2
       ┃  ┠╴CollisionShape3D
       ┃  ┖╴MeshInstance3D
       ┠╴Label
       ┖╴Label2
", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000"}
{"type": "node_group", "label": "areas", "class_name": "Area3D", "count": 0, "raw": "[]"}
{"type": "node_group", "label": "buttons", "class_name": "Button", "count": 3, "raw": "[MiniVan:<Button#36574332268>, TrailerTruck:<Button#36624663892>, TowTruck:<Button#36674995711>]"}
{"type": "node_info", "label": "buttons", "index": 0, "name": "MiniVan", "class_name": "Button", "path": "/root/CarSelect/HBoxContainer/MiniVan", "self": "MiniVan:<Button#36574332268>"}
{"type": "button_connections", "index": 0, "name": "MiniVan", "raw": "[{ \"signal\": Button::[signal]pressed, \"callable\": Control(car_select.gd)::_on_mini_van_pressed, \"flags\": 34 }]"}
{"type": "node_info", "label": "buttons", "index": 1, "name": "TrailerTruck", "class_name": "Button", "path": "/root/CarSelect/HBoxContainer/TrailerTruck", "self": "TrailerTruck:<Button#36624663892>"}
{"type": "button_connections", "index": 1, "name": "TrailerTruck", "raw": "[{ \"signal\": Button::[signal]pressed, \"callable\": Control(car_select.gd)::_on_trailer_truck_pressed, \"flags\": 34 }]"}
{"type": "node_info", "label": "buttons", "index": 2, "name": "TowTruck", "class_name": "Button", "path": "/root/CarSelect/HBoxContainer/TowTruck", "self": "TowTruck:<Button#36674995711>"}
{"type": "button_connections", "index": 2, "name": "TowTruck", "raw": "[{ \"signal\": Button::[signal]pressed, \"callable\": Control(car_select.gd)::_on_tow_truck_pressed, \"flags\": 34 }]"}
{"type": "node_group", "label": "texture_buttons", "class_name": "TextureButton", "count": 0, "raw": "[]"}
{"type": "node_group", "label": "labels", "class_name": "Label", "count": 1, "raw": "[Label:<Label#36725327362>]"}
{"type": "node_info", "label": "labels", "index": 0, "name": "Label", "class_name": "Label", "path": "/root/CarSelect/Label", "self": "Label:<Label#36725327362>"}
{"type": "node_group", "label": "labels3d", "class_name": "Label3D", "count": 0, "raw": "[]"}
{"type": "node_group", "label": "vehicles", "class_name": "VehicleBody3D", "count": 0, "raw": "[]"}
{"type": "node_group", "label": "rigids", "class_name": "RigidBody3D", "count": 0, "raw": "[]"}
{"type": "node_group", "label": "node3d", "class_name": "Node3D", "count": 0, "raw": "[]"}
{"type": "done"}
```

可以找出几个我们比较关注的物品：car、Trigger1、Trigger2、Label、Label2等

我们可以再hook下这些东西的属性

```python
import argparse
import json
import sys
import time

import frida


PKG = "com.tencent.ACE.gamesec2026.preliminary"

JS_TEMPLATE = r"""
'use strict';

const TRIGGER_NAME = %TRIGGER_NAME%;

const state = {
  dlsymHooked: false,
  extInitHooked: false,
  resolverPtr: null,
  done: false,
};

function resolveName(resolver, name) {
  const gp = new NativeFunction(resolver, 'pointer', ['pointer']);
  const p = gp(Memory.allocUtf8String(name));
  if (p.isNull()) {
    throw new Error('resolve failed: ' + name);
  }
  return p;
}

function readUtf32(ptrValue, len) {
  try {
    const ab = ptrValue.readByteArray(len * 4);
    const u8 = new Uint8Array(ab);
    let out = '';
    for (let i = 0; i < len; i++) {
      const ch = u8[i * 4];
      if (ch === 0) break;
      out += String.fromCharCode(ch);
    }
    return out;
  } catch (e) {
    return null;
  }
}

function variantToUtf8(api, variantPtr) {
  const strObj = Memory.alloc(0x10);
  api.variantStringify(variantPtr, strObj);
  const need = api.stringToUtf8(strObj, ptr(0), 0);
  const buf = Memory.alloc(Math.max(need + 4, 0x100));
  const got = api.stringToUtf8(strObj, buf, need + 1);
  try {
    return buf.readUtf8String(got);
  } catch (e) {
    return '<utf8-read-failed>';
  }
}

function stringName(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNameNew(mem, Memory.allocUtf8String(text));
  return mem;
}

function stringObj(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNewUtf8(mem, Memory.allocUtf8String(text));
  return mem;
}

function newVariantFromString(api, text) {
  const obj = stringObj(api, text);
  const variant = Memory.alloc(0x20);
  api.ctorString(variant, obj);
  return variant;
}

function newVariantFromBool(api, value) {
  const raw = Memory.alloc(8);
  raw.writeU8(value ? 1 : 0);
  const variant = Memory.alloc(0x20);
  api.ctorBool(variant, raw);
  return variant;
}

function newVariantFromInt(api, value) {
  const raw = Memory.alloc(8);
  raw.writeS64(value);
  const variant = Memory.alloc(0x20);
  api.ctorInt(variant, raw);
  return variant;
}

function newVariantFromObject(api, objectPtr) {
  const raw = Memory.alloc(Process.pointerSize);
  raw.writePointer(objectPtr);
  const variant = Memory.alloc(0x20);
  api.ctorObject(variant, raw);
  return variant;
}

function decodeCallError(errPtr) {
  try {
    const data = new Uint8Array(errPtr.readByteArray(0x20));
    let s = '';
    for (let i = 0; i < data.length; i++) {
      s += ('0' + data[i].toString(16)).slice(-2);
    }
    return s;
  } catch (e) {
    return '<call-error-read-failed>';
  }
}

function callVariant(api, selfVar, methodName, args) {
  const retVar = Memory.alloc(0x20);
  const err = Memory.alloc(0x20);
  const sn = stringName(api, methodName);
  let argsPtr = ptr(0);
  if (args.length > 0) {
    argsPtr = Memory.alloc(args.length * Process.pointerSize);
    for (let i = 0; i < args.length; i++) {
      argsPtr.add(i * Process.pointerSize).writePointer(args[i]);
    }
  }
  api.variantCall(selfVar, sn, argsPtr, args.length, retVar, err);
  return { retVar: retVar, errHex: decodeCallError(err) };
}

function arraySize(api, arrayVar) {
  const res = callVariant(api, arrayVar, 'size', []);
  const txt = variantToUtf8(api, res.retVar);
  const num = parseInt(txt, 10);
  if (Number.isNaN(num)) {
    throw new Error('array size parse failed: ' + txt);
  }
  return num;
}

function arrayGet(api, arrayVar, index) {
  return callVariant(api, arrayVar, 'get', [newVariantFromInt(api, index)]).retVar;
}

function findChild(api, selfVar, name) {
  return callVariant(api, selfVar, 'find_child', [
    newVariantFromString(api, name),
    newVariantFromBool(api, true),
    newVariantFromBool(api, false),
  ]).retVar;
}

function getText(api, nodeVar) {
  return variantToUtf8(api, callVariant(api, nodeVar, 'get_text', []).retVar);
}

function getNodeInfo(api, nodeVar, note) {
  const scriptVar = callVariant(api, nodeVar, 'get_script', []).retVar;
  return {
    note: note,
    self: variantToUtf8(api, nodeVar),
    path: variantToUtf8(api, callVariant(api, nodeVar, 'get_path', []).retVar),
    class_name: variantToUtf8(api, callVariant(api, nodeVar, 'get_class', []).retVar),
    script: variantToUtf8(api, scriptVar),
    text: getText(api, nodeVar),
    position: variantToUtf8(api, callVariant(api, nodeVar, 'get_position', []).retVar),
    global_transform: variantToUtf8(api, callVariant(api, nodeVar, 'get_global_transform', []).retVar),
    groups: variantToUtf8(api, callVariant(api, nodeVar, 'get_groups', []).retVar),
    signal_body_entered: variantToUtf8(api, callVariant(api, nodeVar, 'get_signal_connection_list', [newVariantFromString(api, 'body_entered')]).retVar),
    signal_area_entered: variantToUtf8(api, callVariant(api, nodeVar, 'get_signal_connection_list', [newVariantFromString(api, 'area_entered')]).retVar),
    signal_input_event: variantToUtf8(api, callVariant(api, nodeVar, 'get_signal_connection_list', [newVariantFromString(api, 'input_event')]).retVar),
    incoming_connections: variantToUtf8(api, callVariant(api, nodeVar, 'get_incoming_connections', []).retVar),
    script_path: variantToUtf8(api, callVariant(api, scriptVar, 'get_path', []).retVar),
    script_method_list: variantToUtf8(api, callVariant(api, scriptVar, 'get_script_method_list', []).retVar),
    script_property_list: variantToUtf8(api, callVariant(api, scriptVar, 'get_script_property_list', []).retVar),
  };
}

function tryRun() {
  if (state.done || state.resolverPtr === null) return;
  try {
    const api = {
      stringNameNew: new NativeFunction(resolveName(state.resolverPtr, 'string_name_new_with_latin1_chars'), 'void', ['pointer', 'pointer']),
      stringNewUtf8: new NativeFunction(resolveName(state.resolverPtr, 'string_new_with_utf8_chars'), 'void', ['pointer', 'pointer']),
      getVarCtor: new NativeFunction(resolveName(state.resolverPtr, 'get_variant_from_type_constructor'), 'pointer', ['int']),
      variantCall: new NativeFunction(resolveName(state.resolverPtr, 'variant_call'), 'void', ['pointer', 'pointer', 'pointer', 'int', 'pointer', 'pointer']),
      variantStringify: new NativeFunction(resolveName(state.resolverPtr, 'variant_stringify'), 'void', ['pointer', 'pointer']),
      stringToUtf8: new NativeFunction(resolveName(state.resolverPtr, 'string_to_utf8_chars'), 'int', ['pointer', 'pointer', 'int']),
      globalGetSingleton: new NativeFunction(resolveName(state.resolverPtr, 'global_get_singleton'), 'pointer', ['pointer']),
    };
    api.ctorBool = new NativeFunction(api.getVarCtor(1), 'void', ['pointer', 'pointer']);
    api.ctorInt = new NativeFunction(api.getVarCtor(2), 'void', ['pointer', 'pointer']);
    api.ctorString = new NativeFunction(api.getVarCtor(4), 'void', ['pointer', 'pointer']);
    api.ctorObject = new NativeFunction(api.getVarCtor(24), 'void', ['pointer', 'pointer']);

    const engineObj = api.globalGetSingleton(stringName(api, 'Engine'));
    const engineVar = newVariantFromObject(api, engineObj);
    const sceneTreeVar = callVariant(api, engineVar, 'get_main_loop', []).retVar;
    const rootVar = callVariant(api, sceneTreeVar, 'get_root', []).retVar;
    const townVar = findChild(api, rootVar, 'TownScene');
    const triggerVar = findChild(api, townVar, TRIGGER_NAME);
    const trigger1Var = findChild(api, townVar, 'Trigger1');
    const trigger2Var = findChild(api, townVar, 'Trigger2');
    const labelVar = findChild(api, townVar, 'Label');
    const label2Var = findChild(api, townVar, 'Label2');
    const carVar = findChild(api, townVar, 'car');
    const bodyVar = findChild(api, townVar, 'Body');

    send({ type: 'node_info', info: getNodeInfo(api, trigger1Var, 'trigger1') });
    send({ type: 'node_info', info: getNodeInfo(api, trigger2Var, 'trigger2') });
    send({ type: 'node_info', info: getNodeInfo(api, labelVar, 'label') });
    send({ type: 'node_info', info: getNodeInfo(api, label2Var, 'label2') });
    send({ type: 'node_info', info: getNodeInfo(api, carVar, 'car') });
    send({ type: 'node_info', info: getNodeInfo(api, bodyVar, 'body') });

    send({
      type: 'before_emit',
      trigger: TRIGGER_NAME,
      label: getText(api, labelVar),
      label2: getText(api, label2Var),
    });

    const emitBodyRes = callVariant(api, triggerVar, 'emit_signal', [
      newVariantFromString(api, 'body_entered'),
      bodyVar,
    ]);
    send({
      type: 'emit_body_result',
      trigger: TRIGGER_NAME,
      err_hex: emitBodyRes.errHex,
      result: variantToUtf8(api, emitBodyRes.retVar),
    });

    send({
      type: 'after_body_emit',
      trigger: TRIGGER_NAME,
      label: getText(api, labelVar),
      label2: getText(api, label2Var),
    });

    const emitCollidedRes = callVariant(api, triggerVar, 'emit_signal', [
      newVariantFromString(api, 'collided_with'),
      newVariantFromString(api, TRIGGER_NAME),
    ]);
    send({
      type: 'emit_collided_result',
      trigger: TRIGGER_NAME,
      err_hex: emitCollidedRes.errHex,
      result: variantToUtf8(api, emitCollidedRes.retVar),
    });

    send({
      type: 'after_emit',
      trigger: TRIGGER_NAME,
      label: getText(api, labelVar),
      label2: getText(api, label2Var),
    });

    state.done = true;
    send({ type: 'done' });
  } catch (e) {
    send({ type: 'error', err: String(e), stack: e.stack || '' });
  }
}

function hookResolver(ptrValue) {
  if (state.resolverPtr !== null) return;
  state.resolverPtr = ptrValue;
  setTimeout(tryRun, 2500);
}

function hookExtensionInit(ptrValue) {
  if (state.extInitHooked) return;
  state.extInitHooked = true;
  Interceptor.attach(ptrValue, {
    onEnter(args) {
      hookResolver(args[0]);
    }
  });
}

function hookDlsym() {
  if (state.dlsymHooked) return;
  state.dlsymHooked = true;
  const dlsymPtr = Module.getGlobalExportByName('dlsym');
  Interceptor.attach(dlsymPtr, {
    onEnter(args) {
      this.name = '<bad>';
      try { this.name = args[1].readCString(); } catch (e) {}
    },
    onLeave(retval) {
      if (this.name === 'extension_init' && !retval.isNull()) {
        hookExtensionInit(retval);
      }
    }
  });
}

setImmediate(hookDlsym);
"""


def main():
    parser = argparse.ArgumentParser(description="Probe TownScene triggers and labels by emitting body_entered")
    parser.add_argument("trigger_name", choices=["Trigger1", "Trigger2"])
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    js = JS_TEMPLATE.replace("%TRIGGER_NAME%", repr(args.trigger_name))

    device = frida.get_usb_device(timeout=10)
    pid = device.spawn([PKG])
    print(f"[host] spawn pid={pid}")
    session = device.attach(pid)
    script = session.create_script(js)

    done = {"ok": False}

    def on_message(message, data):
        if message["type"] != "send":
            print(message)
            return
        payload = message["payload"]
        sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8", "backslashreplace"))
        sys.stdout.flush()
        if payload.get("type") in {"done", "error"}:
            done["ok"] = True

    script.on("message", on_message)
    script.load()
    device.resume(pid)

    deadline = time.time() + args.timeout
    while time.time() < deadline and not done["ok"]:
        time.sleep(0.25)


if __name__ == "__main__":
    main()

```

结果

```
\trigger_probe.py Trigger2
[host] spawn pid=27087
{"type": "node_info", "info": {"note": "trigger1", "self": "Trigger1:<Area3D#41976596247>", "path": "/root/TownScene/Trigger1", "class_name": "Area3D", "script": "<GDScript#-9223372002763471510>", "text": "<null>", "position": "(-12.84548, 5.822042, -15.34991)", "global_transform": "[X: (1.0, 0.0, 0.0), Y: (0.0, 1.0, 0.0), Z: (0.0, 0.0, 1.0), O: (-12.84548, 5.822042, -15.34991)]", "groups": "[]", "signal_body_entered": "[]", "signal_area_entered": "[]", "signal_input_event": "[]", "incoming_connections": "[]", "script_path": "res://Trigger/trigger.gd", "script_method_list": "[{ \"name\": \"_ready\", \"args\": [], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }, { \"name\": \"xor_enc\", \"args\": [{ \"name\": \"plain\", \"class_name\": &\"\", \"type\": 4, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 29, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 } }, { \"name\": \"_process\", \"args\": [{ \"name\": \"delta\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 131072 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }]", "script_property_list": "[{ \"name\": \"flag1Triggered\", \"class_name\": &\"\", \"type\": 1, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"flag2Triggered\", \"class_name\": &\"\", \"type\": 1, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"t\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"cnt\", \"class_name\": &\"\", \"type\": 2, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"obj\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 135168 }]"}}
{"type": "node_info", "info": {"note": "trigger2", "self": "Trigger2:<Area3D#42026927898>", "path": "/root/TownScene/Trigger2", "class_name": "Area3D", "script": "<GDScript#-9223372002763471510>", "text": "<null>", "position": "(-14.13952, 11.81643, -3.958621)", "global_transform": "[X: (1.0, 0.0, 0.0), Y: (0.0, 1.0, 0.0), Z: (0.0, 0.0, 1.0), O: (-14.13952, 11.81643, -3.958621)]", "groups": "[]", "signal_body_entered": "[]", "signal_area_entered": "[]", "signal_input_event": "[]", "incoming_connections": "[]", "script_path": "res://Trigger/trigger.gd", "script_method_list": "[{ \"name\": \"_ready\", \"args\": [], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }, { \"name\": \"xor_enc\", \"args\": [{ \"name\": \"plain\", \"class_name\": &\"\", \"type\": 4, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 29, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 } }, { \"name\": \"_process\", \"args\": [{ \"name\": \"delta\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 131072 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }]", "script_property_list": "[{ \"name\": \"flag1Triggered\", \"class_name\": &\"\", \"type\": 1, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"flag2Triggered\", \"class_name\": &\"\", \"type\": 1, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"t\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"cnt\", \"class_name\": &\"\", \"type\": 2, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"obj\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 135168 }]"}}
{"type": "node_info", "info": {"note": "label", "self": "Label:<Label#42077259549>", "path": "/root/TownScene/Label", "class_name": "Label", "script": "<GDScript#-9223372002427927087>", "text": "Token: 1455245e", "position": "(0.0, 0.0)", "global_transform": "[X: (1.0, 0.0), Y: (0.0, 1.0), O: (0.0, 0.0)]", "groups": "[&\"_root_canvas1924145348608\"]", "signal_body_entered": "[]", "signal_area_entered": "[]", "signal_input_event": "[]", "": "[{ \"signal\": LabelSettings::[signal]changed, \"callable\": , \"flags\": 8 }, { \"signal\": Window::[signal]visibility_changed, \"callable\": , \"flags\": 0 }, { \"signal\": Window::[signal]size_changed, \"callable\": , \"flags\": 0 }]", "script_path": "res://token.gd", "script_method_list": "[{ \"name\": \"generate_token\", \"args\": [{ \"name\": \"len\", \"class_name\": &\"\", \"type\": 2, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 4, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 } }, { \"name\": \"_ready\", \"args\": [], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }]", "script_property_list": "[{ \"name\": \"rng\", \"class_name\": &\"RandomNumberGenerator\", \"type\": 24, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"score\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 135168 }]"}}
{"type": "node_info", "info": {"note": "label2", "self": "Label2:<Label#42127591200>", "path": "/root/TownScene/Label2", "class_name": "Label", "script": "<GDScript#-9223372002092382765>", "text": "", "position": "(792.0, 0.0)", "global_transform": "[X: (1.0, 0.0), Y: (0.0, 1.0), O: (792.0, 0.0)]", "groups": "[&\"_root_canvas1924145348608\"]", "signal_body_entered": "[]", "signal_area_entered": "[]", "signal_input_event": "[]", "incoming_connections": "[{ \"signal\": LabelSettings::[signal]changed, \"callable\": , \"flags\": 8 }, { \"signal\": Window::[signal]visibility_changed, \"callable\": , \"flags\": 0 }, { \"signal\": Window::[signal]size_changed, \"callable\": , \"flags\": 0 }, { \"signal\": Area3D(trigger.gd)::[signal]collided_with, \"callable\": Label(label2.gd)::_on_collided_with, \"flags\": 0 }, { \"signal\": Area3D(trigger.gd)::[signal]collided_with, \"callable\": Label(label2.gd)::_on_collided_with, \"flags\": 0 }]", "script_path": "res://label2.gd", "script_method_list": "[{ \"name\": \"_ready\", \"args\": [], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }, { \"name\": \"_on_collided_with\", \"args\": [{ \"name\": \"name\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 131072 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }, { \"name\": \"_process\", \"args\": [{ \"name\": \"delta\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }]", "script_property_list": "[]"}}
{"type": "node_info", "info": {"note": "car", "self": "car:<Node3D#37228643848>", "path": "/root/TownScene/InstancePos/car", "class_name": "Node3D", "script": "<null>", "text": "<null>", "position": "(0.0, 0.0, 0.0)", "global_transform": "[X: (0.0, 0.0, 1.0), Y: (0.0, 1.0, 0.0), Z: (-1.0, 0.0, 0.0), O: (8.0, 3.36405, -16.0)]", "groups": "[]", "signal_body_entered": "[]", "signal_area_entered": "[]", "signal_input_event": "[]", "incoming_connections": "[]", "script_path": "<null>", "script_method_list": "<null>", "script_property_list": "<null>"}}
{"type": "node_info", "info": {"note": "body", "self": "Body:<VehicleBody3D#37245421065>", "path": "/root/TownScene/InstancePos/car/Body", "class_name": "VehicleBody3D", "script": "<GDScript#-9223372008518056613>", "text": "<null>", "position": "(-0.001696, 0.222867, -0.095518)", "global_transform": "[X: (0.0, 0.0, 1.0), Y: (0.0, 1.0, 0.0), Z: (-1.0, 0.0, 0.0), O: (8.095518, 3.586917, -16.0017)]", "groups": "[]", "signal_body_entered": "[]", "signal_area_entered": "[]", "signal_input_event": "[]", "incoming_connections": "[{ \"signal\": PhysicsMaterial::[signal]changed, \"callable\": , \"flags\": 0 }]", "script_path": "res://vehicles/vehicle.gd", "script_method_list": "[{ \"name\": \"_physics_process\", \"args\": [{ \"name\": \"delta\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }]", "script_property_list": "[{ \"name\": \"engine_force_value\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4102 }, { \"name\": \"previous_speed\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"_steer_target\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"desired_engine_pitch\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }]"}}
{"type": "before_emit", "trigger": "Trigger2", "label": "Token: 1455245e", "label2": ""}
{"type": "emit_body_result", "trigger": "Trigger2", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "result": "2"}
{"type": "after_body_emit", "trigger": "Trigger2", "label": "Token: 1455245e", "label2": ""}
{"type": "emit_collided_result", "trigger": "Trigger2", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "result": "0"}
{"type": "after_emit", "trigger": "Trigger2", "label": "Token: 1455245e", "label2": "Trigger2"}
{"type": "done"}
```

我们已经能看到位置属性了，在把小车的位置改到绿块上理论就能显示 flag 了

```python
import argparse
import json
import sys
import time

import frida


PKG = "com.tencent.ACE.gamesec2026.preliminary"

JS_TEMPLATE = r"""
'use strict';

const TRIGGER_NAME = %TRIGGER_NAME%;
const TOKEN_OVERRIDE = %TOKEN_OVERRIDE%;

const state = {
  dlsymHooked: false,
  extInitHooked: false,
  resolverPtr: null,
  finished: false,
  retries: 0,
};

function resolveName(resolver, name) {
  const gp = new NativeFunction(resolver, 'pointer', ['pointer']);
  const p = gp(Memory.allocUtf8String(name));
  if (p.isNull()) {
    throw new Error('resolve failed: ' + name);
  }
  return p;
}

function stringName(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNameNew(mem, Memory.allocUtf8String(text));
  return mem;
}

function stringObj(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNewUtf8(mem, Memory.allocUtf8String(text));
  return mem;
}

function newVariant(api, ctor, rawPtr) {
  const variant = Memory.alloc(0x20);
  ctor(variant, rawPtr);
  return variant;
}

function newVariantFromString(api, text) {
  return newVariant(api, api.ctorString, stringObj(api, text));
}

function newVariantFromBool(api, value) {
  const raw = Memory.alloc(8);
  raw.writeU8(value ? 1 : 0);
  return newVariant(api, api.ctorBool, raw);
}

function newVariantFromFloat(api, value) {
  const raw = Memory.alloc(8);
  raw.writeDouble(value);
  return newVariant(api, api.ctorFloat, raw);
}

function newVariantFromObject(api, objectPtr) {
  const raw = Memory.alloc(Process.pointerSize);
  raw.writePointer(objectPtr);
  return newVariant(api, api.ctorObject, raw);
}

function newVariantFromVector3(api, x, y, z) {
  const raw = Memory.alloc(0x10);
  raw.writeFloat(x);
  raw.add(4).writeFloat(y);
  raw.add(8).writeFloat(z);
  raw.add(12).writeU32(0);
  return newVariant(api, api.ctorVector3, raw);
}

function decodeCallError(errPtr) {
  try {
    const data = new Uint8Array(errPtr.readByteArray(0x20));
    let s = '';
    for (let i = 0; i < data.length; i++) {
      s += ('0' + data[i].toString(16)).slice(-2);
    }
    return s;
  } catch (e) {
    return '<call-error-read-failed>';
  }
}

function variantToUtf8(api, variantPtr) {
  const strObj = Memory.alloc(0x10);
  api.variantStringify(variantPtr, strObj);
  const need = api.stringToUtf8(strObj, ptr(0), 0);
  const buf = Memory.alloc(Math.max(need + 4, 0x100));
  const got = api.stringToUtf8(strObj, buf, need + 1);
  try {
    return buf.readUtf8String(got);
  } catch (e) {
    return '<utf8-read-failed>';
  }
}

function callVariant(api, selfVar, methodName, args) {
  const retVar = Memory.alloc(0x20);
  const err = Memory.alloc(0x20);
  const sn = stringName(api, methodName);
  let argsPtr = ptr(0);
  if (args.length > 0) {
    argsPtr = Memory.alloc(args.length * Process.pointerSize);
    for (let i = 0; i < args.length; i++) {
      argsPtr.add(i * Process.pointerSize).writePointer(args[i]);
    }
  }
  api.variantCall(selfVar, sn, argsPtr, args.length, retVar, err);
  return { retVar: retVar, errHex: decodeCallError(err) };
}

function findChild(api, selfVar, name) {
  return callVariant(api, selfVar, 'find_child', [
    newVariantFromString(api, name),
    newVariantFromBool(api, true),
    newVariantFromBool(api, false),
  ]).retVar;
}

function getText(api, nodeVar) {
  return variantToUtf8(api, callVariant(api, nodeVar, 'get_text', []).retVar);
}

function getProperty(api, nodeVar, name) {
  return variantToUtf8(api, callVariant(api, nodeVar, 'get', [newVariantFromString(api, name)]).retVar);
}

function parseVector3Text(text) {
  const m = /\((-?[0-9.]+), (-?[0-9.]+), (-?[0-9.]+)\)/.exec(text);
  if (!m) {
    throw new Error('failed to parse Vector3 text: ' + text);
  }
  return [parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3])];
}

function buildApi(resolver) {
  const api = {
    stringNameNew: new NativeFunction(resolveName(resolver, 'string_name_new_with_latin1_chars'), 'void', ['pointer', 'pointer']),
    stringNewUtf8: new NativeFunction(resolveName(resolver, 'string_new_with_utf8_chars'), 'void', ['pointer', 'pointer']),
    getVarCtor: new NativeFunction(resolveName(resolver, 'get_variant_from_type_constructor'), 'pointer', ['int']),
    variantCall: new NativeFunction(resolveName(resolver, 'variant_call'), 'void', ['pointer', 'pointer', 'pointer', 'int', 'pointer', 'pointer']),
    variantStringify: new NativeFunction(resolveName(resolver, 'variant_stringify'), 'void', ['pointer', 'pointer']),
    stringToUtf8: new NativeFunction(resolveName(resolver, 'string_to_utf8_chars'), 'int', ['pointer', 'pointer', 'int']),
    globalGetSingleton: new NativeFunction(resolveName(resolver, 'global_get_singleton'), 'pointer', ['pointer']),
  };

  api.ctorBool = new NativeFunction(api.getVarCtor(1), 'void', ['pointer', 'pointer']);
  api.ctorFloat = new NativeFunction(api.getVarCtor(3), 'void', ['pointer', 'pointer']);
  api.ctorString = new NativeFunction(api.getVarCtor(4), 'void', ['pointer', 'pointer']);
  api.ctorVector3 = new NativeFunction(api.getVarCtor(9), 'void', ['pointer', 'pointer']);
  api.ctorObject = new NativeFunction(api.getVarCtor(24), 'void', ['pointer', 'pointer']);
  return api;
}

function tryTeleport() {
  if (state.finished || state.resolverPtr === null) {
    return;
  }

  try {
    const api = buildApi(state.resolverPtr);
    const engineObj = api.globalGetSingleton(stringName(api, 'Engine'));
    const engineVar = newVariantFromObject(api, engineObj);
    const sceneTreeVar = callVariant(api, engineVar, 'get_main_loop', []).retVar;
    const rootVar = callVariant(api, sceneTreeVar, 'get_root', []).retVar;
    const townVar = findChild(api, rootVar, 'TownScene');
    const triggerVar = findChild(api, townVar, TRIGGER_NAME);
    const labelVar = findChild(api, townVar, 'Label');
    const label2Var = findChild(api, townVar, 'Label2');
    const carVar = findChild(api, townVar, 'car');
    const bodyVar = findChild(api, townVar, 'Body');

    const townText = variantToUtf8(api, townVar);
    const triggerText = variantToUtf8(api, triggerVar);
    const label2Text = variantToUtf8(api, label2Var);
    const carText = variantToUtf8(api, carVar);
    const bodyText = variantToUtf8(api, bodyVar);
    if ([townText, triggerText, label2Text, carText, bodyText].some(v => v.indexOf('<null>') !== -1)) {
      state.retries += 1;
      if (state.retries > 20) {
        throw new Error('TownScene nodes never became ready');
      }
      setTimeout(tryTeleport, 500);
      return;
    }

    if (TOKEN_OVERRIDE.length > 0) {
      callVariant(api, labelVar, 'set_text', [newVariantFromString(api, 'Token: ' + TOKEN_OVERRIDE)]);
    }

    const triggerPosText = variantToUtf8(api, callVariant(api, triggerVar, 'get_position', []).retVar);
    const triggerPos = parseVector3Text(triggerPosText);

    send({
      type: 'plan',
      trigger: TRIGGER_NAME,
      trigger_position: triggerPosText,
      car_before: variantToUtf8(api, callVariant(api, carVar, 'get_global_transform', []).retVar),
      body_before: variantToUtf8(api, callVariant(api, bodyVar, 'get_global_transform', []).retVar),
      label2_before: getText(api, label2Var),
      car_has_set_global_position: variantToUtf8(api, callVariant(api, carVar, 'has_method', [newVariantFromString(api, 'set_global_position')]).retVar),
      body_has_set_global_position: variantToUtf8(api, callVariant(api, bodyVar, 'has_method', [newVariantFromString(api, 'set_global_position')]).retVar),
    });

    const posVar = newVariantFromVector3(api, triggerPos[0], triggerPos[1], triggerPos[2]);
    const moveCar = callVariant(api, carVar, 'set_global_position', [posVar]);
    const moveBody = callVariant(api, bodyVar, 'set_global_position', [posVar]);
    send({
      type: 'teleport',
      trigger: TRIGGER_NAME,
      car_err_hex: moveCar.errHex,
      body_err_hex: moveBody.errHex,
      car_after: variantToUtf8(api, callVariant(api, carVar, 'get_global_transform', []).retVar),
      body_after: variantToUtf8(api, callVariant(api, bodyVar, 'get_global_transform', []).retVar),
      overlaps_body: variantToUtf8(api, callVariant(api, triggerVar, 'overlaps_body', [bodyVar]).retVar),
    });

    const deltaVar = newVariantFromFloat(api, 0.016);
    for (let i = 0; i < 5; i++) {
      const procRes = callVariant(api, triggerVar, '_process', [deltaVar]);
      send({
        type: 'process_tick',
        index: i,
        err_hex: procRes.errHex,
        label2: getText(api, label2Var),
        flag1: getProperty(api, triggerVar, 'flag1Triggered'),
        flag2: getProperty(api, triggerVar, 'flag2Triggered'),
      });
    }

    setTimeout(function () {
      try {
        send({
          type: 'final',
          trigger: TRIGGER_NAME,
          label2: getText(api, label2Var),
          token_label: getText(api, labelVar),
        });
        state.finished = true;
        send({ type: 'done' });
      } catch (e) {
        state.finished = true;
        send({ type: 'error', err: String(e), stack: e.stack || '' });
      }
    }, 1500);
  } catch (e) {
    state.finished = true;
    send({ type: 'error', err: String(e), stack: e.stack || '' });
  }
}

function hookResolver(ptrValue) {
  if (state.resolverPtr !== null) {
    return;
  }
  state.resolverPtr = ptrValue;
  send({ type: 'log', msg: '[resolver] ' + ptrValue });
  setTimeout(tryTeleport, 2500);
}

function hookExtensionInit(ptrValue) {
  if (state.extInitHooked) {
    return;
  }
  state.extInitHooked = true;
  Interceptor.attach(ptrValue, {
    onEnter(args) {
      hookResolver(args[0]);
    }
  });
}

function hookDlsym() {
  if (state.dlsymHooked) {
    return;
  }
  state.dlsymHooked = true;
  const dlsymPtr = Module.getGlobalExportByName('dlsym');
  Interceptor.attach(dlsymPtr, {
    onEnter(args) {
      this.name = '<bad>';
      try {
        this.name = args[1].readCString();
      } catch (e) {
      }
    },
    onLeave(retval) {
      if (this.name === 'extension_init' && !retval.isNull()) {
        hookExtensionInit(retval);
      }
    }
  });
}

setImmediate(hookDlsym);
"""


def main():
    parser = argparse.ArgumentParser(description="Teleport car/body onto a trigger and print Label2")
    parser.add_argument("trigger_name", choices=["Trigger1", "Trigger2"], help="Target trigger node name")
    parser.add_argument("--token", default="", help="Optional token override before teleport")
    parser.add_argument("--timeout", type=int, default=18)
    args = parser.parse_args()

    js = JS_TEMPLATE.replace("%TRIGGER_NAME%", repr(args.trigger_name))
    js = js.replace("%TOKEN_OVERRIDE%", repr(args.token or ""))

    device = frida.get_usb_device(timeout=10)
    pid = device.spawn([PKG])
    print(f"[host] spawn pid={pid}")
    session = device.attach(pid)
    script = session.create_script(js)

    done = {"ok": False}

    def on_message(message, data):
        if message["type"] != "send":
            print(message)
            return
        payload = message["payload"]
        sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8", "backslashreplace"))
        sys.stdout.flush()
        if payload.get("type") in {"done", "error"}:
            done["ok"] = True

    script.on("message", on_message)
    script.load()
    device.resume(pid)

    deadline = time.time() + args.timeout
    while time.time() < deadline and not done["ok"]:
        time.sleep(1.25)


if __name__ == "__main__":
    main()
```

结果

```
rt_to_trigger.py Trigger2
[host] spawn pid=27674
{"type": "log", "msg": "[resolver] 0x786f2157bc"}
{"type": "plan", "trigger": "Trigger2", "trigger_position": "(-14.13952, 11.81643, -3.958621)", "car_before": "[X: (0.0, 0.0, 1.0), Y: (0.0, 1.0, 0.0), Z: (-1.0, 0.0, 0.0), O: (8.0, 3.36405, -16.0)]", "body_before": "[X: (0.0, 0.0, 1.0), Y: (0.0, 1.0, 0.0), Z: (-1.0, 0.0, 0.0), O: (8.095518, 3.586917, -16.0017)]", "label2_before": "", "car_has_set_global_position": "true", "body_has_set_global_position": "true"}
{"type": "teleport", "trigger": "Trigger2", "car_err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "body_err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "car_after": "[X: (0.0, 0.0, 1.0), Y: (0.0, 1.0, 0.0), Z: (-1.0, 0.0, 0.0), O: (-14.13952, 11.81643, -3.958621)]", "body_after": "[X: (0.0, 0.0, 1.0), Y: (0.0, 1.0, 0.0), Z: (-1.0, 0.0, 0.0), O: (-14.13952, 11.81643, -3.958621)]", "overlaps_body": "false"}
{"type": "process_tick", "index": 0, "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "label2": "", "flag1": "false", "flag2": "false"}
{"type": "process_tick", "index": 1, "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "label2": "", "flag1": "false", "flag2": "false"}
{"type": "process_tick", "index": 2, "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "label2": "", "flag1": "false", "flag2": "false"}
{"type": "process_tick", "index": 3, "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "label2": "", "flag1": "false", "flag2": "false"}
{"type": "process_tick", "index": 4, "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "label2": "", "flag1": "false", "flag2": "false"}
{"type": "final", "trigger": "Trigger2", "label2": "flag{sec2026_PART1_2E1C504F7162261F}  ", "token_label": "Token: 6babdf27"}
{"type": "done"}
```

至此我们已经能稳定的获得启动后的 flag 了，下一步我们就要揪出 flag 计算的来源

### 4. 算法复现之 gd 层

我们已经看出 label2 会被赋值 flag 了，那么我们应该顺着往上看看谁给 label2 赋值了

```
{"type": "node_info", "info": {"note": "label2", 
...
"incoming_connections": "[{ \"signal\": LabelSettings::[signal]changed, \"callable\": , \"flags\": 8 }, { \"signal\": Window::[signal]visibility_changed, \"callable\": , \"flags\": 0 }, { \"signal\": Window::[signal]size_changed, \"callable\": , \"flags\": 0 }, { \"signal\": Area3D(trigger.gd)::[signal]collided_with, \"callable\": Label(label2.gd)::_on_collided_with, \"flags\": 0 }, { \"signal\": Area3D(trigger.gd)::[signal]collided_with, \"callable\": Label(label2.gd)::_on_collided_with, \"flags\": 0 }]", 
...
}
```

之前的组件属性中可以看出是 trigger.gd 连接 label2.gd

在前面提取到的结果中可以看到 trigger.gd 中的方法和属性

```
"script_path": "res://Trigger/trigger.gd", "script_method_list": "[{ \"name\": \"_ready\", \"args\": [], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }, { \"name\": \"xor_enc\", \"args\": [{ \"name\": \"plain\", \"class_name\": &\"\", \"type\": 4, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 29, \"hint\": 0, \"hint_string\": \"\", \"usage\": 0 } }, { \"name\": \"_process\", \"args\": [{ \"name\": \"delta\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 131072 }], \"default_args\": [], \"flags\": 1, \"id\": 0, \"return\": { \"name\": \"\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 6 } }]", "script_property_list": "[{ \"name\": \"flag1Triggered\", \"class_name\": &\"\", \"type\": 1, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"flag2Triggered\", \"class_name\": &\"\", \"type\": 1, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"t\", \"class_name\": &\"\", \"type\": 3, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"cnt\", \"class_name\": &\"\", \"type\": 2, \"hint\": 0, \"hint_string\": \"\", \"usage\": 4096 }, { \"name\": \"obj\", \"class_name\": &\"\", \"type\": 0, \"hint\": 0, \"hint_string\": \"\", \"usage\": 135168 }]"
```

我们希望详细看看这些都干了什么，但是由于没法解密，只能上全量 hook 脚本来 trace 整个过程是怎么从 token 变成 flag 的

注入脚本

```python
import json
import sys
import time
from pathlib import Path

import frida


PKG = "com.tencent.ACE.gamesec2026.preliminary"
SOURCE_TEXT = Path("trigger_full_hook.gd").read_text(encoding="utf-8")

JS = r"""
'use strict';

const SOURCE_TEXT = %SOURCE_TEXT%;

const state = {
  dlsymHooked: false,
  extInitHooked: false,
  resolverPtr: null,
  retries: 0,
  done: false,
};

function resolveName(resolver, name) {
  const gp = new NativeFunction(resolver, 'pointer', ['pointer']);
  const p = gp(Memory.allocUtf8String(name));
  if (p.isNull()) throw new Error('resolve failed: ' + name);
  return p;
}

function stringName(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNameNew(mem, Memory.allocUtf8String(text));
  return mem;
}

function stringObj(api, text) {
  const mem = Memory.alloc(0x10);
  api.stringNewUtf8(mem, Memory.allocUtf8String(text));
  return mem;
}

function newVariant(api, ctor, rawPtr) {
  const variant = Memory.alloc(0x20);
  ctor(variant, rawPtr);
  return variant;
}

function newVariantFromString(api, text) {
  return newVariant(api, api.ctorString, stringObj(api, text));
}

function newVariantFromBool(api, value) {
  const raw = Memory.alloc(8);
  raw.writeU8(value ? 1 : 0);
  return newVariant(api, api.ctorBool, raw);
}

function newVariantFromInt(api, value) {
  const raw = Memory.alloc(8);
  raw.writeS64(value);
  return newVariant(api, api.ctorInt, raw);
}

function newVariantFromFloat(api, value) {
  const raw = Memory.alloc(8);
  raw.writeDouble(value);
  return newVariant(api, api.ctorFloat, raw);
}

function newVariantFromObject(api, objectPtr) {
  const raw = Memory.alloc(Process.pointerSize);
  raw.writePointer(objectPtr);
  return newVariant(api, api.ctorObject, raw);
}

function newVariantFromVector3(api, x, y, z) {
  const raw = Memory.alloc(0x10);
  raw.writeFloat(x);
  raw.add(4).writeFloat(y);
  raw.add(8).writeFloat(z);
  raw.add(12).writeU32(0);
  return newVariant(api, api.ctorVector3, raw);
}

function decodeCallError(errPtr) {
  try {
    const data = new Uint8Array(errPtr.readByteArray(0x20));
    let s = '';
    for (let i = 0; i < data.length; i++) s += ('0' + data[i].toString(16)).slice(-2);
    return s;
  } catch (e) {
    return '<call-error-read-failed>';
  }
}

function variantToUtf8(api, variantPtr) {
  const strObj = Memory.alloc(0x10);
  api.variantStringify(variantPtr, strObj);
  const need = api.stringToUtf8(strObj, ptr(0), 0);
  const buf = Memory.alloc(Math.max(need + 4, 0x100));
  const got = api.stringToUtf8(strObj, buf, need + 1);
  try {
    return buf.readUtf8String(got);
  } catch (e) {
    return '<utf8-read-failed>';
  }
}

function callVariant(api, selfVar, methodName, args) {
  const retVar = Memory.alloc(0x20);
  const err = Memory.alloc(0x20);
  const sn = stringName(api, methodName);
  let argsPtr = ptr(0);
  if (args.length > 0) {
    argsPtr = Memory.alloc(args.length * Process.pointerSize);
    for (let i = 0; i < args.length; i++) {
      argsPtr.add(i * Process.pointerSize).writePointer(args[i]);
    }
  }
  api.variantCall(selfVar, sn, argsPtr, args.length, retVar, err);
  return { retVar: retVar, errHex: decodeCallError(err) };
}

function findChild(api, selfVar, name) {
  return callVariant(api, selfVar, 'find_child', [
    newVariantFromString(api, name),
    newVariantFromBool(api, true),
    newVariantFromBool(api, false),
  ]).retVar;
}

function parseVector3Text(text) {
  const m = /\((-?[0-9.]+), (-?[0-9.]+), (-?[0-9.]+)\)/.exec(text);
  if (!m) throw new Error('failed to parse Vector3 text: ' + text);
  return [parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3])];
}

function installHookOnTrigger(api, triggerVar, triggerName) {
  const templateScriptVar = callVariant(api, triggerVar, 'get_script', []).retVar;
  const dupRes = callVariant(api, templateScriptVar, 'duplicate', [newVariantFromBool(api, false)]);
  const hookScriptVar = dupRes.retVar;
  send({ type: 'duplicate', trigger: triggerName, err_hex: dupRes.errHex, value: variantToUtf8(api, hookScriptVar) });

  const setRes = callVariant(api, hookScriptVar, 'set_source_code', [newVariantFromString(api, SOURCE_TEXT)]);
  send({ type: 'set_source_code', trigger: triggerName, err_hex: setRes.errHex, value: variantToUtf8(api, setRes.retVar) });

  const reloadRes = callVariant(api, hookScriptVar, 'reload', [newVariantFromBool(api, false)]);
  send({ type: 'reload', trigger: triggerName, err_hex: reloadRes.errHex, value: variantToUtf8(api, reloadRes.retVar) });

  const setScriptRes = callVariant(api, triggerVar, 'set_script', [hookScriptVar]);
  send({ type: 'set_script', trigger: triggerName, err_hex: setScriptRes.errHex, value: variantToUtf8(api, setScriptRes.retVar) });

  const readyRes = callVariant(api, triggerVar, '_ready', []);
  send({ type: 'manual_ready', trigger: triggerName, err_hex: readyRes.errHex, value: variantToUtf8(api, readyRes.retVar) });
}

function tryRun() {
  if (state.done || state.resolverPtr === null) return;
  try {
    const api = {
      stringNameNew: new NativeFunction(resolveName(state.resolverPtr, 'string_name_new_with_latin1_chars'), 'void', ['pointer', 'pointer']),
      stringNewUtf8: new NativeFunction(resolveName(state.resolverPtr, 'string_new_with_utf8_chars'), 'void', ['pointer', 'pointer']),
      getVarCtor: new NativeFunction(resolveName(state.resolverPtr, 'get_variant_from_type_constructor'), 'pointer', ['int']),
      variantCall: new NativeFunction(resolveName(state.resolverPtr, 'variant_call'), 'void', ['pointer', 'pointer', 'pointer', 'int', 'pointer', 'pointer']),
      variantStringify: new NativeFunction(resolveName(state.resolverPtr, 'variant_stringify'), 'void', ['pointer', 'pointer']),
      stringToUtf8: new NativeFunction(resolveName(state.resolverPtr, 'string_to_utf8_chars'), 'int', ['pointer', 'pointer', 'int']),
      globalGetSingleton: new NativeFunction(resolveName(state.resolverPtr, 'global_get_singleton'), 'pointer', ['pointer']),
    };
    api.ctorBool = new NativeFunction(api.getVarCtor(1), 'void', ['pointer', 'pointer']);
    api.ctorInt = new NativeFunction(api.getVarCtor(2), 'void', ['pointer', 'pointer']);
    api.ctorFloat = new NativeFunction(api.getVarCtor(3), 'void', ['pointer', 'pointer']);
    api.ctorString = new NativeFunction(api.getVarCtor(4), 'void', ['pointer', 'pointer']);
    api.ctorVector3 = new NativeFunction(api.getVarCtor(9), 'void', ['pointer', 'pointer']);
    api.ctorObject = new NativeFunction(api.getVarCtor(24), 'void', ['pointer', 'pointer']);

    const engineObj = api.globalGetSingleton(stringName(api, 'Engine'));
    const engineVar = newVariantFromObject(api, engineObj);
    const sceneTreeVar = callVariant(api, engineVar, 'get_main_loop', []).retVar;
    const rootVar = callVariant(api, sceneTreeVar, 'get_root', []).retVar;
    const townVar = findChild(api, rootVar, 'TownScene');
    const trigger1Var = findChild(api, townVar, 'Trigger1');
    const trigger2Var = findChild(api, townVar, 'Trigger2');
    const labelVar = findChild(api, townVar, 'Label');
    const label2Var = findChild(api, townVar, 'Label2');
    const carVar = findChild(api, townVar, 'car');
    const bodyVar = findChild(api, townVar, 'Body');

    const trigger2Text = variantToUtf8(api, trigger2Var);
    if (trigger2Text.indexOf('<null>') !== -1) {
      state.retries += 1;
      if (state.retries > 24) throw new Error('Trigger2 never became ready');
      setTimeout(tryRun, 500);
      return;
    }

    const psObj = api.globalGetSingleton(stringName(api, 'ProjectSettings'));
    const psVar = newVariantFromObject(api, psObj);
    const logPath = variantToUtf8(api, callVariant(api, psVar, 'globalize_path', [newVariantFromString(api, 'user://trigger_full_hook_log.txt')]).retVar);
    try {
      const f = new File(logPath, 'wb');
      f.close();
    } catch (e) {
      send({ type: 'clear_log_error', err: String(e), path: logPath });
    }

    installHookOnTrigger(api, trigger1Var, 'Trigger1');
    installHookOnTrigger(api, trigger2Var, 'Trigger2');

    const triggerPosTxt = variantToUtf8(api, callVariant(api, trigger2Var, 'get_position', []).retVar);
    const triggerPos = parseVector3Text(triggerPosTxt);
    const posVar = newVariantFromVector3(api, triggerPos[0], triggerPos[1], triggerPos[2]);

    send({
      type: 'teleport_plan',
      token_label: variantToUtf8(api, callVariant(api, labelVar, 'get_text', []).retVar),
      trigger2_position: triggerPosTxt,
      label2_before: variantToUtf8(api, callVariant(api, label2Var, 'get_text', []).retVar),
    });

    callVariant(api, carVar, 'set_global_position', [posVar]);
    callVariant(api, bodyVar, 'set_global_position', [posVar]);

    const deltaVar = newVariantFromFloat(api, 0.016);
    for (let i = 0; i < 8; i++) {
      callVariant(api, trigger1Var, '_process', [deltaVar]);
      callVariant(api, trigger2Var, '_process', [deltaVar]);
    }

    setTimeout(function () {
      try {
        let logText = '';
        try {
          const f = new File(logPath, 'rb');
          logText = f.readText();
          f.close();
        } catch (e) {
          logText = '<read-failed: ' + e + '>';
        }
        send({
          type: 'final',
          token_label: variantToUtf8(api, callVariant(api, labelVar, 'get_text', []).retVar),
          label2: variantToUtf8(api, callVariant(api, label2Var, 'get_text', []).retVar),
          log_path: logPath,
          log_text: logText,
        });
        state.done = true;
        send({ type: 'done' });
      } catch (e) {
        state.done = true;
        send({ type: 'error', err: String(e), stack: e.stack || '' });
      }
    }, 2200);
  } catch (e) {
    state.done = true;
    send({ type: 'error', err: String(e), stack: e.stack || '' });
  }
}

function hookResolver(ptrValue) {
  if (state.resolverPtr !== null) return;
  state.resolverPtr = ptrValue;
  setTimeout(tryRun, 2500);
}

function hookExtensionInit(ptrValue) {
  if (state.extInitHooked) return;
  state.extInitHooked = true;
  Interceptor.attach(ptrValue, {
    onEnter(args) {
      hookResolver(args[0]);
    }
  });
}

function hookDlsym() {
  if (state.dlsymHooked) return;
  state.dlsymHooked = true;
  const dlsymPtr = Module.getGlobalExportByName('dlsym');
  Interceptor.attach(dlsymPtr, {
    onEnter(args) {
      this.name = '<bad>';
      try { this.name = args[1].readCString(); } catch (e) {}
    },
    onLeave(retval) {
      if (this.name === 'extension_init' && !retval.isNull()) hookExtensionInit(retval);
    }
  });
}

setImmediate(hookDlsym);
"""


def main():
    device = frida.get_usb_device(timeout=10)
    pid = device.spawn([PKG])
    print(f"[host] spawn pid={pid}")
    session = device.attach(pid)
    script = session.create_script(JS.replace("%SOURCE_TEXT%", json.dumps(SOURCE_TEXT)))

    done = {"ok": False}

    def on_message(message, data):
        if message["type"] != "send":
            print(message)
            return
        payload = message["payload"]
        sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8", "backslashreplace"))
        sys.stdout.flush()
        if payload.get("type") in {"done", "error"}:
            done["ok"] = True

    script.on("message", on_message)
    script.load()
    device.resume(pid)

    deadline = time.time() + 30
    while time.time() < deadline and not done["ok"]:
        time.sleep(0.25)


if __name__ == "__main__":
    main()

```

注入的 gd 脚本

```gd
extends "res://Trigger/trigger.gd"

var _hook_process_count := 0

class ProcessProxy:
    extends RefCounted

    var real_obj
    var owner

    func _init(p_real_obj, p_owner):
        real_obj = p_real_obj
        owner = p_owner

    func Process(input):
        owner._append_log({
            "kind": "Process_enter",
            "node": owner.name,
            "real_obj": str(real_obj),
            "input_hex": input.hex_encode(),
        })
        var out = real_obj.Process(input)
        owner._append_log({
            "kind": "Process",
            "node": owner.name,
            "real_obj": str(real_obj),
            "input_hex": input.hex_encode(),
            "output": out,
        })
        return out

func _append_log(item: Dictionary) -> void:
    var mode := FileAccess.READ_WRITE if FileAccess.file_exists("user://trigger_full_hook_log.txt") else FileAccess.WRITE
    var f := FileAccess.open("user://trigger_full_hook_log.txt", mode)
    if f:
        f.seek_end()
        f.store_line(JSON.stringify(item))
        f.close()

func _merge_dict(base: Dictionary, extra: Dictionary) -> Dictionary:
    var out := {}
    for key in base.keys():
        out[key] = base[key]
    for key in extra.keys():
        out[key] = extra[key]
    return out

func _safe_label_text(label_name: String) -> String:
    var tree := get_tree()
    if tree == null or tree.root == null:
        return "<no-root>"
    var town = tree.root.find_child("TownScene", true, false)
    if town == null:
        return "<no-town>"
    var label = town.find_child(label_name, true, false)
    if label == null:
        return "<missing>"
    return str(label.text)

func _state_dict() -> Dictionary:
    return {
        "node": name,
        "cnt": cnt,
        "t": t,
        "flag1Triggered": flag1Triggered,
        "flag2Triggered": flag2Triggered,
        "obj": str(obj),
        "label_text": _safe_label_text("Label"),
        "label2_text": _safe_label_text("Label2"),
    }

func _log_state(kind: String, extra := {}) -> void:
    _append_log(_merge_dict({
        "kind": kind,
    }, _merge_dict(_state_dict(), extra)))

func _ready():
    _log_state("ready_enter")
    super._ready()
    if not is_connected("collided_with", Callable(self, "_capture_signal")):
        connect("collided_with", Callable(self, "_capture_signal"))
    _log_state("ready_after_super", {
        "obj_before_proxy": str(obj),
    })
    obj = ProcessProxy.new(obj, self)
    _log_state("ready_leave", {
        "obj_after_proxy": str(obj),
    })

func _capture_signal(name_value):
    _log_state("signal", {
        "value": name_value,
        "value_hex": str(name_value).to_utf8_buffer().hex_encode(),
    })

func xor_enc(plain):
    _log_state("xor_enc_enter", {
        "plain": plain,
        "plain_hex": plain.to_utf8_buffer().hex_encode(),
    })
    var result = super.xor_enc(plain)
    _log_state("xor_enc", {
        "plain": plain,
        "plain_hex": plain.to_utf8_buffer().hex_encode(),
        "result_hex": result.hex_encode(),
        "stack": get_stack(),
    })
    return result

func _process(delta):
    if _hook_process_count < 12:
        _log_state("process_enter", {
            "delta": delta,
            "process_index": _hook_process_count,
        })
    super._process(delta)
    if _hook_process_count < 12 or flag1Triggered or flag2Triggered or _safe_label_text("Label2") != "":
        _log_state("process_leave", {
            "delta": delta,
            "process_index": _hook_process_count,
        })
    _hook_process_count += 1

```

结果

```
{"type": "duplicate", "trigger": "Trigger1", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<GDScript#-9223371994592966872>"}
[host] spawn pid=30414
{"type": "set_source_code", "trigger": "Trigger1", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<null>"}
{"type": "reload", "trigger": "Trigger1", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "0"}
{"type": "set_script", "trigger": "Trigger1", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<null>"}
{"type": "manual_ready", "trigger": "Trigger1", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<null>"}
{"type": "duplicate", "trigger": "Trigger2", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<GDScript#-9223371994257422548>"}
{"type": "set_source_code", "trigger": "Trigger2", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<null>"}
{"type": "reload", "trigger": "Trigger2", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "0"}
{"type": "set_script", "trigger": "Trigger2", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<null>"}
{"type": "manual_ready", "trigger": "Trigger2", "err_hex": "0000000000000000000000000000000000000000000000000000000000000000", "value": "<null>"}
{"type": "teleport_plan", "token_label": "Token: 97cd4302", "trigger2_position": "(-14.13952, 11.81643, -3.958621)", "label2_before": ""}
{"type": "final", "token_label": "Token: 97cd4302", "label2": "flag{sec2026_PART1_744B541974352140}  ", "log_path": "/data/data/com.tencent.ACE.gamesec2026.preliminary/files/trigger_full_hook_log.txt", "log_text": "{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"ready_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<null>\",\"t\":0.0}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"ready_after_super\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<GameExtension#42496689961>\",\"obj_before_proxy\":\"<GameExtension#42496689961>\",\"t\":0.0}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"ready_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"obj_after_proxy\":\"<RefCounted#-9223371994307754198>\",\"t\":0.0}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"ready_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<null>\",\"t\":0.0}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"ready_after_super\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<GameExtension#42849011501>\",\"obj_before_proxy\":\"<GameExtension#42849011501>\",\"t\":0.0}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"ready_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"obj_after_proxy\":\"<RefCounted#-9223371993955432656>\",\"t\":0.0}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":0,\"t\":0.0}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":0,\"t\":0.032}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":0,\"t\":0.0}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":0,\"t\":0.032}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":1,\"t\":0.032}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":1,\"t\":0.064}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":1,\"t\":0.032}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":1,\"t\":0.064}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":2,\"t\":0.064}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":2,\"t\":0.096}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":2,\"t\":0.064}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":2,\"t\":0.096}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":3,\"t\":0.096}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":3,\"t\":0.128}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":3,\"t\":0.096}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":3,\"t\":0.128}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":4,\"t\":0.128}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":4,\"t\":0.16}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":4,\"t\":0.128}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":4,\"t\":0.16}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":5,\"t\":0.16}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":5,\"t\":0.192}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":5,\"t\":0.16}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":5,\"t\":0.192}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":6,\"t\":0.192}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":6,\"t\":0.224}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":6,\"t\":0.192}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":6,\"t\":0.224}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":7,\"t\":0.224}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":7,\"t\":0.256}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":7,\"t\":0.224}
{\"cnt\":0,\"delta\":0.016,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":7,\"t\":0.256}
{\"cnt\":0,\"delta\":0.0750000000000001,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":8,\"t\":0.256}
{\"cnt\":0,\"delta\":0.0750000000000001,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger1\",\"obj\":\"<RefCounted#-9223371994307754198>\",\"process_index\":8,\"t\":0.406}
{\"cnt\":0,\"delta\":0.0750000000000001,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":8,\"t\":0.256}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"xor_enc_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"plain\":\"97cd4302\",\"plain_hex\":\"3937636434333032\",\"t\":0.406}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"xor_enc\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"plain\":\"97cd4302\",\"plain_hex\":\"3937636434333032\",\"result_hex\":\"0e5407500703023c\",\"stack\":[],\"t\":0.406}
{\"input_hex\":\"0e5407500703023c\",\"kind\":\"Process_enter\",\"node\":\"Trigger2\",\"real_obj\":\"<GameExtension#42849011501>\"}
{\"input_hex\":\"0e5407500703023c\",\"kind\":\"Process\",\"node\":\"Trigger2\",\"output\":\"744B541974352140\",\"real_obj\":\"<GameExtension#42849011501>\"}
{\"cnt\":0,\"delta\":0.0750000000000001,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"process_leave\",\"label2_text\":\"flag{sec2026_PART1_744B541974352140}  \",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"process_index\":8,\"t\":0.406}
"}
{"type": "done"}

```

这些清楚的展现了 flag 的计算过程

```
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"xor_enc_enter\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"plain\":\"97cd4302\",\"plain_hex\":\"3937636434333032\",\"t\":0.406}
{\"cnt\":0,\"flag1Triggered\":false,\"flag2Triggered\":false,\"kind\":\"xor_enc\",\"label2_text\":\"\",\"label_text\":\"Token: 97cd4302\",\"node\":\"Trigger2\",\"obj\":\"<RefCounted#-9223371993955432656>\",\"plain\":\"97cd4302\",\"plain_hex\":\"3937636434333032\",\"result_hex\":\"0e5407500703023c\",\"stack\":[],\"t\":0.406}
{\"input_hex\":\"0e5407500703023c\",\"kind\":\"Process\",\"node\":\"Trigger2\",\"output\":\"744B541974352140\",\"real_obj\":\"<GameExtension#42849011501>\"}
```

1. `xor_enc_enter` 来 token 计算 hex
2. `xor_enc` 听着就是异或，多试几组也证实了，就是异或
3. GameExtension 也就是 native 层 Process 进行了最终处理输出就是 flag 的后缀

### 5. 算法复现之 native 层

其实早早就盯上了有个 GameExtension 也就是 libsec2026.so

ida pro 打开后发现 start 函数实际上是一个 elf 释放器

```c
void __fastcall start(size_t a1, size_t a2, size_t a3)
{
  signed __int64 v3; // x0
  int v4; // w5
  void **v5; // x1
  void **v6; // x4
  int v7; // w0
  char *v8; // t1
  void *v9; // x2
  void *v10; // x3
  void *v11; // x4
  void *v12; // x5
  void *v13; // x6
  signed __int64 v14; // x0
  int v15; // w15
  void *v16; // x7
  __int64 v17; // x14
  ssize_t v18; // x0
  void *v19; // x14
  int v20; // w0
  void *v21; // [xsp+0h] [xbp-30h] BYREF
  size_t v22[4]; // [xsp+8h] [xbp-28h] BYREF

  v22[1] = a1;
  v22[2] = a2;
  v22[3] = a3;
  v22[0] = 6048;
  v3 = linux_eabi_syscall(__NR_openat, 0, "/proc/self/auxv", 0);
  v4 = v3;
  v5 = &v21;
  v6 = (void **)((char *)&v22[-1] + linux_eabi_syscall(__NR_read, v3, &v21, 0x200u));
  v7 = linux_eabi_syscall(__NR_close, v4);
  do
  {
    v8 = (char *)*v5;
    v5 += 2;
  }
  while ( v8 != &byte_6 && v5 < v6 );
  sub_69984(&dword_69A6C, 4129, &v21, v22);
  v14 = linux_eabi_syscall(__NR_memfd_create, byte_69970, 0, v9, v10, v11, v12, v13);
  v15 = v14;
  v21 = v16;
  v18 = linux_eabi_syscall(__NR_write, v14, &v21, *(_QWORD *)(v17 + 8));
  v21 = linux_eabi_syscall(__NR_mmap, 0, v22[0], 5, 2, v15, 0);
  v19 = v21;
  v20 = linux_eabi_syscall(__NR_close, v15);
  __asm { BR              X14; word_10 }
}
```

1. 先读 `/proc/self/auxv`
2. 调 `sub_69984(...)` 做一段解包/还原
3. 用 `memfd_create` 创建匿名内存文件
4. 把解出来的内容 `write` 进去
5. 再 `mmap` 成可执行内存
6. 最后 `BR X14` 直接跳转执行

通过动态 dump 重建的 elf 格式正确，解析也没太大问题，但是函数很碎很难看，最后其实是多跑了几组数据看出了 native 层也是一个异或，直接得出了 flag 算法计算

### 最终 flag 正向算法

```c++
#include <array>
#include <cctype>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

constexpr std::array<std::uint8_t, 8> kPart1Key = {
    0x7A, 0x1F, 0x53, 0x49, 0x73, 0x36, 0x23, 0x7C,
};

std::string normalize_token(std::string token) {
    if (token.size() != 8) {
        throw std::runtime_error("expected exactly 8 hex characters");
    }
    for (char &ch : token) {
        if (!std::isxdigit(static_cast<unsigned char>(ch))) {
            throw std::runtime_error("invalid hex token");
        }
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return token;
}

std::array<std::uint8_t, 8> xor_enc(const std::string &plain) {
    std::array<std::uint8_t, 8> out{};
    for (std::size_t i = 0; i < 7; ++i) {
        out[i] = static_cast<std::uint8_t>(plain[i] ^ plain[i + 1]);
    }
    out[7] = static_cast<std::uint8_t>(plain[7] ^ out[0]);
    return out;
}

std::array<std::uint8_t, 8> native_process(const std::array<std::uint8_t, 8> &input) {
    std::array<std::uint8_t, 8> out{};
    for (std::size_t i = 0; i < input.size(); ++i) {
        out[i] = static_cast<std::uint8_t>(input[i] ^ kPart1Key[i]);
    }
    return out;
}

std::string hex_upper(const std::array<std::uint8_t, 8> &bytes) {
    std::ostringstream oss;
    oss << std::uppercase << std::hex << std::setfill('0');
    for (auto byte : bytes) {
        oss << std::setw(2) << static_cast<unsigned>(byte);
    }
    return oss.str();
}

}  // namespace

int main(int argc, char **argv) {
    if (argc != 2) {
        std::cerr << "usage: flag <8-hex-token>\n";
        return 1;
    }

    try {
        const std::string token = normalize_token(argv[1]);
        const auto stage1 = xor_enc(token);
        const auto payload = native_process(stage1);
        const std::string payload_hex = hex_upper(payload);

        std::cout << "flag=flag{sec2026_PART1_" << payload_hex << "}" << '\n';
        return 0;
    } catch (const std::exception &ex) {
        std::cerr << ex.what() << '\n';
        return 1;
    }
}

```

### 最终 flag 逆向算法

```c++

#include <array>
#include <cstdint>
#include <iostream>
#include <string>

namespace {
    constexpr std::array<std::uint8_t, 8> kPart1Key = {
        0x7A, 0x1F, 0x53, 0x49, 0x73, 0x36, 0x23, 0x7C,
    };
}

std::string reverse_algo(const std::string& flag) {
    std::string payload_hex = flag.substr(flag.find("PART1_") + 6);
    if (!payload_hex.empty() && payload_hex.back() == '}') {
        payload_hex.pop_back();
    }

    std::array<std::uint8_t, 8> payload{};
    for (std::size_t i = 0; i < 8; ++i) {
        std::string byte_str = payload_hex.substr(i * 2, 2);
        payload[i] = static_cast<std::uint8_t>(std::stoi(byte_str, nullptr, 16));
    }

    std::array<std::uint8_t, 8> stage1{};
    for (std::size_t i = 0; i < 8; ++i) {
        stage1[i] = payload[i] ^ kPart1Key[i];
    }

    std::string token(8, '0');
    token[7] = static_cast<char>(stage1[7] ^ stage1[0]);
    for (int i = 6; i >= 0; --i) {
        token[i] = static_cast<char>(token[i + 1] ^ stage1[i]);
    }

    return token;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        std::cerr << "usage: reflag flag{sec2026_PART1_XXXXXXXXXXXXXXXX}\n";
        return 1;
    }

    try {
        std::string flag = argv[1];
        std::cout << "token=" << reverse_algo(flag) << '\n';
        return 0;
    } catch (const std::exception &ex) {
        std::cerr << ex.what() << '\n';
        return 1;
    }
}
```