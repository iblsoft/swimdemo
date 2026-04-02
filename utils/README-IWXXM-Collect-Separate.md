# IWXXM Collect Separator Service

## Overview

The IWXXM Collect Separator is a service that monitors an input folder for meteorological data files and automatically extracts individual IWXXM reports from WMO collect bulletins.

- Supports both plain XML and WMO01 encapsulated file formats
- Automatically separates `collect:MeteorologicalBulletin` files into individual IWXXM reports
- Preserves WMO headings and file format (WMO01 files produce WMO01 output, one report per WMO01 file)
- Runs continuously as a SystemD user service
- Atomic file operations ensure data integrity

The service monitors `/opt/SWIMWeather/var/input/upload/` for new files and:

1. **Plain XML files** containing:
   - Single IWXXM reports → moved to output folder unchanged
   - `collect:MeteorologicalBulletin` → extracted into individual IWXXM reports

2. **WMO01 encapsulated files** containing one or more messages:
   - Each message is extracted
   - Messages with `collect:MeteorologicalBulletin` are separated into individual reports
   - Output preserves WMO01 format with original WMO headings

All extracted reports are stored in `/opt/SWIMWeather/var/input/object/` with sequential counter suffixes (e.g., `filename_001.xml`, `filename_002.xml` if there were two IWXXM reports in collect:MeteorologicalBulletin).

## Installation and Setup

SWIM Weather should already be installed with environment  set up with `$METPATH` defined. We assume below that the system is running under account "swim".

### Step 1: Deploy the Utils Folder

Copy the `utils` folder from <https://github.com/iblsoft/swimdemo/tree/main/utils> to your SWIM Weather installation:

```bash
cp -r utils $METPATH/
```

Check if the script can run using:

```bash
python3 $METPATH/utils/iwxxm-collect-separate.py --help
```

Create the log directory for the service and an upload directory into which e.g. a message switch such as IBL Moving Weather will be uploading data:

```bash
mkdir -p $METPATH/var/input/log/
mkdir -p $METPATH/var/input/upload/
```

### Step 4: Configure SystemD User Service

Run as user "swim":

```bash
# Create user systemd directory if it doesn't exist
mkdir -p $HOME/.config/systemd/user

# Create symbolic link to the service file
ln -s $METPATH/utils/iwxxm-collect-separate.service $HOME/.config/systemd/user/

# Enable and start the service
systemctl --user enable --now iwxxm-collect-separate
```

### Step 5: Configure Log Rotation

To prevent log files from consuming too much disk space, configure logrotate.

Run with **root access**:

```bash
# Create symbolic link to logrotate configuration
sudo ln -s $METPATH/utils/logrotate_iwxxm-collect-separate /etc/logrotate.d/iwxxm-collect-separate
```

## Service Management

### Check Service Status

```bash
systemctl --user status iwxxm-collect-separate
```

### View Service Logs

```bash
# View recent log entries
tail -f $METPATH/var/input/log/iwxxm-collect-separate.log

# View with journalctl
journalctl --user -u iwxxm-collect-separate -f
```

### Stop the Service

```bash
systemctl --user stop iwxxm-collect-separate
```

### Restart the Service

```bash
systemctl --user restart iwxxm-collect-separate
```

### Disable Auto-start

```bash
systemctl --user disable iwxxm-collect-separate
```

## Uninstallation

To remove the service:

```bash
# Stop and disable the service
systemctl --user stop iwxxm-collect-separate
systemctl --user disable iwxxm-collect-separate

# Remove the symbolic link
rm $HOME/.config/systemd/user/iwxxm-collect-separate.service

# Reload systemd
systemctl --user daemon-reload

# Remove logrotate configuration (requires root)
sudo rm /etc/logrotate.d/iwxxm-collect-separate

# Optionally remove the utils folder and logs
# rm -rf $METPATH/utils/
# rm -rf $METPATH/var/input/log/
```
