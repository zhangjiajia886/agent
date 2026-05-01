#!/bin/bash
# 快捷停止脚本，委托给 start.sh stop
exec "$(cd "$(dirname "$0")" && pwd)/start.sh" stop
