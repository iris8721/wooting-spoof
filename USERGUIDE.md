# User Guide

For the Wooting 60HE+ on firmware 2.14.2.

## Requirements

- Wooting 60HE+
- Python 3.10 or newer
- `hidapi`
- Wootility closed, including the tray icon

## Install

```bash
git clone <repository-url>
cd wooting-spoof
pip install hidapi
```

The firmware image is downloaded automatically on first use and cached in `firmware/`.

## Check the keyboard

```bash
python tools/wooting.py --status
```

This prints the model, USB serial, firmware version, and decoded serial fields. It does not write anything.

## Choose a ProductId

The serial ends in a five-digit ProductId. Choose a number from 1 to 65535. Everything else in the serial is preserved.

## Dry run

```bash
python tools/wooting.py --product-id 00001
```

This builds the patched image, prints the old and new serial, and computes the CRC without touching the keyboard.

## Flash

```bash
python tools/wooting.py --product-id 00001 --apply --yes
```

The tool enters the bootloader, erases the application, writes 1,890 pages, compares the CRC, resets, and verifies the USB serial. Do not unplug the keyboard during this step.

## Verify

```bash
python tools/wooting.py --status
```

The USB serial and the decoded serial should show the new ProductId.

## Restore

```bash
python tools/wooting.py --recover --apply --yes
```

This flashes the stock 2.14.2 image. The original serial returns because the serial page is never modified.

## Common problems

| Problem | Fix |
|---|---|
| `Wootility is running` | Close Wootility completely |
| `60HE+ not found` | Check the USB cable and that the keyboard is not in bootloader mode |
| `device is in bootloader mode; use --recover` | Run the restore command above |
| `CRC mismatch` | Do not unplug; run the restore command above |
| `stock firmware hash mismatch` | Delete `firmware/` and run again to re-download |

## Limits

- Only the 60HE+.
- Wootility firmware updates overwrite the patch; reapply after updating.
- The tool refuses other models, secure-bootloader models, and AVR boards.
