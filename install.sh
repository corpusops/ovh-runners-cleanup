#!/bin/bash
set -ex
cd "$(dirname $(readlink -f "$0"))"
W="$(pwd)"
SUNIT="${SUNIT:-"/etc/systemd/system/runnerwatcher.service"}"
NSUNIT="$(basename $SUNIT)"
cat > $SUNIT <<EOF
[Unit]
Description=DockerCompose service $NSUNIT
Before=   
After=docker.service network.service    
Requires=docker.service 
[Service]
Restart=yes
RestartSec=0
TimeoutSec=300
WorkingDirectory=$W
ExecStartPre=/usr/bin/env docker-compose  config 
ExecStartPre=/usr/bin/env docker-compose  config 
ExecStart=/usr/bin/env    docker-compose  up     
ExecStop=/usr/bin/env     docker-compose  config 
ExecStop=/usr/bin/env     docker-compose  stop   
ExecStopPost=/usr/bin/env docker-compose  config 
ExecStopPost=/usr/bin/env docker-compose  down    
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable $NSUNIT
systemctl start $NSUNIT
