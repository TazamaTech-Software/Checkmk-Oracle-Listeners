# Oracle Listeners — Checkmk MKP Technical Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Requirements](#2-requirements)
   - [2.1 Checkmk Agent Requirements](#21-checkmk-agent-requirements)
   - [2.2 Checkmk Server Requirements](#22-checkmk-server-requirements)
3. [Installation & Configuration](#3-installation--configuration)
   - [3.1 Importing the MKP](#31-importing-the-mkp)
   - [3.2 Deploying the Agent Script](#32-deploying-the-agent-script)
   - [3.3 Configuring Rules in Checkmk](#33-configuring-rules-in-checkmk)
   - [3.4 Excluding Listeners from Monitoring](#34-excluding-listeners-from-monitoring)
   - [3.5 How the Bakery Works](#35-how-the-bakery-works)
4. [Monitored Metrics & Services](#4-monitored-metrics--services)
   - [4.1 Service Overview](#41-service-overview)
   - [4.2 Metric Descriptions](#42-metric-descriptions)
   - [4.3 Check States & Logic](#43-check-states--logic)
5. [Troubleshooting](#5-troubleshooting)
   - [5.1 Agent-Side Troubleshooting](#51-agent-side-troubleshooting)
   - [5.2 Server-Side Troubleshooting](#52-server-side-troubleshooting)
6. [Uninstallation](#6-uninstallation)
7. [Security Considerations](#7-security-considerations)
8. [Known Limitations & Compatibility Notes](#8-known-limitations--compatibility-notes)
9. [Appendix](#9-appendix)
   - [9.1 File Structure of the MKP](#91-file-structure-of-the-mkp)
   - [9.2 Example Agent Output](#92-example-agent-output)
   - [9.3 Glossary](#93-glossary)
   - [9.4 References & Further Reading](#94-references--further-reading)

---

## 1. Overview

**Oracle Listeners** is a Checkmk Monitoring Extension Package (MKP) that
monitors Oracle TNS listeners on database and Grid Infrastructure hosts. It
discovers and checks standard Oracle listeners, Oracle RAC SCAN listeners, and
the Oracle Grid management listener, emitting one Checkmk service per listener
instance.

| Attribute | Value |
|-----------|-------|
| Plugin type | Agent-based (Perl agent plugin + Python check plugins) |
| Agent section | `oracle_listeners` |
| Separator | Pipe (`\|`, ASCII 124) |
| Number of check plugins | 3 |
| Number of WATO rule sets | 2 (agent config + check parameters) |
| Check interval | 5 minutes (all metrics) |
| Services | Item-based — one service per discovered listener instance |
| Cluster-aware | Yes — all check plugins implement `cluster_check_function` |
| Cluster algorithm | WorstOf (reports the worst state across all cluster nodes) |

### Supported Checkmk editions

| Edition | Supported | Notes |
|---------|-----------|-------|
| Checkmk Raw (CRE) | Yes | Manual agent deployment only; no bakery |
| Checkmk Standard (CSE) | Yes | Manual agent deployment only; no bakery |
| Checkmk Cloud (CCE) | Yes | Full support including bakery |
| Checkmk Enterprise (CEE) | Yes | Full support including bakery |
| Checkmk MSP (CME) | Yes | Full support including bakery |

### Supported Checkmk versions

| Version | Status |
|---------|--------|
| 2.3.x | Supported (minimum required) |
| 2.4.x | Supported |

### Changelog

| Version | Date | Summary |
|---------|------|---------|
| 1.0.0 | 2026-05-05 | Initial release — standard listeners, RAC SCAN listeners, management listener |

---

## 2. Requirements

### 2.1 Checkmk Agent Requirements

#### Operating system

| Platform | Bakery deployment | Manual deployment |
|----------|------------------|-------------------|
| Linux (x86-64, ARM) | Yes | Yes |
| AIX | Yes | Yes |
| Windows | No | Yes |

> **NOTE:** The Agent Bakery deploys the plugin for Linux and AIX only. On
> Windows, the plugin must be placed in the agent plugins directory manually.
> All three listener types (m3000, m3010, m3020) are supported on all
> platforms where the corresponding Oracle binaries are present.

#### Software on the monitored host

| Requirement | Version / Notes |
|-------------|-----------------|
| Checkmk agent | Must match the server version (2.3.x or later) |
| Perl | 5.10 or later; no CPAN modules required — the plugin is fully self-contained |
| Oracle Database or Grid Infrastructure | Must be installed; provides `lsnrctl` |
| Oracle Grid Infrastructure (RAC) | Required for SCAN and management listener checks (m3010, m3020); provides `srvctl` |

The plugin calls Oracle binaries directly:
- `$ORACLE_HOME/bin/lsnrctl` — for standard listener status (m3000)
- `$GRID_HOME/bin/srvctl` — for SCAN and management listener status (m3010, m3020)

Both binaries must be present in their respective Oracle homes. The plugin
discovers these homes automatically (see below) and sets `ORACLE_HOME`
before each invocation.

#### Oracle home discovery

The plugin resolves Oracle homes at runtime using a combined strategy. All
sources are merged (not first-match-wins) so that every home with `lsnrctl`
receives a listener check.

**For standard listener checks (m3000) — homes with `lsnrctl`:**

1. **Running `tnslsnr` processes** — scans `ps -ef` (Unix) or Oracle TNS
   listener Windows services (`sc query` + `sc qc`) to find listeners that
   are currently running together with their Oracle home path.
2. **`/etc/oratab`** (Linux) or **`/var/opt/oracle/oratab`** (AIX/Solaris)
   — every entry whose home contains `bin/lsnrctl`.
3. **Windows registry** — `HKLM\SOFTWARE\ORACLE` and
   `HKLM\SOFTWARE\WOW6432Node\ORACLE` (all `ORACLE_HOME` values).
4. **Environment variables** — `$ORACLE_HOME` and `$GRID_HOME` if set.

**For SCAN and management listener checks (m3010, m3020) — homes with `srvctl`:**

Same source list as above, filtered to homes that contain `bin/srvctl`.

#### Listener name discovery

Within each Oracle home, the plugin discovers listener names from three
sources, applied in order with deduplication:

1. **Running processes** — `tnslsnr` process arguments identify the listener
   name and Oracle home for currently running listeners.
2. **`listener.ora`** — parsed from `$ORACLE_HOME/network/admin/listener.ora`,
   `$TNS_ADMIN/listener.ora`, or `/etc/listener.ora` (Unix fallback). Captures
   all configured listener names, including those whose process is stopped.
3. **Default name fallback** — if neither of the above yields a listener name
   for a home, the default name `LISTENER` is probed.

#### Required user permissions

The Checkmk agent on Linux runs as **root** by default, which is sufficient.
If the agent runs as a non-root user:

| Requirement | Detail |
|-------------|--------|
| Execute permission | `lsnrctl` and `srvctl` must be executable by the agent user |
| Group membership | User typically needs to belong to `oinstall` and/or `dba` |
| `listener.ora` | Must be readable by the agent user |
| TNS admin socket | `lsnrctl` communicates with the listener via a local IPC socket; the agent user must have access |

Example `sudoers` entry if the agent runs as `cmk`:

```
cmk ALL=(oracle) NOPASSWD: /u01/app/oracle/product/19c/db/bin/lsnrctl status *
cmk ALL=(grid)   NOPASSWD: /u01/app/oracle/product/19c/grid/bin/srvctl status scan_listener
cmk ALL=(grid)   NOPASSWD: /u01/app/oracle/product/19c/grid/bin/srvctl status mgmtlsnr
```

If using sudo wrappers, update the `run_cmd` subroutine in `oracle_listeners.pl`
to prepend `sudo -u <oracle-user>` to each command.

#### Network ports

None. All data is collected via local process execution (`lsnrctl`, `srvctl`).
No TCP/UDP ports are opened by the plugin.

#### Required environment variables and config files

| Resource | Purpose | Required |
|----------|---------|----------|
| `/etc/oratab` or `/var/opt/oracle/oratab` | Oracle home discovery | No — only needed if homes cannot be discovered from processes or environment |
| `$ORACLE_HOME` | Explicit Oracle home override | No — discovered automatically |
| `$GRID_HOME` | Explicit Grid home override | No — discovered automatically |
| `$TNS_ADMIN` | Alternative path for `listener.ora` | No — falls back to `$ORACLE_HOME/network/admin/` |
| `$MK_CONFDIR/oracle_listeners.cfg` | Listener exclusion list | No — plugin runs without it |

The plugin sets the following environment variables before executing Oracle
commands, ensuring English-language output regardless of the OS locale:

```
ORACLE_HOME        = <discovered home for each invocation>
SRVM_PROPERTY_DEFS = -Duser.language=en -Duser.country=US
NLS_LANG           = AMERICAN_AMERICA
```

---

### 2.2 Checkmk Server Requirements

#### Minimum version and edition

| Attribute | Value |
|-----------|-------|
| Minimum Checkmk version | **2.3.0p1** |
| Bakery support | Enterprise, Cloud, and MSP editions only |
| Check and rule functionality | All editions |

#### Python environment

The check plugins use only Python packages that ship with Checkmk 2.3+:

| Package | Source |
|---------|--------|
| `cmk.agent_based.v2` | Checkmk core |
| `cmk.rulesets.v1` | Checkmk core |
| `cmk.ccc.debug` / `cmk.utils.debug` | Checkmk core (version-dependent path) |

No pip packages or third-party libraries are required. No graphing file is
included because all oracle_listeners metrics are binary state checks that
produce no performance counter data.

#### Disk space

The oracle_listeners metrics are all binary (0/1 values) with no performance
counters. No RRD files are created on the Checkmk server.

#### Permissions on the Checkmk server

Standard Checkmk site-user permissions are sufficient. No elevated privileges
are required to install or run this MKP.

---

## 3. Installation & Configuration

### 3.1 Importing the MKP

#### Via the web interface

1. Download the latest `oracle_listeners-X.Y.Z.mkp` from the
   [Releases page](https://github.com/TazamaTechNK/Checkmk-Oracle-Listeners/releases).
2. Log in to Checkmk as an administrator.
3. Navigate to **Setup → Extension packages**.
4. Click **Upload package**, select the `.mkp` file, and click **Upload**.
5. The package appears in the list with status **Enabled**.

> **NOTE:** No site restart is required. Extension packages are loaded
> dynamically in Checkmk 2.3+.

#### Via the command line

Log in as the Checkmk site user, then:

```bash
# Copy the MKP to the site first (if needed)
scp oracle_listeners-1.0.0.mkp <checkmk-server>:/tmp/

# Install
mkp install /tmp/oracle_listeners-1.0.0.mkp

# Verify
mkp list | grep oracle_listeners
```

Expected output of `mkp list`:

```
oracle_listeners  1.0.0  Oracle Listeners Monitoring
```

#### Building the MKP locally

The repository includes a self-contained build script that requires only
Python 3 and the `local/` directory tree:

```powershell
# Windows (PowerShell, from the repository root)
python build.py --version 1.0.0

# Linux / macOS
python3 build.py --version 1.0.0
```

This produces `oracle_listeners-1.0.0.mkp` in the current directory. To
write the output to a subdirectory:

```bash
python3 build.py --version 1.0.0 --output-dir dist/
```

#### Verifying successful installation

```bash
# Confirm the agent plugin is present on the Checkmk server
ls -l ~/local/share/check_mk/agents/plugins/oracle_listeners.pl

# Check that Python files are importable
python3 -c "import cmk_addons.plugins.oracle_listeners.oracle_listeners_metrics"
```

The two rule sets appear in the Checkmk web interface under:
- **Setup → Agents → Agent rules** → search **Oracle Listeners** (agent config rule)
- **Setup → Service monitoring rules** → search **Oracle Listeners** (check parameters rule)

---

### 3.2 Deploying the Agent Script

#### What the script does

`oracle_listeners.pl` is a self-contained Perl script that:

1. Loads the exclusion list from `$MK_CONFDIR/oracle_listeners.cfg` (if present).
2. Discovers all Oracle homes that have `lsnrctl` present.
3. Scans running `tnslsnr` processes and `listener.ora` files to build a
   complete list of listeners — both running and stopped.
4. Runs `lsnrctl status` for each non-excluded listener (metric 3000).
5. For each Oracle Grid home with `srvctl`, queries SCAN listeners (metric 3010)
   and the management listener (metric 3020).
6. Emits results as a pipe-delimited Checkmk agent section.

The script has no external Perl module dependencies. Listener names and Oracle
homes are discovered entirely at runtime from processes, `listener.ora`, and
oratab — no hardcoded paths.

#### Option A — Agent Bakery (Enterprise/Cloud/MSP only, recommended)

> **NOTE:** This option requires a Checkmk edition that includes the Agent
> Bakery (CEE, CCE, or CME). It is not available in Checkmk Raw or Standard.

1. In Checkmk go to **Setup → Agents → Agent rules** and search for
   **Oracle Listeners**.
2. Create a new rule, set **enabled = true**, optionally add entries to the
   **Excluded listeners** list, and assign the rule to the host group or
   folder containing your Oracle hosts.
3. Navigate to **Setup → Agents → Windows, Linux, Solaris, AIX** and click
   **Bake agents**.
4. Deploy the baked agent package to the target hosts using your normal
   mechanism (Checkmk auto-update, Ansible, manual RPM/DEB install, etc.).

The baked agent places the plugin at:

```
# Linux
/usr/lib/check_mk_agent/plugins/oracle_listeners.pl

# AIX
/usr/check_mk/lib/plugins/oracle_listeners.pl
```

If the **Excluded listeners** list in the rule is non-empty, the bakery also
deploys a configuration file (see [Section 3.4](#34-excluding-listeners-from-monitoring)).

#### Option B — Manual deployment (all editions)

```bash
# Linux
sudo cp oracle_listeners.pl /usr/lib/check_mk_agent/plugins/
sudo chmod 755 /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
sudo chown root:root /usr/lib/check_mk_agent/plugins/oracle_listeners.pl

# AIX
cp oracle_listeners.pl /usr/check_mk/lib/plugins/
chmod 755 /usr/check_mk/lib/plugins/oracle_listeners.pl
```

```cmd
:: Windows — copy to the agent plugins directory
copy oracle_listeners.pl "C:\Program Files (x86)\checkmk\service\plugins\"
```

#### Triggering service discovery after deployment

After the script is deployed and producing output, run a service discovery on
the host:

```bash
# As site user — discover new services
cmk -I <hostname>

# Apply changes
cmk -R
```

Or via the web interface: **Setup → Hosts → <hostname> → Run service discovery**.

#### Verifying the script output

```bash
# Run as root on the monitored host (Linux)
perl /usr/lib/check_mk_agent/plugins/oracle_listeners.pl

# From the Checkmk server, inspect cached agent output
cmk --debug --cache <hostname> | grep -A 20 'oracle_listeners'

# Or dump a fresh agent run via the agent controller
cmk-agent-ctl dump | grep -A 20 'oracle_listeners'
```

Expected output (two standard listeners, one SCAN listener, management listener):

```
<<<oracle_listeners:sep(124)>>>
LISTENER:/u01/app/oracle/product/19c/db|3000|0|LSNRNAME=LISTENER|ORAHOME=/u01/app/oracle/product/19c/db|ERROR=No error|NODE=rac1|None
LISTENER2:/u01/app/oracle/product/19c/db|3000|0|LSNRNAME=LISTENER2|ORAHOME=/u01/app/oracle/product/19c/db|ERROR=No error|NODE=rac1|None
LISTENER_SCAN1:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN1|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
LISTENER_SCAN2:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN2|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
LISTENER_SCAN3:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN3|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
MGMTLSNR:/u01/app/oracle/product/19c/grid|3020|0|LSNRNAME=MGMTLSNR|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
```

---

### 3.3 Configuring Rules in Checkmk

#### Locating the rule set

**Setup → Service monitoring rules → Oracle Listeners Metrics**

(Direct path: search "Oracle Listeners" in the Setup search bar.)

Rule set name (internal identifier): `oracle_listeners_parameters`

The rule set appears under the **Databases** topic.

#### Available parameters

The rule contains one sub-section per metric. Each metric has four fields:

| Parameter | Type | Accepted values | Description |
|-----------|------|-----------------|-------------|
| `enabled` | Boolean | `true` / `false` | Whether the metric is evaluated. Disabled metrics produce no service and no alert, even if data is present in the agent output. |
| `warning` | String (numeric or `NaN`) | Any number or literal `NaN` | Threshold value for WARNING state. `NaN` disables the WARNING threshold. Validated against the regex `([-]?([0-9]+[.])?[0-9]+\|NaN)`. |
| `critical` | String (numeric or `NaN`) | Any number or literal `NaN` | Threshold value for CRITICAL state. `NaN` disables the CRITICAL threshold. |
| `type` | Read-only string | `MAX` | Direction of the threshold comparison. Fixed to MAX for all listener metrics — alert when value *exceeds* the threshold (higher is worse). |

#### Default parameter values

| Metric | enabled | type | warning | critical |
|--------|---------|------|---------|----------|
| m3000 — Oracle Listener | `true` | MAX | `0.9` | `NaN` |
| m3010 — Oracle RAC SCAN Listener | `true` | MAX | `0.9` | `NaN` |
| m3020 — Oracle Management Listener | `true` | MAX | `0.9` | `NaN` |

These defaults are compiled into the check plugin
(`check_default_parameters` in `oracle_listeners.py`) and apply when no
matching WATO rule exists for a host.

#### Threshold semantics for binary metrics

All three metrics produce only two values: `0` (listener running) or `1`
(listener not running or error). A warning threshold of `0.9` means any
value ≥ 1 triggers WARNING — effectively "alert on any problem." To escalate
directly to CRITICAL, set **critical = `0.9`** (and optionally set warning to
`NaN` to suppress the intermediate WARNING state).

#### Item-based rule conditions

Services are item-based. The item is `LSNRNAME:ORAHOME`, for example:
`LISTENER:/u01/app/oracle/product/19c/db`. Use the **Item** filter in the
rule condition to target thresholds at specific listeners or Oracle homes.

#### Example rule configurations

**Alert CRITICAL immediately when any listener is down (skip WARNING):**

```
m3000:
  enabled: true
  type: MAX        (read-only)
  warning: NaN
  critical: 0.9
```

**Disable SCAN listener monitoring for a specific host group:**

```
m3010:
  enabled: false
```

**Target a stricter threshold at a specific listener by item:**

Set the rule condition item filter to `LISTENER:/u01/app/oracle/product/19c/db`
to apply the rule only to that listener.

#### Rule assignment and precedence

Rules follow standard Checkmk precedence: rules at a more specific folder or
host label level override rules at a higher level. Use the **Analyse** button
on the rule set page to verify which rule applies to a given host and service.

---

### 3.4 Excluding Listeners from Monitoring

Some listeners may not need monitoring — for example, a listener belonging to
a decommissioned Oracle home that still appears in `listener.ora`, or a SCAN
listener managed by a different team.

#### Config file location

The plugin reads the exclusion list from:

```
$MK_CONFDIR/oracle_listeners.cfg
```

`MK_CONFDIR` is set by the Checkmk agent before invoking any plugin. Its
default value is `/etc/check_mk` on Linux/AIX and
`C:\ProgramData\checkmk\agent\config` on Windows. The plugin falls back to
these conventional paths when run manually outside the agent.

#### Config file format

```ini
# Exclude by listener name across all Oracle homes
EXCLUDE = MYLISTENER

# Exclude by listener name and specific Oracle home
EXCLUDE = LISTENER:/u01/app/oracle/product/19c/db_old

# Exclude the management listener on all homes
EXCLUDE = MGMTLSNR

# Exclude a specific SCAN listener
EXCLUDE = LISTENER_SCAN3
```

Lines starting with `#` are comments. Matching is case-insensitive for the
listener name and Oracle home path. If the file is absent or unreadable, no
exclusions apply.

#### Via the Agent Bakery (CEE/CCE/MSP)

The bakery rule for **Oracle Listeners** includes an **Excluded listeners**
field. Add one entry per listener to exclude (either `LSNRNAME` or
`LSNRNAME:ORAHOME`). The bakery generates `oracle_listeners.cfg`
automatically and deploys it alongside the plugin to `$MK_CONFDIR` on the
target host.

#### Manual file placement

Create the file at the path above and ensure it is readable by the agent user:

```bash
# Linux
cat > /etc/check_mk/oracle_listeners.cfg << 'EOF'
EXCLUDE = MYLISTENER
EXCLUDE = LISTENER:/u01/app/oracle/product/19c/db_old
EOF
chmod 644 /etc/check_mk/oracle_listeners.cfg
```

---

### 3.5 How the Bakery Works

#### What is baked

The bakery plugin (`cmk/base/cee/plugins/bakery/oracle_listeners.py`) is
called by the Agent Bakery when generating agent packages. When the plugin is
enabled via a WATO rule (`conf['enabled'] == True`), it:

1. Includes `oracle_listeners.pl` in the baked package for:
   - `OS.LINUX` — deployed to `/usr/lib/check_mk_agent/plugins/`
   - `OS.AIX` — deployed to `/usr/check_mk/lib/plugins/`
2. If the **Excluded listeners** list in the rule is non-empty, generates
   `oracle_listeners.cfg` with one `EXCLUDE = <entry>` line per listener
   and includes it in the package for both `OS.LINUX` and `OS.AIX`.

If the plugin is **disabled** (no matching rule, or rule explicitly sets
`enabled = false`), neither the Perl script nor the config file is included.
Windows is not supported by the bakery plugin; deploy manually if needed.

No systemd unit is created. No other configuration files are generated.

#### Baking workflow

**GUI:**

1. Configure the agent rule (Section 3.3).
2. Go to **Setup → Agents → Windows, Linux, Solaris, AIX**.
3. Click **Bake agents** and wait for the bake job to complete.
4. Deploy the agent package via your normal mechanism.

**CLI (as site user):**

```bash
# Bake all agents
cmk -v --bake-agents

# Bake for a specific host only
cmk -v --bake-agents <hostname>
```

#### Verifying baked content

```bash
# List baked agent packages
ls /omd/sites/<site>/var/check_mk/agents/

# Inspect a specific package (replace with actual filename)
tar -tzf /omd/sites/<site>/var/check_mk/agents/<package>.tar.gz | grep oracle
```

You should see `plugins/oracle_listeners.pl` in the archive, and
`config/oracle_listeners.cfg` if exclusions were configured.

> **WARNING:** Do not modify `oracle_listeners.pl` inside a baked package.
> Changes to the source file must be made in
> `local/share/check_mk/agents/plugins/oracle_listeners.pl` (on the
> Checkmk server), followed by a new bake and re-deployment.

---

## 4. Monitored Metrics & Services

### 4.1 Service Overview

Services are **item-based** — one service is created per discovered listener
instance per metric type. The service item is `LSNRNAME:ORAHOME`, making each
service uniquely identifiable by listener name and Oracle home.

| Service Name Template | Check Plugin | Default | Description |
|---|---|---|---|
| `Oracle Listener <LSNRNAME:ORAHOME>` | `oracle_m3000` | Enabled | Standard Oracle listener via `lsnrctl status` |
| `Oracle RAC SCAN Listener <LSNRNAME:ORAHOME>` | `oracle_m3010` | Enabled | RAC SCAN listener via `srvctl status scan_listener` |
| `Oracle Management Listener <LSNRNAME:ORAHOME>` | `oracle_m3020` | Enabled | Grid management listener via `srvctl status mgmtlsnr` |

Example service names on a two-listener RAC node:

```
Oracle Listener LISTENER:/u01/app/oracle/product/19c/db
Oracle Listener LISTENER_APP:/u01/app/oracle/product/19c/db
Oracle RAC SCAN Listener LISTENER_SCAN1:/u01/app/oracle/product/19c/grid
Oracle RAC SCAN Listener LISTENER_SCAN2:/u01/app/oracle/product/19c/grid
Oracle RAC SCAN Listener LISTENER_SCAN3:/u01/app/oracle/product/19c/grid
Oracle Management Listener MGMTLSNR:/u01/app/oracle/product/19c/grid
```

All three check plugins read from the same agent section (`oracle_listeners`)
and implement `cluster_check_function`. In a Checkmk cluster object, each
listener service aggregates data from all cluster nodes using the WorstOf
algorithm.

---

### 4.2 Metric Descriptions

#### m3000 — Oracle Listener

| Attribute | Value |
|-----------|-------|
| Check plugin | `oracle_m3000` |
| Service name | `Oracle Listener <LSNRNAME:ORAHOME>` |
| Source command | `lsnrctl status <LSNRNAME>` (with `ORACLE_HOME` set) |
| Value type | Binary integer |
| Unit | None (0 = running, 1 = not running or error) |
| Threshold type | MAX |
| Default warning | `0.9` |
| Default critical | `NaN` (disabled) |
| Performance counter | None |
| Enabled by default | Yes |

The plugin runs `lsnrctl status <name>` for each discovered listener, with
`ORACLE_HOME` set to the listener's home. A `TNS-` error code in the output
(e.g. `TNS-12541: TNS: no listener`) sets value = `1` and reports the matched
error text in `OPTION3` as `ERROR=<text>`.

Listeners are discovered from three sources in priority order (see
[Section 2.1](#21-checkmk-agent-requirements)). This means that a listener
configured in `listener.ora` but not currently running will still appear as a
service in state WARNING/CRITICAL (value = `1`), allowing detection of stopped
listeners without relying on process presence alone.

**Alert text:** `Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.`

---

#### m3010 — Oracle RAC SCAN Listener

| Attribute | Value |
|-----------|-------|
| Check plugin | `oracle_m3010` |
| Service name | `Oracle RAC SCAN Listener <LSNRNAME:ORAHOME>` |
| Source command | `srvctl status scan_listener` |
| Value type | Binary integer |
| Unit | None (0 = running, 1 = not running) |
| Threshold type | MAX |
| Default warning | `0.9` |
| Default critical | `NaN` (disabled) |
| Performance counter | None |
| Enabled by default | Yes |

`srvctl status scan_listener` queries SCAN listener status cluster-wide. One
output record is emitted per SCAN listener found (typically three in a
standard RAC cluster: `LISTENER_SCAN1`, `LISTENER_SCAN2`, `LISTENER_SCAN3`).
The node the listener is running on is reported in `OPTION4` as
`NODE=<nodename>`.

This metric is only emitted for Oracle homes where `srvctl` is present (Grid
Infrastructure homes). It is not emitted on standalone database homes.

**Alert text:** `SCAN Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.`

---

#### m3020 — Oracle Management Listener

| Attribute | Value |
|-----------|-------|
| Check plugin | `oracle_m3020` |
| Service name | `Oracle Management Listener MGMTLSNR:<ORAHOME>` |
| Source command | `srvctl status mgmtlsnr` |
| Value type | Binary integer |
| Unit | None (0 = running, 1 = not running) |
| Threshold type | MAX |
| Default warning | `0.9` |
| Default critical | `NaN` (disabled) |
| Performance counter | None |
| Enabled by default | Yes |

Checks the Oracle Grid Infrastructure management listener (`MGMTLSNR`),
introduced in Oracle 12c. The record is silently skipped when
`srvctl status mgmtlsnr` does not return recognisable output — this is
expected on pre-12c Grid homes where `mgmtlsnr` is not configured. No
UNKNOWN service is created in this case.

**Alert text:** `Management Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.`

---

### 4.3 Check States & Logic

#### State calculation

All three check plugins share a single state calculation function (`calc_state`
in `oracle_listeners_lib.py`). All listener metrics use **MAX** threshold type:

```
if value > critical  →  CRIT   (when critical ≠ NaN)
if value > warning   →  WARN   (when warning ≠ NaN)
otherwise            →  OK
```

CRITICAL is evaluated before WARNING. If both thresholds are set, the highest
severity wins.

With the default threshold of `warning = 0.9` and `critical = NaN`, a
listener value of `1` (not running) triggers WARNING. To trigger CRITICAL
instead, set `critical = 0.9` (and optionally `warning = NaN`).

#### Disabled metric behavior

If a metric is marked `enabled = false` in the active rule, the check function
returns without yielding any result. This means:
- The service still exists if it was previously discovered while enabled.
- It will always show OK regardless of the measured value.
- To fully suppress the service, disable it in the rule *before* running
  discovery, or manually remove the service.

#### No-data behavior

If the agent section contains no data row for a given item and metric, the
check function yields:

```
State.UNKNOWN — "No data received for <item>"
```

This occurs when the agent plugin stopped running, the listener was removed
from the host, or the metric was excluded via the config file after the service
was already discovered. UNKNOWN state does not write to the RRD.

#### Cluster behavior

All three check plugins implement `cluster_check_function` using the **WorstOf**
algorithm:

- Each node's individual state is calculated using the same `calc_state` logic.
- `State.worst(*node_states.values())` selects the most severe state across all
  nodes.
- For m3000, each RAC node runs its own local `lsnrctl status` — both nodes
  contribute independently to the cluster service.
- For m3010, `srvctl status scan_listener` is cluster-aware and returns
  per-SCAN-listener status. On a two-node cluster, both nodes typically return
  the same data; WorstOf handles any discrepancy.
- For m3020, same behavior as m3010.

If a listener is present on one node but absent (or excluded) on another, only
the nodes that report data contribute to the cluster result.

---

## 5. Troubleshooting

### 5.1 Agent-Side Troubleshooting

#### Running the plugin manually

```bash
# Run as root on the monitored host (Linux)
perl /usr/lib/check_mk_agent/plugins/oracle_listeners.pl

# AIX
perl /usr/check_mk/lib/plugins/oracle_listeners.pl

# With debug output from stderr
perl /usr/lib/check_mk_agent/plugins/oracle_listeners.pl 2>/tmp/lsnr_debug.log
cat /tmp/lsnr_debug.log
```

If the script emits only the section header with no data rows:

```
<<<oracle_listeners:sep(124)>>>
```

No Oracle home with `lsnrctl` was found. See "No Oracle home discovered" below.

#### Common errors and solutions

---

**No Oracle home discovered (empty section)**

```bash
# Inspect oratab
cat /etc/oratab | grep -v '^#' | grep -v '^$'

# Locate lsnrctl manually
find /u01 /app /oracle -name lsnrctl 2>/dev/null

# Test with explicit override
ORACLE_HOME=/u01/app/oracle/product/19c/db \
  perl /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
```

If the explicit override works, set `ORACLE_HOME` in the Checkmk agent
environment or add the correct entry to `/etc/oratab`:

```
MYDB:/u01/app/oracle/product/19c/db:N
```

---

**Listener is running but not appearing in output**

The listener name may be in the exclusion list. Check:

```bash
cat /etc/check_mk/oracle_listeners.cfg
```

If the listener is not excluded, verify the process is visible:

```bash
ps -ef | grep tnslsnr
```

If the process shows a non-default listener name (not `LISTENER`), confirm
that the corresponding `listener.ora` entry is present and readable:

```bash
cat $ORACLE_HOME/network/admin/listener.ora
```

---

**Listener is stopped and not appearing in output**

The plugin discovers stopped listeners from `listener.ora`. If `listener.ora`
does not exist or does not contain the listener name, a stopped listener is
invisible.

```bash
# Check if listener.ora is readable
cat $ORACLE_HOME/network/admin/listener.ora

# Check if the listener name is a recognised top-level stanza
grep -i "^[A-Za-z]" $ORACLE_HOME/network/admin/listener.ora
```

If the listener name is absent, add it to `listener.ora`. The plugin will
then discover it and report value = `1` (not running).

---

**SCAN or management listener records not appearing**

`srvctl` must be present in a Grid home:

```bash
# Check for srvctl
test -x /u01/app/oracle/product/19c/grid/bin/srvctl && echo "OK" || echo "MISSING"

# Test as agent user
sudo -u <agent-user> /u01/app/oracle/product/19c/grid/bin/srvctl status scan_listener
sudo -u <agent-user> /u01/app/oracle/product/19c/grid/bin/srvctl status mgmtlsnr
```

m3020 (management listener) is silently skipped on pre-12c Grid homes where
`mgmtlsnr` is not configured — this is expected behavior, not an error.

---

**`lsnrctl command failed` in ERROR field**

```bash
# Check binary exists and is executable
ls -l $ORACLE_HOME/bin/lsnrctl

# Test as agent user
sudo -u <agent-user> $ORACLE_HOME/bin/lsnrctl status LISTENER
```

If `lsnrctl` hangs, the listener process may be stuck. Check the TNS
admin socket directory:

```bash
ls -la /tmp/.oracle/
```

---

**Plugin not running at all (section missing from agent output)**

```bash
# Check file exists and is executable
ls -l /usr/lib/check_mk_agent/plugins/oracle_listeners.pl

# Check for syntax errors
perl -c /usr/lib/check_mk_agent/plugins/oracle_listeners.pl

# Run agent manually to confirm section appears
check_mk_agent | grep oracle_listeners
```

---

**Plugin times out**

`lsnrctl status` may hang if the listener is in a partial failure state. The
Checkmk agent has a global plugin timeout (default: 60 seconds). Run manually
with a timeout to reproduce:

```bash
timeout 30 perl /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
```

If the command hangs at a specific listener, that listener's process is likely
unresponsive. Investigate at the Oracle level; exclude the listener temporarily
while investigating (see [Section 3.4](#34-excluding-listeners-from-monitoring)).

---

#### Agent log file locations

| Platform | Log location |
|----------|-------------|
| Linux (systemd) | `journalctl -u check-mk-agent.socket` |
| Linux (xinetd) | `/var/log/syslog` or `/var/log/messages` |
| AIX | `/var/log/check_mk/check_mk_agent.log` |
| Windows | Event Viewer → Applications and Services Logs → Checkmk |

---

### 5.2 Server-Side Troubleshooting

#### Inspecting service discovery output

```bash
# As site user — list discovered services for a host
cmk -v --checks=oracle_m3000,oracle_m3010,oracle_m3020 <hostname>

# Re-run discovery
cmk -vv -I <hostname>
```

#### Debugging check execution

```bash
# Verbose check run for all oracle_listeners plugins
cmk -v --debug <hostname> 2>&1 | grep -A 5 oracle

# Debug a single check plugin with full output
cmk -v --debug --checks=oracle_m3000 <hostname>
```

The `--debug` flag activates the `if debug.enabled():` branches in
`oracle_listeners_lib.py`, which print the parsed section dictionary and
intermediate state calculations to stdout.

#### Inspecting raw agent output

```bash
# From cached output (updated on last agent contact)
cat /omd/sites/<site>/tmp/check_mk/cache/<hostname> | grep -A 30 oracle_listeners

# From a live agent run
cmk --debug --cache <hostname> | grep -A 30 oracle_listeners
```

#### Common server-side errors and solutions

---

**Services go UNKNOWN — "No data received for `<item>`"**

1. Verify the agent plugin is running and producing output (Section 5.1).
2. Verify the metric is still enabled in the active WATO rule.
3. Check whether the listener item matches exactly — the item is case-sensitive
   and includes the Oracle home path.
4. If the MKP was recently updated or the plugin redeployed, run a full
   re-discovery:

```bash
cmk -I <hostname>
cmk -R
```

---

**Services not discovered after MKP import**

```bash
cmk -II <hostname>   # force full re-discovery
cmk -R
```

---

**Too many services discovered (unwanted listeners appearing)**

Add the unwanted listeners to the exclusion config (see
[Section 3.4](#34-excluding-listeners-from-monitoring)), then run:

```bash
cmk -I <hostname>   # re-discovery will remove excluded services
cmk -R
```

---

**Thresholds not applied — service always OK despite listener being down**

1. Check the active rule via the GUI Analyse button.
2. Confirm the metric's `enabled` field is `true` in the active rule.
3. Confirm `warning` and `critical` are numeric values (not `NaN`) for the
   state you expect.
4. Run the check with debug to see the raw value and threshold evaluation:

```bash
cmk -v --debug --checks=oracle_m3000 <hostname> 2>&1 | grep -i "m3000\|state\|warn\|crit"
```

---

**Bakery not including the agent script**

1. Confirm an agent rule for **Oracle Listeners** exists and matches the host.
2. Re-bake: `cmk -v --bake-agents <hostname>`.
3. Inspect the baked package:

```bash
ls /omd/sites/<site>/var/check_mk/agents/
tar -tzf /omd/sites/<site>/var/check_mk/agents/<package>.tar.gz | grep oracle
```

If the script is absent, the agent rule may not be matching (check folder
assignment and host labels).

---

#### Server log locations

| Log | Location | Relevant for |
|-----|----------|-------------|
| Microcore (CEE) | `/omd/sites/<site>/var/log/cmc.log` | Check scheduling, staleness |
| Nagios core (RAW) | `/omd/sites/<site>/var/log/nagios/nagios.log` | Check scheduling |
| GUI/REST errors | `/omd/sites/<site>/var/log/web.log` | MKP install errors |
| Agent output cache | `/omd/sites/<site>/tmp/check_mk/cache/<hostname>` | Raw agent data |

---

## 6. Uninstallation

### Remove the MKP from the Checkmk server

**Via the web interface:**

1. Navigate to **Setup → Extension packages**.
2. Find `oracle_listeners` and click **Delete**.

**Via the command line:**

```bash
mkp remove oracle_listeners
```

> **NOTE:** Removing the MKP does not automatically delete services that were
> already discovered. Existing services will go UNKNOWN on the next check cycle
> because the check plugins are no longer present.

### Remove stale services

After removing the MKP, remove the Oracle Listener services from all affected hosts:

```bash
# For each affected host
cmk -I <hostname>   # re-discovery removes services with no matching plugin
cmk -R
```

Or remove services manually via **Monitor → <host> → Services → Remove services**.

### Remove the agent plugin from monitored hosts

**Manual removal:**

```bash
# Linux
sudo rm /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
sudo rm -f /etc/check_mk/oracle_listeners.cfg

# AIX
rm /usr/check_mk/lib/plugins/oracle_listeners.pl
rm -f /etc/check_mk/oracle_listeners.cfg
```

**Via bakery:** Disable the Oracle Listeners agent rule, re-bake, and redeploy
the agent package. The Perl script and config file will be absent from the new
package.

### Impact on monitoring data

All oracle_listeners metrics are binary and produce no RRD performance data
files. Removing the services leaves no orphaned RRD data on the server.

---

## 7. Security Considerations

### Data accessed and transmitted

The agent plugin accesses only Oracle listener state information via local
process execution. It does **not** connect to any database, does not read
Oracle data files, and does not use any Oracle credentials.

Data transmitted to the Checkmk server in the `oracle_listeners` section:

- Listener names (e.g. `LISTENER`, `LISTENER_SCAN1`)
- Oracle home paths (e.g. `/u01/app/oracle/product/19c/db`)
- Listener running state (binary 0/1)
- TNS error message text (when a listener fails to respond)
- Hostname of the node running the listener

None of this data is confidential by Oracle security classification, but it
does reveal listener topology and current fault state.

### Principle of least privilege

If the Checkmk agent cannot run as `root`, restrict access as narrowly as
possible:

```bash
# /etc/sudoers.d/checkmk-oracle
Defaults:cmk !requiretty
cmk ALL=(oracle) NOPASSWD: /u01/app/oracle/product/19c/db/bin/lsnrctl status *
cmk ALL=(grid)   NOPASSWD: /u01/app/oracle/product/19c/grid/bin/srvctl status scan_listener
cmk ALL=(grid)   NOPASSWD: /u01/app/oracle/product/19c/grid/bin/srvctl status mgmtlsnr
```

### Credentials

This plugin stores **no credentials**. No database passwords, no OS user
passwords, no API tokens. `lsnrctl` and `srvctl` use the local Oracle
environment and OS-level IPC only.

### Network exposure

The plugin runs locally on the agent host. The only network connection involved
is the standard Checkmk agent transport (TCP 6556 or agent controller TLS
tunnel) used to deliver the section output to the server.

### Output sanitisation

The Perl script sanitises all values before including them in the
pipe-delimited output:
- Literal pipe characters (`|`) in Oracle output are replaced with `?` to
  prevent field splitting.
- Output strings are truncated to 512 characters with a ` ...` suffix to
  prevent unbounded agent output.

---

## 8. Known Limitations & Compatibility Notes

| Limitation | Detail |
|------------|--------|
| Windows not supported by bakery | The bakery plugin targets `OS.LINUX` and `OS.AIX` only. Windows deployment is manual. |
| No async execution | The plugin runs synchronously. If `lsnrctl status` hangs (e.g. stuck listener), the agent check cycle is delayed for that host. |
| `listener.ora` parsing limited to top-level stanzas | The plugin does not evaluate Oracle iFile directives. Listener definitions included via `IFILE=` will not be discovered. |
| English-only output | The plugin forces English locale via `NLS_LANG=AMERICAN_AMERICA`. If Oracle produces output in a different language, the pattern matching in metric state detection may not work correctly. |
| Debug API path change | The plugin imports `cmk.ccc.debug` (2.4.0+) with a fallback to `cmk.utils.debug` (2.3.x). If Checkmk changes this path again in a future release, the import will fail. |
| m3020 silently skipped on pre-12c | `srvctl status mgmtlsnr` does not exist in Oracle Grid before 12c. The plugin skips this metric without error when the command produces no recognisable output. |
| Multiple Grid homes | If a host has more than one Grid home with `srvctl`, SCAN and management listener checks are run for each. This is typically an unusual configuration. |

### Upgrade notes

When upgrading from one plugin version to another:

1. Install the new MKP (it replaces the old one).
2. Re-bake and redeploy agents if using the bakery.
3. Run service re-discovery if new metrics were added or removed.
4. Review WATO rules — new default parameters may differ from previous versions.

---

## 9. Appendix

### 9.1 File Structure of the MKP

#### Repository layout

```
Checkmk-Oracle-Listeners/
├── .mkp-builder.ini                           Package metadata and build configuration
├── build.py                                   MKP build script (pure Python, no dependencies)
├── DOCUMENTATION.md                           This document
├── README.md                                  Quick-start configuration guide
└── local/                                     MKP payload (mirrors Checkmk site/local/)
    ├── lib/python3/
    │   ├── cmk/base/cee/plugins/bakery/
    │   │   └── oracle_listeners.py            Bakery plugin (CEE/CCE/MSP only)
    │   └── cmk_addons/plugins/oracle_listeners/
    │       ├── agent_based/
    │       │   ├── oracle_listeners.py        Check plugin registrations (3 plugins)
    │       │   └── oracle_listeners_lib.py    Parsing, state calculation, cluster logic
    │       ├── rulesets/
    │       │   ├── ruleset_oracle_listeners.py      WATO rule set registrations
    │       │   └── ruleset_oracle_listeners_lib.py  Rule form specification
    │       └── oracle_listeners_metrics.py    Central metric definitions (METRIC_DEF)
    └── share/check_mk/agents/plugins/
        └── oracle_listeners.pl                Agent plugin (Perl, Linux + AIX + Windows)
```

#### MKP archive layout

The `.mkp` file is a gzip-compressed tar archive. The outer archive contains
metadata files and one inner tar per file section. Checkmk's `mkp` tool
handles unpacking automatically.

```
oracle_listeners-1.0.0.mkp  (tar.gz)
├── info                                       Package metadata (Python literal dict)
├── info.json                                  Package metadata (JSON)
├── agents.tar
│   └── plugins/
│       └── oracle_listeners.pl
└── cmk_addons_plugins.tar
    └── oracle_listeners/
        ├── agent_based/
        │   ├── oracle_listeners.py
        │   └── oracle_listeners_lib.py
        ├── oracle_listeners_metrics.py
        └── rulesets/
            ├── ruleset_oracle_listeners.py
            └── ruleset_oracle_listeners_lib.py
```

> **NOTE:** The bakery plugin (`cmk/base/cee/plugins/bakery/oracle_listeners.py`)
> is in the `lib` section and is installed under `local/lib/python3/cmk/base/`.
> It is only loaded on Enterprise/Cloud/MSP editions that have the Agent Bakery.

---

### 9.2 Example Agent Output

#### Healthy host — two standard listeners, three SCAN listeners, management listener

```
<<<oracle_listeners:sep(124)>>>
LISTENER:/u01/app/oracle/product/19c/db|3000|0|LSNRNAME=LISTENER|ORAHOME=/u01/app/oracle/product/19c/db|ERROR=No error|NODE=rac1|None
LISTENER_APP:/u01/app/oracle/product/19c/db|3000|0|LSNRNAME=LISTENER_APP|ORAHOME=/u01/app/oracle/product/19c/db|ERROR=No error|NODE=rac1|None
LISTENER_SCAN1:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN1|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
LISTENER_SCAN2:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN2|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
LISTENER_SCAN3:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN3|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
MGMTLSNR:/u01/app/oracle/product/19c/grid|3020|0|LSNRNAME=MGMTLSNR|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
```

#### Degraded host — one listener down, one SCAN listener not running

```
<<<oracle_listeners:sep(124)>>>
LISTENER:/u01/app/oracle/product/19c/db|3000|0|LSNRNAME=LISTENER|ORAHOME=/u01/app/oracle/product/19c/db|ERROR=No error|NODE=rac1|None
LISTENER_APP:/u01/app/oracle/product/19c/db|3000|1|LSNRNAME=LISTENER_APP|ORAHOME=/u01/app/oracle/product/19c/db|ERROR=TNS-12541: TNS:no listener|NODE=rac1|None
LISTENER_SCAN1:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN1|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
LISTENER_SCAN2:/u01/app/oracle/product/19c/grid|3010|1|LSNRNAME=LISTENER_SCAN2|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=SCAN listener not running|NODE=|None
LISTENER_SCAN3:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN3|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
MGMTLSNR:/u01/app/oracle/product/19c/grid|3020|0|LSNRNAME=MGMTLSNR|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=rac1|None
```

#### No Oracle home found (plugin ran but no listeners discovered)

```
<<<oracle_listeners:sep(124)>>>
```

#### Field format reference

```
OBJECT | MetricNumber | Value | Option1 | Option2 | Option3 | Option4 | Option5
```

| Field | Content |
|-------|---------|
| OBJECT | `LSNRNAME:ORAHOME` — uniquely identifies the listener instance |
| MetricNumber | Raw metric number: `3000`, `3010`, or `3020` |
| Value | Binary: `0` = running / healthy, `1` = not running or error |
| Option1 | `LSNRNAME=<name>` — listener name |
| Option2 | `ORAHOME=<path>` — Oracle home directory |
| Option3 | `ERROR=<text>` — TNS error text, or `No error` |
| Option4 | `NODE=<hostname>` — short hostname of the reporting node |
| Option5 | Always `None` (reserved) |

---

### 9.3 Glossary

| Term | Definition |
|------|------------|
| **Grid Home** | The Oracle installation directory for Grid Infrastructure (CRS, ASM, SCAN listeners, network services) |
| **lsnrctl** | Oracle CLI tool for controlling and querying TNS listeners; located in `$ORACLE_HOME/bin/` |
| **listener.ora** | Oracle network configuration file that defines listener names, ports, and SID lists; typically in `$ORACLE_HOME/network/admin/` |
| **MKP** | Monitoring Extension Package — Checkmk's format for distributing plugins as a single installable archive (gzip-compressed tar) |
| **MK_CONFDIR** | Environment variable set by the Checkmk agent before invoking plugins; points to the agent configuration directory (`/etc/check_mk` on Linux) |
| **NaN** | "Not a Number" — used in threshold fields to indicate that a threshold level is disabled |
| **oratab** | A text file listing Oracle database and Grid instances with their home directories; typically `/etc/oratab` |
| **RAC** | Real Application Clusters — Oracle's multi-node database clustering technology |
| **SCAN** | Single Client Access Name — a cluster-level DNS name and associated listeners that provide a single connection point for Oracle RAC clients |
| **srvctl** | Oracle CLI tool for managing cluster resources including SCAN listeners and the management listener; located in `$ORACLE_HOME/bin/` |
| **TNS** | Transparent Network Substrate — Oracle's network protocol layer; TNS errors (e.g. `TNS-12541`) indicate listener communication failures |
| **TNS_ADMIN** | Environment variable that overrides the default location of Oracle network configuration files (`listener.ora`, `tnsnames.ora`) |
| **tnslsnr** | The Oracle listener process binary; its presence in the process table indicates a running listener |
| **WorstOf** | Checkmk cluster algorithm that reports the most severe state across all nodes |
| **WATO** | Web Administration Tool — Checkmk's configuration system; accessed via the **Setup** menu |

---

### 9.4 References & Further Reading

| Resource | URL |
|----------|-----|
| MKP source repository | https://github.com/TazamaTechNK/Checkmk-Oracle-Listeners |
| Checkmk MKP documentation | https://docs.checkmk.com/latest/en/mkps.html |
| Checkmk Agent Bakery API | https://docs.checkmk.com/latest/en/bakery_api.html |
| Checkmk agent-based check API v2 | https://docs.checkmk.com/latest/en/devel_check_plugins.html |
| Checkmk Extension Packages (Exchange) | https://exchange.checkmk.com |
| Oracle lsnrctl reference | https://docs.oracle.com/en/database/oracle/oracle-database/19/netrf/lsnrctl.html |
| Oracle srvctl reference | https://docs.oracle.com/en/database/oracle/oracle-database/19/racad/server-control-utility-reference.html |
| Oracle listener.ora reference | https://docs.oracle.com/en/database/oracle/oracle-database/19/netrf/listener-ora-file-reference.html |
| Oracle SCAN listener documentation | https://docs.oracle.com/en/database/oracle/oracle-database/19/rilin/about-scan-listeners.html |
