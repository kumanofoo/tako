#!/bin/bash

set -eu

takoserver_dir="/opt/takoserver"
etc_dir="${takoserver_dir}/etc"

docker_image="takoserver:test"
docker_container="test_takoserver"

install_takoserver() {
    python3 -m venv ${takoserver_dir}
    source ${takoserver_dir}/bin/activate
    pip install wheel
    pip install .[dev]

    if [ -f /etc/default/takoserver ]; then
        echo skip install /etc/default/takoserver
    else
        install -o root -g root -m 600 takoserver /etc/default
    fi
    
    if [ -f /etc/systemd/system/takoserverd.service ]; then
        echo skip install /etc/systemd/system/takoserverd.service
    else
        install -o root -g root -m 644 \
                takoserverd.service \
                /etc/systemd/system
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
        -c "mkdir -p /root/project/takoserver && tar zxf /tmp/files.tar.gz -C /root/project/takoserver"

    # exec installer in container
    docker exec ${docker_container} /bin/bash -c "cd takoserver && /bin/bash install.sh install"
}

test_on_docker() {
    initialize_docker
    # run test
    docker exec ${docker_container} /bin/bash \
           -c "source ${takoserver_dir}/bin/activate && cd takoserver && pytest"
    stop_docker
}

run_on_docker() {
    initialize_docker
    # run takoserverd
    docker exec ${docker_container} /bin/bash \
           -c "source ${takoserver_dir}/bin/activate && takoserver"
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
