# -*- coding: utf-8 -*-
"""H20 连接助手（与 a800_conn.py 同接口，便于复用同一套调用写法）。"""
import time

import paramiko

H = ('<REDACTED-POD-HOST>', 23, 'root', '<REDACTED-POD-PASSWORD2>')


def connect(h=H, tries=8, wait=8):
    last = None
    for i in range(tries):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(h[0], port=h[1], username=h[2], password=h[3],
                      timeout=25, banner_timeout=25, auth_timeout=25)
            return c
        except Exception as e:      # 瞬断/繁忙时重试
            last = e
            time.sleep(wait)
    raise last


def sh(c, cmd, timeout=300):
    _, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode('utf-8', 'replace')
    err = se.read().decode('utf-8', 'replace')
    return out + (('\n[stderr] ' + err) if err.strip() else '')


def launch(c, cmd):
    """长驻命令：用 setsid 脱离 SSH 通道，避免 paramiko 侧 PipeTimeout。"""
    tr = c.get_transport()
    ch = tr.open_session()
    ch.exec_command('setsid nohup bash -c %s </dev/null >/dev/null 2>&1 &' % _q(cmd))
    ch.close()
    return True


def _q(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"
