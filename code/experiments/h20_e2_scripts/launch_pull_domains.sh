#!/bin/bash
mkdir -p /root/logs
cd /root
setsid nohup /usr/local/miniconda3/bin/python3 -u /root/pull_domains.py < /dev/null > /root/logs/pull_domains.log 2>&1 &
echo "PULL_DOMAINS_LAUNCHED pid=$!"
