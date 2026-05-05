# Oracle Listeners — Checkmk Extension Package (MKP)

Checkmk extension for monitoring Oracle listeners. Collects health and status
data from every monitored host via the Checkmk agent and evaluates the results
on the Checkmk server.

---

## Table of Contents

1. [Requirements — Checkmk Agent Host](#1-requirements--checkmk-agent-host)
2. [Requirements — Checkmk Server](#2-requirements--checkmk-server)
3. [Oracle Listeners](#3-oracle-listeners)
   - [3.1 Deploy the Agent Plugin](#31-deploy-the-agent-plugin)
   - [3.2 Excluding Listeners from Monitoring](#32-excluding-listeners-from-monitoring)
   - [3.3 Adjusting Thresholds via Rules](#33-adjusting-thresholds-via-rules)
   - [3.4 How the Bakery Works](#34-how-the-bakery-works)
   - [3.5 Metric Reference](#35-metric-reference)
4. [Troubleshooting](#4-troubleshooting)

---

## 1. Requirements — Checkmk Agent Host

### Operating system

| Platform | `oracle_listeners.pl` |
|----------|-----------------------|
| Linux (x86-64, ARM) | Yes |
| AIX | Yes |
| Windows | Yes (manual deployment only) |

### Software

| Requirement | Notes |
|-------------|-------|
| Checkmk agent | Version matching the server (2.3.x or later) |
| Perl | 5.10 or later; standard installation, no extra modules needed |
| Oracle Database or Grid Infrastructure | Provides `lsnrctl` and optionally `srvctl` |

### Firewall / connectivity

No additional network ports are required. The plugin runs locally on the agent
host and its output is collected by the standard Checkmk agent mechanism.

---

## 2. Requirements — Checkmk Server

| Requirement | Value |
|-------------|-------|
| Checkmk version | **2.3.0p1 or later** |
| Edition for agent baking | **CEE / CCE / MSP** (Enterprise editions) |
| Edition for manual deployment | **All editions** (RAW included) |

The check plugins, rulesets, and graphing definitions work on all editions.
The **bakery** (automatic agent deployment) requires an Enterprise edition with
the Agent Bakery feature enabled.

---

## 3. Oracle Listeners

### 3.1 Deploy the Agent Plugin

#### Oracle environment

The plugin discovers Oracle homes and listener names automatically using the
following strategy (all sources are combined):

1. **Running processes** — scans `tnslsnr` processes (Unix: `ps -ef`; Windows:
   Oracle TNS listener services via `sc query` + `sc qc`) to find listeners
   that are currently running, together with their Oracle home path.
2. **`listener.ora`** — reads `$ORACLE_HOME/network/admin/listener.ora` for
   each discovered Oracle home to find all *configured* listener names,
   including listeners that are currently stopped.
3. **oratab / registry fallback** — if no listeners are found via the above,
   probes the default listener name (`LISTENER`) for each Oracle home found in
   `/etc/oratab`, `/var/opt/oracle/oratab`, or (Windows) the registry under
   `HKLM\SOFTWARE\ORACLE`.

SCAN and management listeners are discovered separately using
`srvctl status scan_listener` and `srvctl status mgmtlsnr` on Grid homes that
have `srvctl` present.

The plugin requires read-execute access to:
- `$ORACLE_HOME/bin/lsnrctl` — for standard listener status (metric 3000)
- `$ORACLE_HOME/bin/srvctl` — for SCAN and management listener status
  (metrics 3010, 3020; Grid homes only)

The Checkmk agent typically runs as `root` on Linux. If it runs as a different
user, that user must be able to execute `lsnrctl` and read the TNS configuration.

#### Option A — Agent Bakery (CEE/CCE/MSP only, recommended)

1. Go to **Setup → Agent rules → Agent plugins** (or search for
   *Oracle Listeners*).
2. Create a rule that matches your Oracle hosts, set **enabled = true**, and
   optionally add listener names to the **Excluded listeners** list
   (see [Section 3.2](#32-excluding-listeners-from-monitoring)).
3. Go to **Setup → Agents → Windows, Linux, Solaris, AIX** and click
   **Bake agents**.
4. Deploy the newly baked agent to the target hosts via your normal mechanism.

The baked agent places the plugin at:

```
/usr/lib/check_mk_agent/plugins/oracle_listeners.pl   (Linux)
/usr/check_mk/lib/plugins/oracle_listeners.pl         (AIX)
```

If the exclusion list is non-empty, the bakery also deploys a configuration
file alongside the plugin (see [Section 3.2](#32-excluding-listeners-from-monitoring)).

#### Option B — Manual deployment (all editions)

```bash
# Linux
cp oracle_listeners.pl /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
chmod 755 /usr/lib/check_mk_agent/plugins/oracle_listeners.pl

# AIX
cp oracle_listeners.pl /usr/check_mk/lib/plugins/oracle_listeners.pl
chmod 755 /usr/check_mk/lib/plugins/oracle_listeners.pl

# Windows — copy to the agent plugins directory
copy oracle_listeners.pl "C:\Program Files (x86)\checkmk\service\plugins\"
```

#### Verify the plugin runs

```bash
cmk-agent-ctl dump | grep -A 20 'oracle_listeners'
```

Expected output (two listeners running, one SCAN listener):

```
<<<oracle_listeners:sep(124)>>>
LISTENER:/u01/app/oracle/product/19c/db|3000|0|LSNRNAME=LISTENER|ORAHOME=/u01/app/oracle/product/19c/db|ERROR=No error|NODE=host1|None
LISTENER_SCAN1:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN1|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=host1|None
MGMTLSNR:/u01/app/oracle/product/19c/grid|3020|0|LSNRNAME=MGMTLSNR|ORAHOME=/u01/app/oracle/product/19c/grid|ERROR=No error|NODE=host1|None
```

---

### 3.2 Excluding Listeners from Monitoring

Some listeners may not need monitoring — for example, a listener belonging to
a decommissioned home that still appears in `listener.ora`, or a SCAN listener
managed by a different team.

Exclusions are configured through a plain-text configuration file read by the
plugin at runtime.

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

Lines starting with `#` are comments. Matching is case-insensitive. If the
file is absent or unreadable, no exclusions apply and the plugin behaves as if
the file does not exist.

#### Via the Agent Bakery (CEE/CCE/MSP)

The bakery rule for *Oracle Listeners* includes an **Excluded listeners** field.
Add one entry per listener to exclude (either `LSNRNAME` or `LSNRNAME:ORAHOME`).
The bakery generates `oracle_listeners.cfg` automatically and deploys it
alongside the plugin.

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

### 3.3 Adjusting Thresholds via Rules

**Setup → Service monitoring rules → Oracle Listeners Metrics**

Each metric has three independently configurable parameters:

| Parameter | Description |
|-----------|-------------|
| **Enabled** | Toggle the metric on or off. Disabled metrics produce no service and no alert. |
| **Warning** | Threshold value that triggers a WARNING state. Accepts a number or `NaN` (disabled). |
| **Critical** | Threshold value that triggers a CRITICAL state. Accepts a number or `NaN` (disabled). |
| **Threshold type** | Read-only: `MAX` = alert when value *exceeds* the threshold. |

Default thresholds:

| Metric | Type | Warning | Critical | Enabled |
|--------|------|---------|----------|---------|
| m3000 — Oracle Listener | MAX | `0.9` | `NaN` | Yes |
| m3010 — Oracle RAC SCAN Listener | MAX | `0.9` | `NaN` | Yes |
| m3020 — Oracle Management Listener | MAX | `0.9` | `NaN` | Yes |

All listener metrics are binary: `0` = listener running, `1` = not running or
error. A warning threshold of `0.9` means any non-running listener triggers
WARNING. Setting critical to `0.9` upgrades the alert to CRITICAL.

Services are **item-based** — one Checkmk service is created per discovered
listener (e.g. `Oracle Listener LISTENER:/u01/app/oracle/product/19c/db`).
Use the item filter in the rule condition to target specific listeners.

---

### 3.4 How the Bakery Works

- If **enabled**, the bakery includes `oracle_listeners.pl` in the baked agent
  package for **Linux** and **AIX** targets.
- If the **Excluded listeners** list is non-empty, the bakery also generates
  `oracle_listeners.cfg` containing one `EXCLUDE = <entry>` line per listener
  and deploys it to `$MK_CONFDIR` on the target host.
- If **disabled**, neither the script nor the config file is included.
- **Windows** is not supported by the bakery plugin; deploy manually if needed.

---

### 3.5 Metric Reference

All metrics are emitted in the agent section `<<<oracle_listeners:sep(124)>>>`
using a pipe (`|`) separator. Output line format:

```
OBJECT | MetricNumber | Value | Option1 | Option2 | Option3 | Option4 | Option5
```

Where `OBJECT` is `LSNRNAME:ORAHOME` for all three metric types.

Check interval: **5 minutes**.

---

#### m3000 — Oracle Listener

| | |
|-|-|
| Source | `lsnrctl status <LSNRNAME>` |
| Value | Binary — `0` = running, `1` = not running or error |
| Threshold type | MAX |
| Default warning | `0.9` — triggers on any error (value ≥ 1) |
| Default critical | `NaN` — disabled |
| Enabled by default | Yes |
| Service name | `Oracle Listener <LSNRNAME:ORAHOME>` |

Runs `lsnrctl status` for each discovered listener. A `TNS-` error code in the
output sets value = `1` and reports the error text in `OPTION3=ERROR=<text>`.

Listeners are discovered from three sources in priority order: running
`tnslsnr` processes, `listener.ora` (catches stopped listeners), and the
default name `LISTENER` as a fallback.

**Alert message:** `Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.`

---

#### m3010 — Oracle RAC SCAN Listener

| | |
|-|-|
| Source | `srvctl status scan_listener` |
| Value | Binary — `0` = running, `1` = not running |
| Threshold type | MAX |
| Default warning | `0.9` |
| Default critical | `NaN` |
| Enabled by default | Yes |
| Service name | `Oracle RAC SCAN Listener <LSNRNAME:ORAHOME>` |

Queries `srvctl` cluster-wide for each SCAN listener. One output record is
emitted per SCAN listener found. The node the listener is running on is
reported in `OPTION4=NODE=<nodename>`.

Only emitted for Oracle homes where `srvctl` is present (Grid Infrastructure
homes). Not emitted on standalone database homes.

**Alert message:** `RAC SCAN Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.`

---

#### m3020 — Oracle Management Listener

| | |
|-|-|
| Source | `srvctl status mgmtlsnr` |
| Value | Binary — `0` = running, `1` = not running |
| Threshold type | MAX |
| Default warning | `0.9` |
| Default critical | `NaN` |
| Enabled by default | Yes |
| Service name | `Oracle Management Listener MGMTLSNR:<ORAHOME>` |

Checks the Grid Infrastructure management listener (Oracle 12c and later).
Only emitted when `srvctl status mgmtlsnr` produces recognisable output — the
record is silently skipped on pre-12c Grid homes where `mgmtlsnr` is not
configured.

**Alert message:** `Management Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.`

---

## 4. Troubleshooting

### Agent-side issues

#### `oracle_listeners` section missing entirely

```bash
ls -l /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
perl -c /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
sudo perl /usr/lib/check_mk_agent/plugins/oracle_listeners.pl
```

#### No listener records in the output (section header only)

The plugin found no Oracle homes with `lsnrctl`. Check that oratab is populated
and that `lsnrctl` exists in the discovered Oracle homes:

```bash
cat /etc/oratab
test -x /u01/app/oracle/product/19c/db/bin/lsnrctl && echo "OK" || echo "MISSING"
```

You can also set `ORACLE_HOME` in the agent environment as a fallback:

```bash
ORACLE_HOME=/u01/app/oracle/product/19c/db
export ORACLE_HOME
```

#### A known listener is not appearing in the output

The listener may have been excluded. Check the config file:

```bash
cat /etc/check_mk/oracle_listeners.cfg
```

If the listener is running, verify the process is visible:

```bash
ps -ef | grep tnslsnr
```

If the listener is stopped and not in `listener.ora`, it will not be discovered.
Add it to the appropriate `listener.ora` so the plugin can detect it as
configured-but-stopped (value = `1`).

#### SCAN or management listener records not appearing

`srvctl` must be present in the Grid home:

```bash
test -x /u01/app/oracle/product/19c/grid/bin/srvctl && echo "OK" || echo "MISSING"
sudo -u <agent-user> /u01/app/oracle/product/19c/grid/bin/srvctl status scan_listener
sudo -u <agent-user> /u01/app/oracle/product/19c/grid/bin/srvctl status mgmtlsnr
```

m3020 (management listener) is silently skipped on pre-12c Grid homes where
`mgmtlsnr` is not configured — this is expected behavior, not an error.

---

### Server-side issues

#### Service shows UNKNOWN — "No data received for `<item>`"

- Verify the agent plugin is running and producing output (see agent-side steps).
- Verify the metric is enabled in the active ruleset.
- Run a full re-discovery if the plugin was recently deployed or updated:

```bash
cmk -II <hostname>
cmk -R
```

Or via the web interface: **Setup → Hosts → <hostname> → Run service discovery**.

#### Services not discovered after MKP import

```bash
cmk -II <hostname>
cmk -R
```

#### Thresholds not applied

Rules are evaluated in Checkmk's standard precedence order (most specific
folder first). Use the **Analyse** button on the rule set page to verify which
rule is effective for a given host and service.

Confirm that the metric is marked **enabled** in the active rule. A disabled
metric always evaluates to OK regardless of the measured value.

#### Performance graphs missing

The oracle_listeners metrics are all binary state checks and produce no
performance graphs. Verify that the service is in OK or WARN state — UNKNOWN
state suppresses metric storage.
