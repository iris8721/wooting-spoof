import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import hid

VID = 0x31E3
NORMAL_PID_BASE = 0x1320
BOOTLOADER_PID = 0x132F
CONFIG_USAGE_PAGE = 0xFF55
BOOTLOADER_USAGE_PAGE = 0xFFFF
FIRMWARE_VERSION = "2.14.2"
FIRMWARE_URL = "https://wootility.io/api/fw/get_update_data"
FIRMWARE_BACKEND_ID = 9
STOCK_PATH = os.path.join("firmware", "wooting_60he_plus_2.14.2.fwr")
STOCK_SHA256 = "087cf384a9584c4f414965030b3b8e451632abaa6ea09eaac68960f777c33be3"
STOCK_FLAT_SIZE = 483820
APP_BASE = 0x08007000
BASE_LITERAL_ADDRESS = 0x0800C2D0
SERIAL_PAGE = 0x080FF000
FAKE_STRUCT_ADDRESS = 0x0807D1EC
PAGE_SIZE = 256

BOOT_PING = 0x00
BOOT_ERASE_APP = 0x02
BOOT_WRITE_APP_PAGE = 0x03
BOOT_GET_APP_CRC = 0x04
BOOT_RESET_CPU = 0x05
BOOT_UNLOCK = 0x06
BOOT_UNLOCK_MAGIC = 0xFFAAFFBB
BOOT_PACKET_SIZE = 256
BOOT_REPORT_SIZE = 64
BOOT_RESPONSE_MAGIC = b"\xDF\xDB"

READER_PROLOGUE = bytes.fromhex("45 4b 70 b5 b3 f8 fc 20")
PATCH_SITE_STOCK = bytes.fromhex(
    "0b 48 00 90 0d f1 19 03 01 93 02 92 0c 49 73 46 04 f1 16 02 68 46"
)
READER_PROLOGUE_OFFSET = -0x11C
PID_CHECK_OFFSET = -0x118
CODE_REGION_OFFSET = -0x28
CODE_REGION_SIZE = 0x24
STAGE_CHARS = {0: "H", 1: "P", 2: "T", 3: "E", 4: "X"}
SUPPLIER = 1
YEAR = 2
WEEK = 3
PRODUCT = 4
REVISION = 5
PRODUCT_ID = 6
STAGE = 7
VARIANT = 9
PCB = 10
MINOR = 11


def interface(pid, usage_page):
    for candidate in hid.enumerate(VID, pid):
        if candidate.get("usage_page") == usage_page:
            return candidate
    return None


def open_interface(pid, usage_page):
    candidate = interface(pid, usage_page)
    if candidate is None:
        return None
    device = hid.device()
    device.open_path(candidate["path"])
    return device


def normal_interface():
    for candidate in hid.enumerate(VID):
        if candidate.get("usage_page") != CONFIG_USAGE_PAGE:
            continue
        if candidate["product_id"] & 0xFFF0 == NORMAL_PID_BASE:
            return candidate
    return None


def bootloader_interface():
    return interface(BOOTLOADER_PID, BOOTLOADER_USAGE_PAGE)


def feature_command(device, command, parameter=0):
    device.send_feature_report(
        bytes([0x01, 0xD1, 0xDA, command]) + struct.pack("<I", parameter)
    )


def boot_feature_command(device, command, parameter=0):
    device.send_feature_report(
        bytes([0x00, 0xDF, 0xDB, command]) + struct.pack("<I", parameter)
    )


def read_boot_packet(device, timeout=5.0):
    deadline = time.time() + timeout
    packet = bytearray()
    while len(packet) < BOOT_PACKET_SIZE:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        report = device.read(2048, int(min(0.1, remaining) * 1000) or 1)
        if not report:
            continue
        report = bytes(report)
        if len(report) > BOOT_REPORT_SIZE and report[0] == 0x00:
            report = report[1:]
        packet.extend(report)
    return bytes(packet[:BOOT_PACKET_SIZE])


def boot_command(device, command, parameter=0, timeout=5.0):
    boot_feature_command(device, command, parameter)
    deadline = time.time() + timeout
    while time.time() < deadline:
        packet = read_boot_packet(device, max(0.001, deadline - time.time()))
        if len(packet) < 5 or packet[:2] != BOOT_RESPONSE_MAGIC:
            continue
        if packet[2] not in (command, 0xFF):
            continue
        status = packet[3]
        length = packet[4]
        body = packet[5:5 + length]
        if status != 0x88:
            raise RuntimeError(
                f"bootloader command 0x{command:02X} failed with status 0x{status:02X}: {body.hex()}"
            )
        return body
    raise TimeoutError(f"bootloader command 0x{command:02X} timed out")


def read_config_body(device, command, parameter=0, timeout=3.0):
    feature_command(device, command, parameter)
    deadline = time.time() + timeout
    while time.time() < deadline:
        report = device.read(2048, 100)
        if not report:
            continue
        data = bytes(report)
        if len(data) > 1 and data[0] == 0x01 and data[1:3] == b"\xD1\xDA":
            data = data[1:]
        if data[:2] != b"\xD1\xDA" or len(data) < 6 or data[2] != command:
            continue
        if data[3] != 0x88:
            raise RuntimeError(
                f"command 0x{command:02X} failed with status 0x{data[3]:02X}"
            )
        length = data[4] | (data[5] << 8)
        return data[6:6 + length]
    raise TimeoutError(f"command 0x{command:02X} timed out")


def read_version(device):
    body = read_config_body(device, 0x01)
    return ".".join(str(part) for part in body[:3])


def read_serial(device):
    return read_config_body(device, 0x03, 0x02)


def read_varint(payload, offset):
    value = 0
    shift = 0
    while True:
        byte = payload[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7


def decode_serial(payload):
    fields = {}
    offset = 0
    while offset < len(payload):
        tag = payload[offset]
        offset += 1
        number = tag >> 3
        wire_type = tag & 7
        if wire_type == 0:
            fields[number], offset = read_varint(payload, offset)
        elif wire_type == 2:
            length, offset = read_varint(payload, offset)
            fields[number] = payload[offset:offset + length]
            offset += length
        else:
            raise ValueError(f"unsupported wire type {wire_type}")
    return fields


def format_serial(fields, product_id):
    serial = "A%02dB%02d%02dW%02d" % (
        fields.get(SUPPLIER, 0) & 0xFF,
        fields.get(YEAR, 0) & 0xFF,
        fields.get(WEEK, 0) & 0xFF,
        fields.get(PRODUCT, 0) & 0xFF,
    )
    if PCB in fields:
        serial += "T%02d" % (fields[PCB] & 0xFF)
    serial += str(fields.get(REVISION, 0))
    if MINOR in fields:
        serial += "%02d" % (fields[MINOR] & 0xFF)
    if VARIANT in fields:
        serial += "S%02d" % (fields[VARIANT] & 0xFF)
    serial += STAGE_CHARS.get(fields.get(STAGE, 0), "?")
    serial += "%05d" % (product_id & 0xFFFF)
    return serial


def parse_intel_hex(path):
    memory = {}
    upper = 0
    base_address = None
    with open(path, "r", encoding="ascii", errors="replace") as source:
        for line_number, line in enumerate(source, 1):
            line = line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise ValueError(f"{path}:{line_number}: missing ':'")
            record = bytes.fromhex(line[1:])
            count = record[0]
            address = (record[1] << 8) | record[2]
            record_type = record[3]
            payload = record[4:4 + count]
            checksum = record[4 + count]
            if (sum(record[:-1]) + checksum) & 0xFF:
                raise ValueError(f"{path}:{line_number}: bad checksum")
            if record_type == 0x00:
                absolute = upper + address
                if base_address is None:
                    base_address = absolute
                for index, byte in enumerate(payload):
                    memory[absolute + index] = byte
            elif record_type == 0x01:
                break
            elif record_type == 0x04:
                if count != 2 or address != 0:
                    raise ValueError(f"{path}:{line_number}: bad extended linear address")
                upper = struct.unpack(">H", payload)[0] << 16
            elif record_type == 0x02:
                if count != 2 or address != 0:
                    raise ValueError(f"{path}:{line_number}: bad extended segment address")
                upper = struct.unpack(">H", payload)[0] << 4
            elif record_type == 0x05:
                continue
            else:
                raise ValueError(f"{path}:{line_number}: unsupported record type {record_type}")
    if base_address is None:
        raise ValueError(f"{path}: no data records")
    low = min(memory)
    high = max(memory)
    flat = bytearray([0xFF]) * (high - low + 1)
    for address, byte in memory.items():
        flat[address - low] = byte
    return low, bytes(flat)


def xmega_crc32(data):
    polynomial = 0x0080001B
    crc = 0
    for index in range(0, len(data), 2):
        help_a = (crc << 1) & 0x00FFFFFE
        help_b = crc & (1 << 23)
        if help_b:
            help_b = 0x00FFFFFF
        word = (data[index + 1] << 8) | data[index]
        crc = (help_a ^ word ^ (help_b & polynomial)) & 0x00FFFFFF
    return crc


def pad_image(data):
    padded = bytearray(data)
    if len(padded) % PAGE_SIZE:
        padded += b"\xFF" * (PAGE_SIZE - len(padded) % PAGE_SIZE)
    return bytes(padded)


def stock_image(allow_network=True):
    if os.path.isfile(STOCK_PATH):
        with open(STOCK_PATH, "rb") as source:
            data = source.read()
    else:
        if not allow_network:
            raise FileNotFoundError("stock firmware image not found")
        query = urllib.parse.urlencode(
            {
                "device": FIRMWARE_BACKEND_ID,
                "wversion": "5.4.2",
                "fversion": FIRMWARE_VERSION,
                "update_channel": "stable",
            }
        )
        request = urllib.request.Request(
            FIRMWARE_URL + "?" + query, headers={"User-Agent": "Wooting/5.4.2"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            text = json.loads(response.read()).get("result", "")
        if not isinstance(text, str) or not text.startswith(":"):
            raise RuntimeError("updater returned no firmware")
        data = text.encode("ascii")
        os.makedirs(os.path.dirname(STOCK_PATH), exist_ok=True)
        with open(STOCK_PATH, "wb") as target:
            target.write(data)
    if hashlib.sha256(data).hexdigest() != STOCK_SHA256:
        raise ValueError("stock firmware hash mismatch")
    return STOCK_PATH, parse_intel_hex(STOCK_PATH)


def movs_r0(immediate):
    return struct.pack("<H", 0x2000 | (immediate & 0xFF))


def strb_r0_r4(offset):
    return struct.pack("<H", 0x7000 | ((offset & 0x1F) << 6) | (4 << 3))


def code_patch(fields):
    patch = bytearray()
    for value_offset, key in ((0x0E, VARIANT), (0x10, PCB), (0x12, MINOR)):
        present = 1 if key in fields else 0
        value = (fields.get(key, 0) or 0) & 0xFF
        patch += movs_r0(present) + strb_r0_r4(value_offset - 1)
        patch += movs_r0(value) + strb_r0_r4(value_offset)
    patch += movs_r0(1) + strb_r0_r4(0x14)
    patch += struct.pack("<HH", 0xB012, 0xBD70)
    if len(patch) > CODE_REGION_SIZE:
        raise ValueError("code patch exceeds the writable region")
    return bytes(patch)


def fake_struct(fields, product_id):
    return struct.pack(
        "<HBBHHHB",
        fields.get(SUPPLIER, 0) & 0xFFFF,
        fields.get(YEAR, 0) & 0xFF,
        fields.get(WEEK, 0) & 0xFF,
        fields.get(PRODUCT, 0) & 0xFFFF,
        fields.get(REVISION, 0) & 0xFFFF,
        product_id & 0xFFFF,
        fields.get(STAGE, 0) & 0xFF,
    ) + b"\x00\x01\x00"


def patched_image(base, flat, fields, product_id):
    if base != APP_BASE:
        raise ValueError(f"unexpected image base 0x{base:08X}")
    if len(flat) != STOCK_FLAT_SIZE:
        raise ValueError(f"unexpected stock image length {len(flat)}")
    anchor = BASE_LITERAL_ADDRESS - base
    if struct.unpack("<I", flat[anchor:anchor + 4])[0] != SERIAL_PAGE:
        raise ValueError("unexpected serial page literal")
    prologue = flat[
        anchor + READER_PROLOGUE_OFFSET:
        anchor + READER_PROLOGUE_OFFSET + len(READER_PROLOGUE)
    ]
    if prologue != READER_PROLOGUE:
        raise ValueError("unexpected reader prologue")
    region = flat[
        anchor + CODE_REGION_OFFSET:
        anchor + CODE_REGION_OFFSET + len(PATCH_SITE_STOCK)
    ]
    if region != PATCH_SITE_STOCK:
        raise ValueError("unexpected extended decoder setup")
    if base + len(flat) != FAKE_STRUCT_ADDRESS:
        raise ValueError("unexpected fake struct address")
    image = bytearray(flat)
    image.extend(fake_struct(fields, product_id))
    image[anchor:anchor + 4] = struct.pack("<I", FAKE_STRUCT_ADDRESS)
    image[anchor + PID_CHECK_OFFSET:anchor + PID_CHECK_OFFSET + 4] = b"\x00\x22\x00\xBF"
    patch = code_patch(fields)
    image[anchor + CODE_REGION_OFFSET:anchor + CODE_REGION_OFFSET + len(patch)] = patch
    return bytes(image)


def wait_for_bootloader(timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bootloader_interface() is not None:
            return
        time.sleep(0.2)
    raise TimeoutError("bootloader did not appear")


def enter_bootloader(product_id):
    device = open_interface(product_id, CONFIG_USAGE_PAGE)
    if device is None:
        raise RuntimeError("configuration interface not found")
    try:
        feature_command(device, 0x02)
    finally:
        device.close()
    wait_for_bootloader()


def leave_bootloader():
    device = open_interface(BOOTLOADER_PID, BOOTLOADER_USAGE_PAGE)
    if device is None:
        return
    try:
        boot_command(device, BOOT_RESET_CPU, 1, timeout=1)
    except Exception:
        pass
    finally:
        device.close()


def flash(padded, crc):
    device = open_interface(BOOTLOADER_PID, BOOTLOADER_USAGE_PAGE)
    if device is None:
        raise RuntimeError("bootloader interface not found")
    try:
        body = boot_command(device, BOOT_PING)
        if not body or body[0] != 0xFF:
            raise RuntimeError("bootloader ping failed")
        boot_command(device, BOOT_UNLOCK, BOOT_UNLOCK_MAGIC)
        pages = len(padded) // PAGE_SIZE
        boot_command(device, BOOT_ERASE_APP, pages, timeout=10)
        for page in range(pages):
            chunk = padded[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
            for offset in range(0, PAGE_SIZE, BOOT_REPORT_SIZE):
                device.write(bytes([0x00]) + chunk[offset:offset + BOOT_REPORT_SIZE])
            boot_command(device, BOOT_WRITE_APP_PAGE, page)
            if page % 128 == 0 or page == pages - 1:
                print(f"page {page + 1}/{pages}")
        body = boot_command(device, BOOT_GET_APP_CRC, timeout=30)
        if len(body) < 3:
            raise RuntimeError(f"short CRC response {body.hex()}")
        reported = body[0] | (body[1] << 8) | (body[2] << 16)
        if reported != crc:
            raise RuntimeError(
                f"CRC mismatch: device 0x{reported:06X}, image 0x{crc:06X}"
            )
        try:
            boot_command(device, BOOT_RESET_CPU, 1, timeout=1)
        except Exception:
            pass
    finally:
        device.close()


def wait_for_normal(timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if normal_interface() is not None:
            return
        time.sleep(0.2)


def device_state():
    candidate = normal_interface()
    if candidate is None:
        return None
    device = open_interface(candidate["product_id"], CONFIG_USAGE_PAGE)
    if device is None:
        return None
    try:
        version = read_version(device)
        fields = decode_serial(read_serial(device))
        return {
            "product_id": candidate["product_id"],
            "usb_serial": candidate.get("serial_number"),
            "version": version,
            "fields": fields,
        }
    finally:
        device.close()


def wootility_running():
    if sys.platform != "win32":
        return False
    output = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Wootility.exe"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return "Wootility.exe" in output


def print_state(state):
    print(f"model:      Wooting 60HE+ ({state['product_id']:04X})")
    print(f"usb serial: {state['usb_serial']}")
    print(f"firmware:   {state['version']}")
    print(f"serial:     {format_serial(state['fields'], state['fields'].get(PRODUCT_ID, 0))}")
    print(f"fields:     {state['fields']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--product-id", type=lambda value: int(value, 0))
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()

    if arguments.status:
        state = device_state()
        if state is None:
            sys.exit("60HE+ not found")
        print_state(state)
        return

    if wootility_running() and not arguments.force:
        sys.exit("Wootility is running; close it first or pass --force")

    state = device_state()
    if state is None:
        if bootloader_interface() is None:
            sys.exit("60HE+ not found")
        if not arguments.recover:
            leave_bootloader()
            state = device_state()
            if state is None:
                sys.exit("device is in bootloader mode; use --recover")

    image_path, (base, flat) = stock_image(allow_network=not arguments.no_network)

    if arguments.recover:
        padded = pad_image(flat)
        crc = xmega_crc32(padded)
        print("mode:    recover")
        print(f"image:   {image_path}")
        print(f"pages:   {len(padded) // PAGE_SIZE}")
        print(f"crc:     0x{crc:06X}")
    else:
        if arguments.product_id is None:
            sys.exit("--product-id is required unless --recover is used")
        if not 1 <= arguments.product_id <= 0xFFFF:
            sys.exit("--product-id must be 1..65535")
        if state["version"] != FIRMWARE_VERSION:
            print(f"installing {FIRMWARE_VERSION} over {state['version']}")
        patched = patched_image(base, flat, state["fields"], arguments.product_id)
        padded = pad_image(patched)
        crc = xmega_crc32(padded)
        print("mode:    patch")
        print(f"image:   {image_path}")
        print(f"pages:   {len(padded) // PAGE_SIZE}")
        print(f"crc:     0x{crc:06X}")
        print(
            f"serial:  {state['usb_serial']} -> "
            f"{format_serial(state['fields'], arguments.product_id)}"
        )

    if not arguments.apply:
        print("dry run")
        return

    if not arguments.yes:
        if input("Type flash to continue: ").strip() != "flash":
            print("aborted")
            return

    if state is not None:
        enter_bootloader(state["product_id"])
    else:
        wait_for_bootloader()
    flash(padded, crc)
    wait_for_normal()

    state = device_state()
    if state is None:
        sys.exit("device did not return in normal mode")

    if arguments.recover:
        print(f"recovered: {state['usb_serial']}")
        return

    expected = format_serial(state["fields"], arguments.product_id)
    if state["usb_serial"] != expected:
        sys.exit(f"verification failed: expected {expected}, got {state['usb_serial']}")
    if state["version"] != FIRMWARE_VERSION:
        sys.exit(f"unexpected firmware version {state['version']}")
    print(f"serial:  {expected}")
    print("OK")


if __name__ == "__main__":
    main()
