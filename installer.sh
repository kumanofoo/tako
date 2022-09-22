#!/bin/bash

set -u

takouser=takoyaki
takoserver_dir="/opt/takoserver"
takodb=tako.db

docker_image="takoserver:test"
docker_container="test_takoserver"

install_takoserver() {
    if id "${takouser}" &>/dev/null; then
        echo $takouser user already exists.
    else
        useradd -d ${takoserver_dir} -s /usr/sbin/nologin -r ${takouser} || exit $?
    fi
    if [ -d "${takoserver_dir}" ]; then
        echo ${takoserver_dir} already exists.
    else
        install -m 750 -o ${takouser} -g ${takouser} -d ${takoserver_dir} || exit $?
    fi
    python3 -m venv "${takoserver_dir}/venv" || exit $?
    . "${takoserver_dir}/venv/bin/activate" && pip install --upgrade pip && pip install wheel && pip install .[dev] || exit $?
    chown takoyaki:takoyaki -R "${takoserver_dir}/venv" || exit $?
    if [ -f "${takoserver_dir}/${takodb}" ]; then
        echo "${takoserver_dir}/${takodb}" already exists.
    else
        install -m 660 -o ${takouser} -g ${takouser} /dev/null ${takoserver_dir}/${takodb} || exit $?
    fi
    if [ -f /etc/default/takoserver ]; then
        echo skip install /etc/default/takoserver
    else
        install -o root -g root -m 600 takoserver /etc/default || exit $?
    fi
    
    if [ -f /etc/systemd/system/takoserverd.service ]; then
        echo skip install /etc/systemd/system/takoserverd.service
    else
        install -o root -g root -m 644 \
                takoserverd.service \
                /etc/systemd/system || exit $?
    fi

    cat <<EOF

Start takoserverd service
$ sodo systemctl start takoserverd

Check takoserverd service
$ systemctl status takoserverd

Enable to start takoserverd service on system boot 
$ sudo systemctl enable takoserverd

EOF
}

uninstall_takoserver() {
    read -p "Are you sure (yes/NO)? " reply
    case "${reply}" in
        yes)
            ;;
        *)
            echo canceled
            exit 1
            ;;
    esac

    systemctl stop takoserverd
    systemctl disable takoserverd
    rm /etc/systemd/system/takoserverd.service
    rm /etc/default/takoserver
    rm -r ${takoserver_dir}
    userdel ${takouser}
}

initialize_docker() {
    # build docker image
    (docker image build -t ${docker_image} -f Dockerfile .)

    # run docker container and install takoserver
    if [ -f docker/takoserver ]; then
        docker run -itd --rm -e TZ=Asia/Tokyo --env-file=docker/takoserver --name ${docker_container} ${docker_image}
    else
        docker run -itd --rm -e TZ=Asia/Tokyo --name ${docker_container} ${docker_image}
    fi

    # set signal handler
    trap "docker stop ${docker_container}" SIGINT SIGHUP

    # copy takoserver files to container
    temp_dir=$(mktemp -d)
    takoserver_files=${temp_dir}/files.tar.gz
    tar zcf ${takoserver_files} $(git ls-files)
    docker cp ${takoserver_files} ${docker_container}:/tmp/
    rm ${takoserver_files}
    rmdir ${temp_dir}
    docker exec ${docker_container} /bin/bash \
        -c "mkdir -p /tmp/takoserver && tar zxf /tmp/files.tar.gz -C /tmp/takoserver"

    # exec installer in container
    docker exec ${docker_container} /bin/bash -c "cd /tmp/takoserver && /bin/bash installer.sh install"
}

test_on_docker() {
    initialize_docker
    # run test
    docker exec ${docker_container} /bin/bash \
           -c "source ${takoserver_dir}/venv/bin/activate && cd /tmp/takoserver && pytest"
    stop_docker
}

run_on_docker() {
    initialize_docker
    # run takoserverd
    docker exec ${docker_container} /bin/bash \
           -c "source ${takoserver_dir}/venv/bin/activate && takoserver"
}

stop_docker() {
    container=$(docker ps | grep -c ${docker_container})
    if [ $container = 1 ]; then
        docker stop ${docker_container}
    fi
}

usage () {
    echo "usage: ${0##*/} [install|uninstall|test-docker|run-docker|stop-docker]"
}

if [ $# -ne 1 ]; then
    usage
    exit 0
fi

case "$1" in
    install)
        install_takoserver
        ;;
    uninstall)
        uninstall_takoserver
        ;;
    test-docker)
        test_on_docker
        ;;
    run-docker)
        run_on_docker
        ;;
    stop-docker)
        stop_docker
        ;;
    *)
        usage
        ;;
esac

exit 0
