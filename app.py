#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import datetime
import dateutil.parser
import ovh as _ovh
import sys
import traceback
import json
import requests
import docker
from datetime import datetime, timedelta
import logging
import re
import subprocess
import re
import time
import logging
from raven import Client
import machine as _machine


LOG_FORMAT = "%(asctime)s  [%(levelname)-5.5s]  %(message)s"
log = logging.getLogger(__name__)
re_flags = re.U | re.M
SENTRY_URL = os.environ.get("SENTRY_URL", None)
MACHINE_EXPIRY = int(os.environ.get("MACHINE_EXPIRY", 60 * 60 * 12))
CICD_CLOUD_PROJECT = os.environ["CICD_CLOUD_PROJECT"]
RUNNER_PATTERN = os.environ.get("RUNNER_PATTERN", "runner-[^-]+-gitlabci-as-")
LOOP_INTERVAL = int(os.environ.get("LOOP_INTERVAL", 30 * 1))
RUNNERMATCHER = re.compile(RUNNER_PATTERN, flags=re_flags | re.I)
PROBE_MODE = os.environ.get('PROBE_MODE', '')
PROBE_ALERT_WARN = os.environ.get('PROBE_ALERT_WARN', 1)
PROBE_ALERT_ERROR = os.environ.get('PROBE_ALERT_ERROR', 1)
PROBE_ALERT_WARN = (PROBE_ALERT_WARN >= PROBE_ALERT_ERROR
                    and PROBE_ALERT_ERROR
                    or PROBE_ALERT_WARN)


def report_err(sentry_url=SENTRY_URL, trace=None):
    if sentry_url:
        client = Client(sentry_url)
        client.captureException()
    elif trace:
        log.error(trace)


class Loop(object):
    def __init__(self):
        """
        relies on
        OVH_ENDPOINT
        OVH_APPLICATION_KEY
        OVH_APPLICATION_SECRET
        OVH_CONSUMER_KEY
        """
        self.ovh = _ovh.Client()
        self.machine = _machine.Machine(path="/usr/local/bin/docker-machine")

    def get_instance(self, _id):
        return self.ovh.get(
            f"/cloud/project/{CICD_CLOUD_PROJECT}/instance/{_id}"
        )

    def get_instances(self):
        instances = self.ovh.get(
            f"/cloud/project/{CICD_CLOUD_PROJECT}/instance"
        )
        for i in instances:
            try:
                i["idata"] = self.get_instance(i["id"])
            except Exception:
                i['idata'] = {}
        return instances

    def delete(self, instances):
        errors = []
        for i in instances:
            log.debug("Deleting instance {name}".format(**i))
            try:
                self.ovh.delete(
                    f"/cloud/project/{CICD_CLOUD_PROJECT}/instance/{i['id']}"
                )
            except _ovh.exceptions.ResourceNotFoundError:
                pass

    def delete_machines(self, machines):
        for m in machines:
            try:
                self.machine.rm(m["Name"], force=True)
            except RuntimeError:
                trace = traceback.format_exc()
                report_err(trace)

    def run(self):
        instances = self.get_instances()
        to_delete, machines_to_delete = [], []
        machines = self.machine.ls()
        for instance in instances:
            n = instance["name"]
            if not RUNNERMATCHER.search(n):
                log.debug(f"{n} does not match runner PATTERN, continue")
                continue
            # delete instance if in global errpr
            if instance["status"] in ["ERROR"]:
                log.debug(f"{n} in error status => DELETE")
                to_delete.append(instance)
            machine = None
            # search for a entry in docker machine matching cloud instance
            for m in machines:
                if machine_match(instance, m):
                    machine = m
                    break
            # if machine does not  exists, delete it
            if not machine:
                log.debug(f"{n} is unrelated to a machine => DELETE")
                to_delete.append(instance)
            # if machine exists, only remove it if it is too old
            else:
                created = dateutil.parser.parse(instance["created"],
                                                ignoretz=True)
                oldish = datetime.now() - timedelta(
                    seconds=MACHINE_EXPIRY
                )
                if created <= oldish:
                    log.debug(f"{n} is too old => DELETE")
            if instance in to_delete and machine is not None:
                machines_to_delete.append(m)
        for m in machines:
            for i in to_delete:
                if m["Name"] == i["name"]:
                    machines_to_delete.append(m)
        if PROBE_MODE:
            ldel = len(to_delete)
            status = 0
            if ldel > PROBE_ALERT_ERROR:
                status = 2
            elif ldel > PROBE_ALERT_WARN:
                status = 1
            print(f'Machines left: {ldel} | ldel={ldel}')
            sys.exit(status)
        else:
            self.delete(to_delete)
            self.delete_machines(machines_to_delete)


def machine_match(instance, machine):
    return machine["Name"] == instance["name"]


def __call__(*a, **kw):
    logging.basicConfig(format=LOG_FORMAT)
    level = logging.DEBUG
    if PROBE_MODE:
        level = logging.ERROR
    log.setLevel(level)
    while True:
        try:
            Loop().run()
            log.debug(f"Sleeping  {LOOP_INTERVAL}s")
            time.sleep(LOOP_INTERVAL)
        except KeyboardInterrupt:
            raise
        except Exception:  # noqa
            if PROBE_MODE:
                raise
            trace = traceback.format_exc()
            try:
                report_err(SENTRY_URL, trace)
            except Exception:
                pass
            print(trace)


if __name__ == "__main__":
    __call__()
# vim:set et sts=4 ts=4 tw=80:
