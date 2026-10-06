# -*- coding: utf-8 -*-
"""A5-2 ext: download Qwen/Qwen3-VL-32B-Instruct-FP8 (HF official) to /root/models.

Pinned to the revision declared in /root/p4_download.sh L21/L45.
Disk watchdog: aborts if overlay free space drops below LOW_GB.
"""
import os, sys, time, shutil, threading

os.environ.setdefault("HF_HOME", "/root/models/.hfhome")
os.environ.setdefault("HF_HUB_CACHE", "/root/models/.hfhome/hub")
os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
from huggingface_hub import snapshot_download

REPO = "Qwen/Qwen3-VL-32B-Instruct-FP8"
REV = "4bf2c2f39c37c0fede78bede4056e1f18cdf8109"
DST = "/root/models/Qwen3-VL-32B-Instruct-FP8"
LOW_GB = 15.0          # overlay / (tightened)
LOW_MODEL_GB = 2000.0  # /model (40 T pool)
TAG = "[%s]" % time.strftime("%F_%T")


def free_gb(path="/"):
    t = shutil.disk_usage(path)
    return t.free / 1e9


_stop = threading.Event()


def watchdog():
    while not _stop.wait(20):
        f = free_gb("/")
        m = free_gb("/model")
        try:
            sz = sum(os.path.getsize(os.path.join(r, x))
                     for r, _dd, ff in os.walk(DST) for x in ff)
        except Exception:
            sz = -1
        print("%s WATCH free_root=%.2f GB free_model=%.2f GB partial=%.2f GB"
              % (time.strftime("[%F_%T]"), f, m, sz / 1e9), flush=True)
        if f < LOW_GB or m < LOW_MODEL_GB:
            print("%s !! DISK_LOW root=%.2f model=%.2f -> ABORT" %
                  (time.strftime("[%F_%T]"), f, m), flush=True)
            os._exit(9)


def main():
    print("%s START %s rev=%s -> %s" % (TAG, REPO, REV[:12], DST), flush=True)
    print("%s free before = root %.2f GB / model %.2f GB"
          % (time.strftime("[%F_%T]"), free_gb("/"), free_gb("/model")), flush=True)
    threading.Thread(target=watchdog, daemon=True).start()
    t0 = time.time()
    try:
        p = snapshot_download(repo_id=REPO, local_dir=DST, revision=REV,
                              max_workers=8, etag_timeout=60)
    except Exception as e:
        print("%s FAIL %r" % (time.strftime("[%F_%T]"), e), flush=True)
        return 4
    finally:
        _stop.set()
    el = time.time() - t0
    print("%s SNAPSHOT_OK %s elapsed=%.1fs (%.2f min) free_after=root %.2f GB / model %.2f GB"
          % (time.strftime("[%F_%T]"), p, el, el / 60.0, free_gb("/"), free_gb("/model")), flush=True)
    n = tot = 0
    for root, _d, fs in os.walk(DST):
        if "/.cache" in root:
            continue
        for f in fs:
            n += 1
            tot += os.path.getsize(os.path.join(root, f))
    print("%s PAYLOAD_FILES=%d PAYLOAD_BYTES=%d (%.3f GB)"
          % (time.strftime("[%F_%T]"), n, tot, tot / 1e9), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
