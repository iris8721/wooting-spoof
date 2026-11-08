# Wooting 60HE+ Firmware Interface

Applies to firmware 2.14.2.

## 1. Device

| Property | Value |
|---|---|
| Model | Wooting 60HE+ |
| VID | `0x31E3` |
| Normal PID | base `0x1320`, variant `0x2` (`0x1322`) |
| Bootloader PID | `0x132F` (`base | 0x0F`) |
| Configuration usage page | `0xFF55` / `0x01` |
| Bootloader usage page | `0xFFFF` / `0x01` |
| Bootloader version | 2.0.0 |
| Flash page | 256 bytes |

USB interfaces:

| MI | Usage page : usage | Purpose | Report sizes |
|---|---|---|---|
| 00 | `0xFF00:0x01` | legacy vendor, unused | |
| 01 | `0x01:0x06` | keyboard | |
| 02 | `0xFF55:0x01` | configuration, commands and reports | in 2047, out 2047, feature 8 |
| 03 | `0x01:0x80`, `0x0C:0x01`, mouse | system, consumer, mouse | |
| 04 | `0xFF54:0x01` | analog key stream | |

Report sizes include the report ID byte. The configuration interface is MI_02. The bootloader interface reports input 65, output 65, feature 8.

## 2. Configuration protocol

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
| `0x66` | unknown |
| `0x77` | busy |
| `0x99` | overflow |
| `0xAA` | unsupported |
| `0xFF` | error |

Output reports carry bulk data:

```
D1 DA <logical_report_id> <length_lo> <length_hi> <body>
```

The transport selects a HID output report by total buffer length and pads to its logical size:

| Buffer length | HID report ID | Logical size |
|---|---|---|
| ≤ 32 | 1 | 32 |
| ≤ 62 | 2 | 62 |
| ≤ 254 | 3 | 254 |
| ≤ 510 | 4 | 510 |
| ≤ 1022 | 5 | 1022 |
| ≤ 2046 | 6 | 2046 |

The physical report is padded to 2046 bytes. Output reports have no response.

### Report IDs

| ID | Name |
|---:|---|
| `0x07` | `DeviceConfig` |
| `0x08` | `SetDKSProfile` |
| `0x0B` | `WootDevRawReport` |
| `0x0C` | `SerialNumber` |
| `0x0E` | `RgbProfileColorsPart1` |
| `0x0F` | `RgbProfileColorsPart2` |
| `0x11` | `KeyboardProfile` |
| `0x12` | `GamepadMapping` |
| `0x13` | `GamepadProfile` |
| `0x14` | `MappingProfile` |
| `0x15` | `ActuationProfile` |
| `0x16` | `RgbProfileCore` |
| `0x17` | `GlobalSettings` |
| `0x18` | `AKCProfile` |
| `0x19` | `RapidTriggerProfile` |
| `0x1A` | `ProfileMetadata` |
| `0x1B` | `RgbLayer` |
| `0x1C` | `RGBBins` |
| `0x1D` | `FullRapidTriggerProfile` |
| `0x1E` | `RGBLedBarReport` |
| `0x1F` | `ExternalDataSubscriptionsUpdate` |
| `0x20` | `LEDBarProfile` |
| `0x21` | `GlobalLEDBarProfile` |
| `0x22` | `LEDBarProfileMetadata` |
| `0x23` | `GlobalLEDBarProfileMetadata` |
| `0x24` | `SecuritySetPrivateKey` |
| `0x25` | `SecuritySetCertificate` |
| `0x26` | `SecuritySetChallenge` |
| `0x27` | `SetHandshake` |
| `0x28` | `SensorConfigProfile` |
| `0x29` | `SensorConfigSwitchOverride` |
| `0x2A` | `SensorConfigReapply` |
| `0x2B` | `SensorConfigWiggleOverride` |
| `0x2C` | `LinkedAppProfile` |

### Command IDs

| ID | Name | ID | Name |
|---:|---|---:|---|
| `0x00` | `Ping` | `0x2D` | `StartXinputDetection` |
| `0x01` | `GetVersion` | `0x2E` | `StopXinputDetection` |
| `0x02` | `ResetToBootloader` | `0x2F` | `SaveDKSProfile` |
| `0x03` | `GetSerial` | `0x30` | `GetMappingProfile` |
| `0x07` | `ReloadProfile0` | `0x31` | `GetActuationProfile` |
| `0x08` | `SaveRgbProfile` | `0x32` | `GetRgbProfileCore` |
| `0x0B` | `GetCurrentKeyboardProfileIndex` | `0x33` | `GetGlobalSettings` |
| `0x13` | `GetDeviceConfig` | `0x34` | `GetAKCProfile` |
| `0x14` | `GetAnalogValues` | `0x35` | `SaveAKCProfile` |
| `0x15` | `KeysOff` | `0x36` | `GetRapidTriggerProfile` |
| `0x16` | `KeysOn` | `0x37` | `GetProfileMetadata` |
| `0x17` | `ActivateProfile` | `0x38` | `IsFlashChipConnected` |
| `0x18` | `getDKSProfile` | `0x39` | `GetRgbLayer` |
| `0x19` | `doSoftReset` | `0x3A` | `GetFlashStats` |
| `0x1E` | `WootDevSingleColor` | `0x3B` | `GetRGBBins` |
| `0x1F` | `WootDevResetColor` | `0x3C` | `_Dev` |
| `0x20` | `WootDevResetAll` | `0x3D` | `GetFullRapidTriggerProfile` |
| `0x21` | `WootDevInit` | `0x3E` | `GetProfileCount` |
| `0x23` | `GetRgbProfileColorsPart1` | `0x3F` | `DeleteProfile` |
| `0x24` | `GetRgbProfileColorsPart2` | `0x40` | `CreateProfile` |
| `0x26` | `ReloadProfile` | `0x41` | `GetExternalDataSubscriptions` |
| `0x27` | `GetKeyboardProfile` | `0x42` | `GetLEDBarProfile` |
| `0x28` | `GetGamepadMapping` | `0x43` | `GetGlobalLEDBarProfile` |
| `0x29` | `GetGamepadProfile` | `0x44` | `GetLEDBarColors` |
| `0x2A` | `SaveKeyboardProfile` | `0x45` | `GetUSBSpeed` |
| `0x2B` | `ResetSettings` | `0x46` | `GetLEDBarProfileMetadata` |
| `0x2C` | `SetRawScanning` | `0x47` | `GetGlobalLEDBarProfileMetadata` |
| `0x48` | `GetProfileSaveTracker` | `0x51` | `GetHandshake` |
| `0x49` | `Heartbeat` | `0x52` | `GetSensorConfigProfile` |
| `0x4A` | `GetKeyboardColors` | `0x53` | `GetSupportedSwitches` |
| `0x4B` | `EventSubscriptionsClear` | `0x54` | `SetLinkedProfile` |
| `0x4C` | `EventSubscription` | `0x55` | `GetLinkedProfile` |
| `0x4D` | `SetScanningDebugForceSlow` | `0x56` | `GetLinkedAppProfileCount` |
| `0x4E` | `SecurityManage` | `0x57` | `GetLinkedAppProfile` |
| `0x4F` | `SecurityGetCertificate` | `0x58` | `SetScanningDebugForcedQueueCount` |
| `0x50` | `SecurityExecuteChallenge` | | |

IDs `0x04`–`0x06`, `0x09`–`0x0A`, `0x0C`–`0x12`, `0x1A`–`0x1D`, `0x22`, and `0x25` are reserved removed commands.

`GetSerial` parameters:

| `p0` | Meaning |
|---:|---|
| 0 | legacy serial struct |
| 1 | MCU UID at `0x1FFFF7E8`, 12 bytes |
| 2 | protobuf `SerialNumber` |
| 3 | flash chip IDs |

Response headers:

```
GetVersion:  D1 DA 01 88 03 00 02 0E 02       firmware 2.14.2
Ping:        D1 DA 00 88 01 00 FF
```

## 3. Dispatch

Firmware 2.14.2 uses a 89-entry table at `0x08029A28`, 4 bytes per entry. Entries are Thumb handler addresses; zero entries are unsupported. The dispatcher validates magic `0xDAD1` and rejects IDs above `0x58`.

| Item | Address |
|---|---|
| Dispatch table | `0x08029A28` |
| `GetSerial` handler | `0x0800C459` |
| Serial reader | `0x0800C1B4` |

## 4. Memory map

| Address | Contents |
|---|---|
| `0x08000000`–`0x08006FFF` | bootloader, 28 KB |
| `0x08007000`–`0x0807D1EB` | application 2.14.2, 483,820 bytes |
| `0x0807D1EC`–`0x0807D1FF` | unused `0xFF` tail of the last application page |
| `0x080FF000`–`0x080FF01D` | serial page, used range 30 bytes |
| `0x080FFFFC` | product ID word read by the serial reader |
| `0x1FFFF7E8`–`0x1FFFF7F3` | STM32 96-bit UID |

The application image starts at `0x08007000`. The serial page is outside the application image and is not written by application updates.

## 5. Serial number storage

### Protobuf `SerialNumber`

| Tag | Field | Type |
|---:|---|---|
| 1 | `SupplierNumber` | uint32 |
| 2 | `Year` | uint32 |
| 3 | `WeekNumber` | uint32 |
| 4 | `ProductNumber` | uint32 |
| 5 | `RevisionNumber` | uint32 |
| 6 | `ProductId` | uint32 |
| 7 | `Stage` | uint32 |
| 9 | `Variant` | optional uint32 |
| 10 | `UniquePCBDesign` | optional uint32 |
| 11 | `MinorRevision` | optional uint32 |

Tag 8 is unused. `Stage` values:

| Value | Stage |
|---:|---|
| 0 | Mass (`H`) |
| 1 | PVT (`P`) |
| 2 | DVT (`T`) |
| 3 | EVT (`E`) |
| 4 | Prototype (`X`) |

### Legacy flash struct

| Offset | Size | Field |
|---:|---:|---|
| 0 | 2 | SupplierNumber |
| 2 | 1 | Year |
| 3 | 1 | WeekNumber |
| 4 | 2 | ProductNumber |
| 6 | 2 | RevisionNumber |
| 8 | 2 | ProductId |
| 10 | 1 | Stage |
| 11 | 1 | padding |
| 12 | 1 | extended length, 0 or 1–254 |
| 13 | n | extended protobuf |
| `0x14` | 1 | reader success flag |

### Reader

The reader at `0x0800C1B4`:

1. Loads the PID-check base `0x080FFF00` from the literal at `0x0800C2CC`.
2. Reads a uint16 at `0x080FFF00 + 0xFC` (`0x080FFFFC`).
3. If that value is `0x1337` or `0x1338`, takes the special-product path.
4. Loads the scan base `0x080FF000` from `0x0800C2D0` and the scan end `0x080FF01E` from `0x0800C2D4`.
5. Scans from the base until a byte other than `0xFF` or the scan end.
6. Copies `0x1E` bytes to the stack.
7. Parses the legacy fields.
8. If byte 12 is 1–254, decodes the extended protobuf at offset 13.
9. Returns `1` on success, `-2` for an invalid or erased serial, `-3` for an extended decode failure.

Serial reader literals:

| Address | Value | Purpose |
|---|---|---|
| `0x0800C2CC` | `0x080FFF00` | PID-check base |
| `0x0800C2D0` | `0x080FF000` | scan base |
| `0x0800C2D4` | `0x080FF01E` | scan end |
| `0x0800C2DC` | `0x080FF002` | callback argument |

### Output struct

The reader fills a struct with these fields:

| Offset | Meaning |
|---:|---|
| `0x0C` | stage |
| `0x0D` | variant present |
| `0x0E` | variant |
| `0x0F` | unique PCB present |
| `0x10` | unique PCB design |
| `0x11` | minor revision present |
| `0x12` | minor revision |
| `0x14` | reader success flag |

The extended protobuf schema is at `0x08029DCC`, its field list at `0x08029DF0` is `{0x0A, 0x07, 0x0B}`, and the stream callback is `0x08008565`.

### Serial write

`SerialNumber` is report `0x0C`. The 2.14.2 dispatch entry for `0x0C` is zero, so the firmware ignores the report. The serial page is not writable through the configuration protocol.

## 6. Bootloader interface

The bootloader enumerates as `31E3:132F` on usage page `0xFFFF`, report ID `0`, magic `0xDBDF`.

Command feature report, 8 bytes:

```
00 DF DB <command> <p0> <p1> <p2> <p3>
```

Each response is a 256-byte logical packet sent as four 64-byte input reports:

```
DF DB FF <status> <length> <body...>
```

The command byte is `0xFF`. The first report carries the header and body; the next three are zero padding. All four reports must be consumed before the next command is sent.

### Commands

| ID | Name | Parameter | Result |
|---:|---|---|---|
| `0x00` | `Ping` | 0 | body `FF` plus restore flags |
| `0x01` | `GetVersion` | 0 | `02 00` = 2.0.0 |
| `0x02` | `EraseApp` | page count | `0x88`; count 0 is rejected |
| `0x03` | `WriteAppPage` | page index | `0x88` |
| `0x04` | `GetAppCrc` | 0 | 4-byte body, first 3 bytes are the CRC |
| `0x05` | `ResetCpu` | 1 | resets the MCU |
| `0x06` | `Unlock` | `0xFFAAFFBB` | unlocks erase and write |
| `0x07` | `ResetFlash` | 0 | resets settings flash |
| `0x08` | `GetLastWrittenPage` | 0 | `0x66` unsupported |
| `0x09` | `GetSerial` | 0 or 1 | `0x66` unsupported |

`Ping` body byte 1 flags:

| Bit | Meaning |
|---:|---|
| 0 | restore key combination pressed |
| 1 | magic code present |
| 2 | user program invalid |

### CRC

The bootloader uses a 24-bit XMEGA CRC with polynomial `0x0080001B` over the padded image:

```text
crc = 0
for each 16-bit little-endian word w:
    helpA = (crc << 1) & 0x00FFFFFE
    helpB = crc & (1 << 23)
    if helpB != 0:
        helpB = 0x00FFFFFF
    crc = (helpA ^ w ^ (helpB & 0x0080001B)) & 0x00FFFFFF
```

`WriteAppPage` updates the CRC register incrementally. A fresh bootloader session reports `0x000000` from `GetAppCrc` until pages are written.

### Flash sequence

1. `Unlock(0xFFAAFFBB)`.
2. `EraseApp(pages)`.
3. For each page: write 256 bytes as four 64-byte output reports, then `WriteAppPage(page)`.
4. `GetAppCrc()` and compare.
5. Optionally `ResetFlash()`.
6. `ResetCpu(1)`.

## 7. Firmware image

`.fwr` files are Intel HEX text. Record types:

| Type | Meaning |
|---:|---|
| `0x00` | data |
| `0x01` | end of file |
| `0x04` | extended linear address |
| `0x05` | start linear address |

Parsing:

1. Track the extended linear address.
2. Use the first data record to establish the base address.
3. Fill gaps with `0xFF`.
4. Return a flat buffer starting at the first data address.
5. Pad to a multiple of 256 before flashing.

Firmware 2.14.2:

| Property | Value |
|---|---|
| Base | `0x08007000` |
| Flat size | 483,820 bytes |
| Last data address | `0x0807D1EB` |
| Padded size | `0x76200` |
| Pages | 1,890 |

The 60HE+ bootloader checks the CRC, not a signature.
