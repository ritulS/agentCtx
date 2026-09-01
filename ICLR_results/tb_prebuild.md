# Terminal-Bench 1.0 Full Prebuild on Albus

## Outcome

On 2026-08-30 CDT, all 80 tasks from `terminal-bench-core@0.1.1` were
successfully prebuilt:

```text
prebuilt OK (80)
failed (0): none
```

The final record is in `logs/tb1_harbor_prebuild.log` at 19:57:44 CDT.

The remaining 38 tasks were not built with rootful Podman. They were built
with rootless Podman after replacing its single-UID fallback with a normal
subordinate UID/GID mapping. Before this change, only the 42-task
`P-80-rootless` subset could be built without suppressing ownership errors.
The other tasks failed when `apt`, `dpkg`, or package scripts attempted valid
`chown` operations that a single-UID namespace could not represent.

## Host-specific setup

The Podman executable was borrowed from another local installation:

```bash
export PATH="/home/rs67788/.local/bin:/usr/bin:$PATH"
export TB_PODMAN=/home/rs67788/.local/bin/podman
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
```

The experiment launchers had already exited. The remaining Podman API service
was verified and stopped before changing the mapping:

```bash
cd /home/ak58925/agentCtx

pid=$(cat logs/podman_service.pid)
ps -o pid,ppid,pgid,sid,stat,etime,cmd -p "$pid"
kill -TERM "$pid"

export PATH="/home/rs67788/.local/bin:$PATH"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export TB_PODMAN=/home/rs67788/.local/bin/podman

"$TB_PODMAN" system migrate
```

The actual account name is the domain-qualified
`ak58925@austin.utexas.edu`, not `ak58925`. Existing allocations occupied
`100000:262144`; the next non-overlapping 65,536-ID range began at 362144.
Because the following changes require host-administrator privileges, ask
`lab-admin` to back up the files and add the entries with these exact commands:

```bash
sudo cp -a /etc/subuid /etc/subuid.pre-ak58925
sudo cp -a /etc/subgid /etc/subgid.pre-ak58925

echo 'ak58925@austin.utexas.edu:362144:65536' \
  | sudo tee -a /etc/subuid
echo 'ak58925@austin.utexas.edu:362144:65536' \
  | sudo tee -a /etc/subgid

sudo grep -F 'ak58925@austin.utexas.edu:' /etc/subuid /etc/subgid
```

Ubuntu 22.04 did not have `newuidmap` or `newgidmap`. The standard `uidmap`
package was therefore also requested from `lab-admin`, using:

```bash
sudo apt-get install uidmap

command -v newuidmap
command -v newgidmap
ls -l /usr/bin/newuidmap /usr/bin/newgidmap
```

The `needrestart` dialogs reported a pending kernel upgrade and daemons using
outdated libraries. No reboot was performed, and the bulk service-restart
dialog was cancelled. Neither action was required for `uidmap`.

After logging back in as `ak58925@austin.utexas.edu`, Podman was migrated and
the mappings were verified:

```bash
export PATH="/home/rs67788/.local/bin:/usr/bin:$PATH"
export TB_PODMAN=/home/rs67788/.local/bin/podman
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

"$TB_PODMAN" system migrate
"$TB_PODMAN" unshare cat /proc/self/uid_map
"$TB_PODMAN" unshare cat /proc/self/gid_map
```

Observed mappings:

```text
         0 1741623211          1
         1     362144      65536
         0 1007000513          1
         1     362144      65536
```

## Prebuild commands

`write-compressor`, which had previously failed on ownership operations, was
used as the smoke test:

```bash
cd /home/ak58925/agentCtx

export PATH="/home/rs67788/.local/bin:/usr/bin:$PATH"
export TB_PODMAN=/home/rs67788/.local/bin/podman
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

bash scripts/tb_harbor_prebuild_images.sh write-compressor
```

It completed without the ownership-suppressing compatibility mode:

```text
rootless mode: apt-only (ownership semantics preserved)
[write-compressor/main] OK
prebuilt OK (1): write-compressor
failed (0): none
```

The resumable full prebuild was then launched detached. Existing successful
images were reused, and missing images were built sequentially:

```bash
cd /home/ak58925/agentCtx

nohup setsid bash scripts/tb_harbor_prebuild_images.sh \
  > logs/tb1_harbor_prebuild_driver.log 2>&1 < /dev/null &

echo $! > logs/tb1_harbor_prebuild.pid
```

Progress and completion were checked with:

```bash
tail -f logs/tb1_harbor_prebuild.log

pid=$(cat logs/tb1_harbor_prebuild.pid)
ps -o pid,ppid,pgid,sid,stat,etime,cmd -p "$pid"

grep -E 'prebuilt OK \(|failed \(' logs/tb1_harbor_prebuild.log | tail
```

No `ROOTLESS_CHOWN_WORKAROUND=1` override was used.

## Reversal

The host changes are reversible, but the subordinate ranges must not be
removed while Podman storage created with those mappings is still needed.
After stopping the user's containers and Podman service and running
`podman system migrate`, ask `lab-admin` to restore the original files if a
rollback is required:

```bash
sudo cp -a /etc/subuid.pre-ak58925 /etc/subuid
sudo cp -a /etc/subgid.pre-ak58925 /etc/subgid
```

`lab-admin` can also remove `uidmap` with `sudo apt-get remove uidmap`, but it
is required for continued use of rootless Podman with multiple IDs.
