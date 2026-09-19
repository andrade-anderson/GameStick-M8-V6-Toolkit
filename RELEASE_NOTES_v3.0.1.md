# Game Stick M8 v6 Toolkit v3.0.1

## Mega Drive / Genesis format update

Version 3.0.1 expands Mega Drive / Genesis ROM detection.

Supported Mega Drive extensions:

- `.bin`
- `.md`
- `.gen`
- `.smd`

All of them are added to the game database using:

```text
class_type = 5
emu_type = 2
```

### Usage

Copy the extracted ROM files to:

```text
roms\md\
```

Then run:

```text
3 - Build / rebuild game database
```

ZIP and RAR archives must be extracted first.

### Compatibility

The DATA03 patch behavior is unchanged from v3.0.0.
The confirmed development firmware remains:

```text
M8-20231122-release-v6.0
```

Mega Drive `.md`, `.gen` and `.smd` support should be hardware-tested on the
target M8 v6 before publishing v3.0.1 as the final release.
