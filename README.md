# Wooting 60HE+ Bootloader and Flashing

Firmware 2.14.2.

## 1. USB identity

| Role | VID:PID | Usage page | Interface |
|---|---|---|---|
| Normal keyboard | `31E3:1322` | `0xFF55` / `0x01` | MI_02 configuration |
| Bootloader | `31E3:132F` | `0xFFFF` / `0x01` | MI_00 |

The normal PID is a base plus a low-nibble variant: `0x1322 & 0xFFF0 = 0x1320`. The bootloader PID is `base | 0x0F`.

Normal interfaces:

| MI | Usage | Purpose |
|---|---|---|
| 00 | `0xFF00:0x01` | legacy vendor, unused |
| 01 | `0x01:0x06` | keyboard |
| 02 | `0xFF55:0x01` | configuration, commands and reports |
| 03 | system/consumer/mouse | |
| 04 | `0xFF54:0x01` | analog stream |

`HIDP_CAPS` for MI_02: input 2047, output 2047, feature 8 bytes, including the report ID.

`HIDP_CAPS` for the bootloader: input 65, output 65, feature 8 bytes, including the report ID.

## 2. Configuration protocol

Used to talk to the keyboard and to request the bootloader.

Feature command, report ID `1`, 8 bytes:

```
01 D1 DA <command> <p0> <p1> <p2> <p3>
```

`D1 DA` is magic `0xDAD1` little-endian. `p0..p3` is a 32-bit parameter little-endian.

Response input report:

```
D1 DA <command> <status> <length_lo> <length_hi> <body>
```

| Status | Meaning |
|---|---|
| `0x88` | success |
| `0x66` | unknown / unsupported |
| `0x77` | busy |
| `0x99` | overflow |
| `0xAA` | unsupported |
| `0xFF` | error |

`ResetToBootloader` is command `0x02` with parameter `0`. The keyboard does not reply; it resets into the bootloader and re-enumerates as `31E3:132F` on usage page `0xFFFF`.

## 3. Bootloader protocol

The bootloader uses report ID `0` and magic `0xDBDF`.

Command feature report, 8 bytes:

```
00 DF DB <command> <p0> <p1> <p2> <p3>
```

Every response is a 256-byte logical packet sent as four 64-byte input reports:

```
DF DB FF <status> <length> <body...>
```

- `FF` is placed in the command byte instead of echoing the command ID.
- `length` is one byte.
- The first report contains the header and body; the next three are zero padding.
- The reports arrive roughly 1 ms apart.

All four reports must be consumed before the next feature command. Returning after the first report and sending the next command desynchronizes the bootloader; the command is dropped. Symptom: `Ping` succeeds, then `GetVersion`, `GetAppCrc`, and `EraseApp` time out.

The bootloader interface is classified as `V2_SplitPackets`: the 64-byte output report descriptor makes the transport expect 256-byte packets, so input reports are accumulated until 256 bytes have arrived.

Raw responses:

```
Ping         DF DB FF 88 01 FF          + 3 x 64 zero bytes
GetVersion   DF DB FF 88 02 02 00       + 3 x 64 zero bytes
GetAppCrc    DF DB FF 88 04 00 00 00 00 + 3 x 64 zero bytes
EraseApp(0)  DF DB FF FF 04 00 00 00 00 + 3 x 64 zero bytes
```

## 4. Bootloader commands

| ID | Name | Parameter | Result |
|---:|---|---|---|
| `0x00` | `Ping` | 0 | body `FF` plus restore flags byte |
| `0x01` | `GetVersion` | 0 | body `02 00` = 2.0.0 |
| `0x02` | `EraseApp` | page count | `0x88` in about 20 ms; count `0` is rejected with `0xFF` |
| `0x03` | `WriteAppPage` | page index | `0x88`; commits four output reports as one page |
| `0x04` | `GetAppCrc` | 0 | 4-byte body; first 3 bytes are the CRC, little-endian |
| `0x05` | `ResetCpu` | 1 | resets the MCU |
| `0x06` | `Unlock` | `0xFFAAFFBB` | must precede erase |
| `0x07` | `ResetFlash` | 0 | resets settings flash; not required for an app update |
| `0x08` | `GetLastWrittenPage` | 0 | `0x66` unsupported |
| `0x09` | `GetSerial` | 0 or 1 | `0x66` unsupported |

`Ping` restore flags:

| Bit | Meaning |
|---:|---|
| 0 | restore key combination pressed |
| 1 | magic code present |
| 2 | user program invalid |

## 5. Flash layout

| Address | Contents |
|---|---|
| `0x08000000`–`0x08006FFF` | bootloader, 28 KB |
| `0x08007000`–`0x0807D1EB` | application 2.14.2, 483,820 bytes |
| `0x0807D1EC`–`0x0807D1FF` | unused `0xFF` tail of the last app page |
| `0x080FF000`–`0x080FF01D` | serial page, used range 30 bytes |
| `0x080FFFFC` | product ID word read by the serial routine |
| `0x1FFFF7E8`–`0x1FFFF7F3` | STM32 96-bit UID |

The bootloader pages are 256 bytes. The 2.14.2 image pads to `0x76200` = 1,890 pages. The serial page is outside the application image and is not written by an app update.

## 6. Firmware image format

`.fwr` files are Intel HEX text. Used record types:

| Type | Meaning |
|---:|---|
| `0x00` | data |
| `0x01` | end of file |
| `0x04` | extended linear address |
| `0x05` | start linear address |

Parsing:

1. Track the extended linear address.
2. The first data record establishes the base address.
3. Fill gaps with `0xFF`.
4. Return a flat buffer starting at the first data address.
5. Pad the flat buffer to a multiple of 256 before flashing.

2.14.2 image values:

| Property | Value |
|---|---|
| Base | `0x08007000` |
| Flat size | 483,820 bytes |
| Last data address | `0x0807D1EB` |
| Padded size | `0x76200` |
| Pages | 1,890 |
| Stock CRC | `0xF990D8` |

## 7. CRC

The bootloader uses a 24-bit XMEGA CRC with polynomial `0x0080001B`:

```text
crc = 0
for each 16-bit little-endian word w in the padded image:
    helpA = (crc << 1) & 0x00FFFFFE
    helpB = crc & (1 << 23)
    if helpB != 0:
        helpB = 0x00FFFFFF
    crc = (helpA ^ w ^ (helpB & 0x0080001B)) & 0x00FFFFFF
```

The CRC register is built incrementally by `WriteAppPage`. It reads `0x000000` on a fresh bootloader session before any page write, so `GetAppCrc` is only meaningful after the upload. The stock 2.14.2 image has CRC `0xF990D8`; patched images have a different CRC determined by their contents.

## 8. Flashing sequence

1. Close Wootility. It holds MI_02 and interferes with bootloader entry.
2. Open the normal configuration interface and read version and serial.
3. Send `ResetToBootloader` (`0x02`) on MI_02 and close the handle.
4. Wait for `31E3:132F` on usage page `0xFFFF`.
5. `Ping`, expect body `FF`.
6. `Unlock(0xFFAAFFBB)`.
7. `EraseApp(pages)`, where `pages = padded_size / 256`.
8. For each page `0..pages-1`:
   - write the 256-byte chunk as four 64-byte output reports, each prefixed with report ID `0`;
   - `WriteAppPage(page)`.
9. `GetAppCrc()` and compare with the computed 24-bit CRC.
10. Optionally `ResetFlash()`.
11. `ResetCpu(1)`.
12. Wait for the normal device to re-enumerate and verify version and serial.

Timing:

| Step | Duration |
|---|---|
| `Unlock` → `EraseApp` reply | about 20 ms |
| Page write interval | about 13.7 ms |
| 1,890 pages | about 26 s |
| Full flash including bootloader entry and verification | about 27 s |

Page data is fire-and-forget. There is no per-report acknowledgement; the page is committed by `WriteAppPage`.

## 9. Serial reader and patch

The spoofer changes the serial read path only. The serial page is not written.

2.14.2 reader addresses:

| Item | Address |
|---|---|
| Reader entry | `0x0800C1B4` |
| `GET_SERIAL` handler | `0x0800C459` |
| Base literal | `0x0800C2D0` |
| PID check instruction | `0x0800C1B8` |
| Extended decoder setup | `0x0800C2A8` |
| Fake struct | `0x0807D1EC` |

The reader loads its scan base from the literal at `0x0800C2D0`. Pointing that literal at `0x0807D1EC` makes it read a fake struct in the last page's `0xFF` tail.

Fake struct, 14 bytes:

```
<supplier u16> <year u8> <week u8> <product u16> <revision u16>
<product_id u16> <stage u8> <pad u8> <extended_length u8> <extended_byte u8>
```

The extended-length byte is `1`, which selects the extended serial branch. The patched branch writes the optional fields directly into the output struct instead of invoking the firmware protobuf decoder:

| Output offset | Meaning |
|---:|---|
| `0x0C` | stage |
| `0x0D` | variant present |
| `0x0E` | variant |
| `0x0F` | unique PCB present |
| `0x10` | unique PCB |
| `0x11` | minor revision present |
| `0x12` | minor revision |
| `0x14` | reader success flag |

The PID check at `0x0800C1B8` reads `0x080FFFFC`. It is replaced with `movs r2,#0; nop` so the patched reader never takes the special-product path.

The reader function's stack frame is `0x12` bytes. The patched epilogue is `add sp,#0x12; pop {r4,r5,r6,pc}`.

## 10. Tool

`tools/wooting_spoof.py` is specific to the 60HE+.

```bash
python tools/wooting_spoof.py --status
python tools/wooting_spoof.py --product-id 00001
python tools/wooting_spoof.py --product-id 00001 --apply --yes
python tools/wooting_spoof.py --recover --apply --yes
```

Behavior:

| Flag | Effect |
|---|---|
| `--status` | reads model, USB serial, firmware, decoded serial fields |
| `--product-id N` | dry run unless `--apply` |
| `--apply` | writes to the device |
| `--yes` | skips the interactive confirmation |
| `--recover` | flashes the stock 2.14.2 image |
| `--no-network` | disables fetching the stock image |
| `--force` | skips the Wootility check |

Image acquisition order:

1. `firmware/wooting_60he_plus_2.14.2.fwr`, if present locally
2. `https://wootility.io/api/fw/get_update_data?device=9&wversion=5.4.2&fversion=2.14.2&update_channel=stable`

The firmware image is not included in this repository. It is fetched from the updater and cached in `firmware/`. The fetched image is verified against the pinned SHA-256 before use.

The tool preserves the unit's supplier, year, week, product number, revision, stage, variant, PCB design, and minor revision. Only the 16-bit ProductId changes.

## 11. Verification

After a successful flash:

- `GET_VERSION` returns `2.14.2`.
- `GET_SERIAL` param 2 returns the new serial protobuf.
- The USB iSerial string matches the formatted serial.
- The bootloader-reported CRC matched the image CRC.

Example verified run:

```
serial:  <original-serial> -> <new-serial>
crc:     <computed-crc>
page 1890/1890
serial:  <new-serial>
OK
```

Recovery test:

```
python tools/wooting_spoof.py --recover --apply --yes
crc:     0xF990D8
recovered: <original-serial>
```

The original serial returning after a stock flash proves the serial page was never modified.

## 12. Failure modes

| Symptom | Cause | Action |
|---|---|---|
| `Ping` works, later commands time out | response framing desync: not all four input reports consumed | reassemble 256-byte responses |
| `EraseApp` times out after a previous timeout | same desync | fix framing first |
| `GET_SERIAL` on the bootloader times out | old firmware also desyncs; `0x66` is the normal unsupported reply | not required for flashing |
| Wootility cannot open the device | Wootility is running | close it |
| CRC mismatch | wrong image, interrupted write, or desync | reflash stock; device stays in bootloader |
| Device stays in bootloader | app invalid or interrupted flash | `--recover` from bootloader mode |
| `60HE+ not found` | wrong PID or bootloader mode | check USB identity |

A CRC mismatch aborts before `ResetCpu`, leaving the device in the bootloader. The next `--recover` restores it.

## 13. Constraints

- The patch is tied to the 60HE+ 2.14.2 application image and its reader addresses.
- The 60HE v2 and 80HE+ use a different reader and a secure bootloader with certificate attestation.
- The 80HE uses a different reader and serial page at `0x007FF000`.
- AVR boards use a different architecture and the legacy 128-byte transport.
- Wootility firmware updates overwrite the patch; reapply after updating.

## 14. Reference

`docs/wooting-60he-plus-firmware-interface.md` contains the full protocol and serial format reference.
