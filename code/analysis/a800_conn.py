# -*- coding: utf-8 -*-
"""带重试的连接器（公用）：本项目已多次遇到 sshd 握手 EOFError，必须重试并区分"抖动"与"机器没开"。"""
import time

import paramiko


def connect(host, tries=8, wait=8):
    last = None
    for i in range(tries):
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(host[0], port=host[1], username=host[2], password=host[3], timeout=45,
                      banner_timeout=45, auth_timeout=45, look_for_keys=False, allow_agent=False)
            return c
        except Exception as ex:
            last = ex
            try:
                c.close()
            except Exception:
                pass
            time.sleep(wait)
    raise last


def sh(c, cmd, t=240):
    si, so, se = c.exec_command(cmd, timeout=t)
    return (so.read().decode('utf-8', 'replace') + se.read().decode('utf-8', 'replace')).strip()


def launch(c, cmd):
    """非阻塞启动：发出即弃掉通道（读完 stdout 会 PipeTimeout）。"""
    si, so, se = c.exec_command(cmd, timeout=8)
    time.sleep(1)
    for f in (so, se):
        try:
            f.channel.close()
        except Exception:
            pass
