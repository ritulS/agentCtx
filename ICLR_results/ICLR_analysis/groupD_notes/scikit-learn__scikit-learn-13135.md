# scikit-learn__scikit-learn-13135 — why compression-robust (Group D)
82 runs, resolve 0.80. Gold = 1 line (`centers.sort()`) in `sklearn/preprocessing/_discretization.py`.

## 1. Task shape: maximally localized
- PR text carries the full traceback (file, `transform()`, line 255) AND the cause ("centers and
  consequently bin_edges being unsorted"). Location and fix are both stated up front.
- FC run_3: s1 `find|grep -l KBinsDiscretizer`, s2 `cat _discretization.py`, s3 `sed -n '130,180p'`,
  edit s22. **Exactly 1 source file opened before first edit** (same FC run_1/2). Working set = one
  15-line window (165-180). Re-derivable from PR + one read: yes.
- Recovery after any wipe costs one command: `grep -n cluster_centers_ <file>` → line 174
  (TR b10k/r3 s72, TRC-SS b10k/r1 s61, OTRC-TR b20k/r1 s117).

## 2. Environment: reproduction impossible; it did not matter
- `python` = /opt/miniconda3 py3.11 but /testbed .so are cpython-36m → every import of testbed
  sklearn dies: `No module named 'sklearn.__check_build._check_build'` (FC/r3 s12); `setup.py
  build_ext` fails at `CompileError: sklearn/ensemble/_gradient_boosting.pyx` (s9). **No run in any
  condition ever executed the repro or tests against the patched testbed.**
- Second trap: agents `pip install scikit-learn` (1.1.3/1.2.0/1.9.0) which already CONTAINS the gold
  fix, so `cd /tmp && python repro.py` prints "Success!" (FC/r3 s11). Agents read this correctly as
  "testbed is the old version" and continued.
- Verification substitute: standalone `from sklearn.cluster import KMeans` simulation — TR b10k/r3
  s23 `centers: [0.25 3. 10. 2. 9.] sorted? False`; s27 after sort `bin_edges monotonically
  increasing? True`. FC/r3 verified by reading `git diff` only (s33) and still resolved.

## 3. Compression before first edit: clean restart that re-converges
- TR b10k/r3 (8 comps @11,16,23,32,41,46,55,67; 10.3k→4.3k tok): after comp@41 it has forgotten its
  s25 edit and re-explores from zero (s42 `cat|head -300`, s43/48/49 re-reads, s46/50 re-run the
  KMeans simulation), re-applies the same fix at s52. Nothing pre-compression was needed — msg1 (PR
  text) + one `sed -n` rebuilds the state. ~20 of 76 steps are re-reads of window 165-185.
- TRC-SS b10k/r1 (12 comps, first @15): s16-43 pip-version rabbit hole; after comp@28/45 restarts
  cleanly (s45-50 re-read file), edits s51.
- The saver is an idempotent, self-verifying edit loop: every `sed -i` is followed by `sed -n` on the
  same window, and bad line offsets are detected and undone from the file alone, no history needed
  (TR/r3 52→53→54→56; TRC-SS/r1 51→53→58→63).

## 4. Edit correctness
- First edit gold-equivalent in every resolved run. Three accepted variants: `centers =
  np.sort(centers)`, `centers.sort()`, inline `np.sort(km.fit(...).cluster_centers_[:, 0])`.
  d05__b20k__tr/run_1's patch is byte-identical to gold including the comment.
- Pre-submit verification = re-read window + `git diff`; never a test run.

## 5. Failing runs (16)
- **11 = eval anomaly**: label silent_crash but `info.exit_status == "Submitted"` with a
  gold-equivalent patch — su-full b20k r1,r2; trc b20k r1,r2; ss b20k r1,r2; tr b10k r2; trc b10k
  r1,r2; tr b20k r1,r2. (su-full b20k/r1 adds a redundant second `np.sort` on bin_edges — a no-op.)
- otrc-tr b10k/r3 — **task description wiped**: traj msg[1] = `[tool-result cleared — online-trc —
  2762 tok — step 24]`. Agent drifted to a different bug (quantile + duplicate values), rewrote the
  whole file via `cat > … << EOF` at s54, echo-looped s113-116 to the limit. Wrong fix, no submit.
- otrc-tr b20k/r1, r2 (120 online clears each) — correct fix applied (r1 s105) but never submitted:
  having lost the record of prior failures it re-ran `setup.py build_ext` (s96,107,120) and
  pip-version roulette (s97,98,108,111) to step 125. LimitsExceeded.
- otrc-ss-partial b15k/r2 (104 clears) — correct fix in tree (s93/99), same build_ext/pip retry loop
  (s90,96,101-103,107), no submission, empty exit_status.
- su-full b15k/r3 — correct fix at s22, then ~100 steps comparing against installed sklearn (at s125
  it literally reads the gold `centers.sort()` upstream) without emitting submit. LimitsExceeded.

## 6. Verdict
The task survives compression because its entire state is a *regenerable* triple: PR text (traceback
+ file + cause), one file, one 15-line window that any single grep/sed reconstructs. Compression
deletes redundancy, not information — after a wipe the agent restarts clean down the identical short
path onto one of three equivalent one-line patches, and it verifies by re-reading the file rather
than running anything, which is essential because the container can never import the patched testbed.
Limits appear only where compression touches something non-regenerable or non-idempotent: online
clearing can remove the *goal* (otrc-tr b10k/r3, msg1 wiped → wrong-bug drift) or the *memory of
negative results*, turning a broken build environment into an unbounded retry loop (all 4 OTRC runs →
LimitsExceeded). Threshold TR/TRC/SU/SS never touch msg1; 11 of their 12 "failures" are mislabeled
gold-equivalent submissions and the 12th is one no-submit verification loop. Robustness here is a
property of re-derivability, not of retention.
