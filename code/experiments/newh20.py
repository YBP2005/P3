# -*- coding: utf-8 -*-
"""新 H20 连接助手：统一入口，避免各处重复写连接参数。"""
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
import paramiko

HOST = '<REDACTED-POD-HOST>'
PORT = 23
USER = 'root'
PW = '<REDACTED-POD-PASSWORD2>'
MACHINE = ('<REDACTED-POD-HOST>', 23654, 'root', '<REDACTED-POD-PASSWORD>')


def connect(host=HOST, port=PORT, user=USER, pw=PW, tries=8):
    last = None
    for i in range(tries):
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(host, port=port, username=user, password=pw, timeout=60,
                      banner_timeout=60, auth_timeout=60, look_for_keys=False, allow_agent=False)
            return c
        except Exception as ex:
            last = ex
            try:
                c.close()
            except Exception:
                pass
            time.sleep(10)
    raise last


def run(c, cmd, timeout=300):
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode('utf-8', 'replace')
    err = se.read().decode('utf-8', 'replace')
    return out, err


if __name__ == '__main__':
    c = connect()
    try:
        o, e = run(c, 'hostname; date')
        print(o.strip())
    finally:
        c.close()
