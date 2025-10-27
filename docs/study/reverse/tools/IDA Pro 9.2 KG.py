# -*- coding: utf-8 -*-

import json
import hashlib
import os
import platform

# IDA Pro可能的安装路径（根据你的实际情况修改）
IDA_PATHS = [
    r"D:\Program Files\IDA Pro 9.2",
    r"D:\Program Files\IDA Pro 9.1",
    r"D:\Program Files\IDA Professional 9.2",
    r"C:\Program Files\IDA Pro",
    r"D:\IDA",
    # 添加其他可能的路径
]

license = {
    "header": {"version": 1},
    "payload": {
        "name": "IDAPRO9",
        "email": "idapro9@example.com",
        "licenses": [
            {
                "id": "48-2137-ACAB-99",
                "edition_id": "ida-pro",
                "description": "license",
                "license_type": "named",
                "product": "IDA",
                "product_id": "IDAPRO",
                "product_version": "9.1",
                "seats": 1,
                "start_date": "2024-08-10 00:00:00",
                "end_date": "2033-12-31 23:59:59",
                "issued_on": "2024-08-10 00:00:00",
                "owner": "HexRays",
                "add_ons": [],
                "features": [],
            }
        ],
    },
}


def add_every_addon(license):
    """添加所有插件到许可证"""
    platforms = [
        "W",  # Windows
        "L",  # Linux
        "M",  # macOS
    ]
    addons = [
        "HEXX86",
        "HEXX64",
        "HEXARM",
        "HEXARM64",
        "HEXMIPS",
        "HEXMIPS64",
        "HEXPPC",
        "HEXPPC64",
        "HEXRV64",
        "HEXARC",
        "HEXARC64",
    ]

    i = 0
    for addon in addons:
        i += 1
        license["payload"]["licenses"][0]["add_ons"].append(
            {
                "id": f"48-1337-0000-{i:02}",
                "code": addon,
                "owner": license["payload"]["licenses"][0]["id"],
                "start_date": "2024-08-10 00:00:00",
                "end_date": "2033-12-31 23:59:59",
            }
        )


add_every_addon(license)


def json_stringify_alphabetical(obj):
    """将对象转换为排序后的JSON字符串"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def buf_to_bigint(buf):
    """字节缓冲区转换为大整数"""
    return int.from_bytes(buf, byteorder="little")


def bigint_to_buf(i):
    """大整数转换为字节缓冲区"""
    return i.to_bytes((i.bit_length() + 7) // 8, byteorder="little")


# 原始HexRays公钥模数
pub_modulus_hexrays = buf_to_bigint(
    bytes.fromhex(
        "edfd425cf978546e8911225884436c57140525650bcf6ebfe80edbc5fb1de68f4c66c29cb22eb668788afcb0abbb718044584b810f8970cddf227385f75d5dddd91d4f18937a08aa83b28c49d12dc92e7505bb38809e91bd0fbd2f2e6ab1d2e33c0c55d5bddd478ee8bf845fcef3c82b9d2929ecb71f4d1b3db96e3a8e7aaf93"
    )
)

# 修补后的公钥模数（5C -> CB）
pub_modulus_patched = buf_to_bigint(
    bytes.fromhex(
        "edfd42cbf978546e8911225884436c57140525650bcf6ebfe80edbc5fb1de68f4c66c29cb22eb668788afcb0abbb718044584b810f8970cddf227385f75d5dddd91d4f18937a08aa83b28c49d12dc92e7505bb38809e91bd0fbd2f2e6ab1d2e33c0c55d5bddd478ee8bf845fcef3c82b9d2929ecb71f4d1b3db96e3a8e7aaf93"
    )
)

# 私钥
private_key = buf_to_bigint(
    bytes.fromhex(
        "77c86abbb7f3bb134436797b68ff47beb1a5457816608dbfb72641814dd464dd640d711d5732d3017a1c4e63d835822f00a4eab619a2c4791cf33f9f57f9c2ae4d9eed9981e79ac9b8f8a411f68f25b9f0c05d04d11e22a3a0d8d4672b56a61f1532282ff4e4e74759e832b70e98b9d102d07e9fb9ba8d15810b144970029874"
    )
)


def decrypt(message):
    """解密消息"""
    decrypted = pow(buf_to_bigint(message), exponent, pub_modulus_patched)
    decrypted = bigint_to_buf(decrypted)
    return decrypted[::-1]


def encrypt(message):
    """加密消息"""
    encrypted = pow(buf_to_bigint(message[::-1]), private_key, pub_modulus_patched)
    encrypted = bigint_to_buf(encrypted)
    return encrypted


exponent = 0x13


def sign_hexlic(payload: dict) -> str:
    """为许可证payload生成签名"""
    data = {"payload": payload}
    data_str = json_stringify_alphabetical(data)

    buffer = bytearray(128)
    # 前33字节是随机数据
    for i in range(33):
        buffer[i] = 0x42

    # 计算数据的SHA256哈希
    sha256 = hashlib.sha256()
    sha256.update(data_str.encode())
    digest = sha256.digest()

    # 将哈希值复制到缓冲区
    for i in range(32):
        buffer[33 + i] = digest[i]

    # 加密缓冲区
    encrypted = encrypt(buffer)

    return encrypted.hex().upper()


def patch(filename):
    """修补文件中的公钥模数"""
    if not os.path.exists(filename):
        print(f"跳过: {filename} - 文件未找到")
        return False

    try:
        with open(filename, "rb") as f:
            data = f.read()

        # 检查是否已经修补
        if data.find(bytes.fromhex("EDFD42CBF978")) != -1:
            print(f"已修补: {filename} - 文件已经修补过")
            return True

        # 检查是否包含原始模数
        if data.find(bytes.fromhex("EDFD425CF978")) == -1:
            print(f"无法修补: {filename} - 不包含原始模数")
            return False

        # 执行修补
        data = data.replace(
            bytes.fromhex("EDFD425CF978"), bytes.fromhex("EDFD42CBF978")
        )

        # 创建备份
        backup_file = filename + ".backup"
        if not os.path.exists(backup_file):
            with open(backup_file, "wb") as f:
                f.write(open(filename, "rb").read())
            print(f"已创建备份: {backup_file}")

        # 写入修补后的文件
        with open(filename, "wb") as f:
            f.write(data)

        print(f"✓ 成功修补: {filename}")
        return True

    except Exception as e:
        print(f"✗ 修补失败: {filename} - 错误: {e}")
        return False


def find_and_patch_ida_files():
    """查找并修补IDA文件"""
    # 所有可能的IDA文件目标
    targets = [
        "ida.dll", "ida32.dll", "ida64.dll",
        "ida.exe", "ida32.exe", "ida64.exe",
        "libida.so", "libida32.so", "libida64.so",
        "libida.dylib", "libida32.dylib", "libida64.dylib"
    ]

    found_files = []
    patched_files = []

    print("\n" + "=" * 60)
    print("查找IDA Pro文件...")
    print("=" * 60)

    # 搜索所有可能的路径
    search_paths = IDA_PATHS.copy()

    # 添加当前目录
    search_paths.append(os.getcwd())

    # 添加环境变量路径
    if 'IDA_DIR' in os.environ:
        search_paths.append(os.environ['IDA_DIR'])

    for ida_path in search_paths:
        if os.path.exists(ida_path):
            print(f"\n搜索路径: {ida_path}")
            for target in targets:
                full_path = os.path.join(ida_path, target)
                if os.path.exists(full_path):
                    found_files.append(full_path)
                    print(f"  找到: {target}")

    # 如果没有找到文件，尝试在Program Files中搜索
    if not found_files:
        program_files = [os.environ.get('ProgramFiles', r'C:\Program Files')]
        if os.environ.get('ProgramFiles(x86)'):
            program_files.append(os.environ['ProgramFiles(x86)'])

        for pf in program_files:
            for root, dirs, files in os.walk(pf):
                if 'IDA' in root:
                    for file in files:
                        if any(target in file for target in ['ida', 'libida']):
                            full_path = os.path.join(root, file)
                            if os.path.exists(full_path) and os.path.isfile(full_path):
                                found_files.append(full_path)
                                print(f"  找到: {full_path}")

    # 修补找到的文件
    if found_files:
        print(f"\n找到 {len(found_files)} 个文件，开始修补...")
        for file_path in found_files:
            if patch(file_path):
                patched_files.append(file_path)
    else:
        print("\n⚠️ 未找到任何IDA Pro文件")

    return patched_files


def verify_license():
    """验证生成的许可证文件"""
    try:
        with open('idapro.hexlic', 'r', encoding='utf-8') as f:
            license_data = json.load(f)

        print("\n" + "=" * 60)
        print("许可证验证信息")
        print("=" * 60)
        print(f"名称: {license_data['payload']['name']}")
        print(f"邮箱: {license_data['payload']['email']}")
        print(f"产品: {license_data['payload']['licenses'][0]['product']}")
        print(f"版本: {license_data['payload']['licenses'][0]['product_version']}")
        print(
            f"有效期: {license_data['payload']['licenses'][0]['start_date']} 至 {license_data['payload']['licenses'][0]['end_date']}")
        print(f"插件数量: {len(license_data['payload']['licenses'][0]['add_ons'])}")
        print(f"签名长度: {len(license_data['signature'])} 字符")

        # 检查签名格式
        signature = license_data['signature']
        if len(signature) == 512:  # 256字节的十六进制字符串应该是512字符
            print("✓ 签名长度正确")
        else:
            print(f"⚠️ 签名长度异常: {len(signature)} (期望: 512)")

        # 检查文件大小
        file_size = os.path.getsize('idapro.hexlic')
        print(f"文件大小: {file_size} 字节")

        return True

    except Exception as e:
        print(f"✗ 许可证验证错误: {e}")
        return False


def manual_patch_instructions():
    """显示手动修补说明"""
    print("\n" + "=" * 60)
    print("手动修补说明")
    print("=" * 60)
    print("如果自动修补失败，请手动操作：")
    print("1. 使用十六进制编辑器（如HxD、010 Editor）")
    print("2. 打开IDA的DLL或EXE文件")
    print("3. 搜索十六进制值: ED FD 42 5C F9 78")
    print("4. 替换为: ED FD 42 CB F9 78")
    print("5. 保存文件")
    print("\n需要修补的文件通常包括：")
    print("   - ida64.dll / ida64.exe (64位版本)")
    print("   - ida32.dll / ida32.exe (32位版本)")
    print("   - libida64.so / libida64.dylib (Linux/macOS)")


def usage_instructions():
    """显示使用说明"""
    print("\n" + "=" * 60)
    print("使用说明")
    print("=" * 60)
    print("1. 许可证文件: idapro.hexlic")
    print("   位置: 当前目录")
    print("")
    print("2. 安装步骤:")
    print("   a) 将 idapro.hexlic 复制到:")
    print("      IDA安装目录/licenses/ 文件夹")
    print("")
    print("   b) 确保IDA库文件已正确修补")
    print("      (将5C改为CB)")
    print("")
    print("3. 启动IDA Pro，应该会自动加载许可证")
    print("")
    print("4. 如果遇到问题:")
    print("   - 检查文件是否修补成功")
    print("   - 尝试手动修补")
    print("   - 确保许可证文件在正确位置")


def main():
    """主函数"""
    print("IDA Pro 许可证生成器")
    print("版本: 1.0")
    print("=" * 60)

    # 生成许可证
    try:
        print("\n生成许可证...")
        license["signature"] = sign_hexlic(license["payload"])
        serialized = json_stringify_alphabetical(license)

        with open("idapro.hexlic", "w", encoding='utf-8') as f:
            f.write(serialized)

        print("✓ 许可证文件生成成功: idapro.hexlic")

    except Exception as e:
        print(f"✗ 许可证生成失败: {e}")
        return

    # 验证许可证
    verify_license()

    # 查找并修补文件
    patched_files = find_and_patch_ida_files()

    # 显示结果
    if patched_files:
        print(f"\n✓ 成功修补 {len(patched_files)} 个文件")
    else:
        print("\n⚠️ 没有文件被修补，需要手动操作")
        manual_patch_instructions()

    # 显示使用说明
    usage_instructions()

    # 显示许可证文件内容预览
    try:
        with open('idapro.hexlic', 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"\n许可证文件预览 (前200字符):")
            print(content[:200] + "..." if len(content) > 200 else content)
    except:
        pass


if __name__ == "__main__":
    main()