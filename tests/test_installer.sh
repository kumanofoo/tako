#!/bin/bash

set -u

takouser=takoyaki
takoserver_dir="/opt/takoserver"

OK() {
    echo -e '\033[0;32mOK\033[0m'
    return 0
}
NG() {
    echo -e '\033[0;31mNG\033[0m'
    return 1
}

check_directory() {
    echo -n "$1 ... "
    if [ -d "$1" ]; then
        if [ "$(stat -c '%a %U %G' $1)" = "$2 $3 $4" ]; then
            OK
        else
            NG
        fi
    else
        NG
    fi
}

check_file() {
    echo -n "$1 ... "
    if [ -f "$1" ]; then
        if [ "$(stat -c '%a %U %G' $1)" = "$2 $3 $4" ]; then
            OK
        else
            NG
        fi
    else
        NG
    fi
}

echo -n "${takouser} user ... "
if id -u "$takouser" &>/dev/null; then
    OK
else
    NG
fi
echo -n "${takouser} group ... "
if id -g "$takouser" &>/dev/null; then
    OK
else
    NG
fi

check_directory "$takoserver_dir" 750 "$takouser" "$takouser"
if [ $? = 0 ]; then
    check_directory "${takoserver_dir}/venv" 755 "$takouser" "$takouser"
    check_file "${takoserver_dir}/tako.db" 660 "$takouser" "$takouser"
fi
check_file /etc/default/takoserver 600 root root
check_file /etc/systemd/system/takoserverd.service 644 root root
