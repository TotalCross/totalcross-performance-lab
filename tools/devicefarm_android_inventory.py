#!/usr/bin/env python3
"""Non-billable Device Farm Android device inventory for SQLite storage regression.

Lists devices and existing project pools only. Never uploads apps, schedules
device tests, creates sessions or mutates AWS resources. Uses GitHub OIDC.
"""
import json
import os
from pathlib import Path
import sys
import boto3
from botocore.exceptions import ClientError

REGION="us-west-2"
VERSIONS=("8","10","12","15")


def paginate(client, operation, result_key, **args):
    items=[]
    token=None
    while True:
        params=dict(args)
        if token:
            params["nextToken"]=token
        response=getattr(client, operation)(**params)
        items.extend(response.get(result_key, []))
        token=response.get("nextToken")
        if not token:
            return items


def main():
    out=Path(os.getenv("DEVICEFARM_REPORT_DIR", "devicefarm-android-inventory"))
    out.mkdir(parents=True,exist_ok=True)
    report={"region":REGION,"requestedVersions":list(VERSIONS),
            "deviceLookup":"NOT_RUN","projectPoolLookup":"NOT_RUN",
            "scheduleInvoked":False,"devices":[],"existingPools":[]}
    try:
        client=boto3.client("devicefarm",region_name=REGION)
        # Explicitly avoid discovering only AVAILABLE phones: a BUSY device
        # is still a useful model for a later test and may soon be available.
        devices=paginate(client,"list_devices","devices",filters=[
            {"attribute":"PLATFORM","operator":"EQUALS","values":["ANDROID"]}
        ])
        inventory=[]
        for d in devices:
            version=str(d.get("os", ""))
            major=version.split(".",1)[0]
            if major not in VERSIONS:
                continue
            inventory.append({
                "arn":d.get("arn"),"name":d.get("name"),
                "manufacturer":d.get("manufacturer"),
                "model":d.get("model"),"osVersion":version,
                "osMajor":major,"availability":d.get("availability"),
                "fleetType":d.get("fleetType"),
                "formFactor":d.get("formFactor"),
                "remoteAccessEnabled":d.get("remoteAccessEnabled"),
                "instanceArn":d.get("instanceArn"),
            })
        report["devices"]=sorted(inventory,key=lambda x:(int(x["osMajor"]),x["name"] or ""))
        report["deviceLookup"]="PASS"
        project=os.getenv("AWS_DEVICE_FARM_PROJECT_ARN", "")
        if project:
            try:
                client.get_project(arn=project)
                pools=paginate(client,"list_device_pools","devicePools",arn=project)
                report["existingPools"]=[{
                    "arn":p.get("arn"),"name":p.get("name"),
                    "maxDevices":p.get("maxDevices"),"type":p.get("type"),
                    "rules":p.get("rules")
                } for p in pools]
                report["projectPoolLookup"]="PASS"
            except ClientError as err:
                report["projectPoolLookup"]="DENIED_OR_FAILED"
                report["projectPoolErrorCode"]=err.response["Error"].get("Code")
        else:
            report["projectPoolLookup"]="NOT_CONFIGURED"
        report["byVersion"]={version: [
            {"name":d["name"],"model":d["model"],
             "osVersion":d["osVersion"],
             "availability":d["availability"],
             "arn":d["arn"],
             "remoteAccessEnabled":d["remoteAccessEnabled"]}
            for d in inventory if d["osMajor"]==version] for version in VERSIONS}
        print("ANDROID_DEVICE_FARM_INVENTORY_BEGIN")
        for ver,found in report["byVersion"].items():
            print(f"Android {ver}: {len(found)} device models")
            for d in found:
                print(f"  {d['name']} | Android {d['osVersion']} | {d['availability']} | {d['arn']}")
        print("projectPoolLookup:",report["projectPoolLookup"])
        print("ANDROID_DEVICE_FARM_INVENTORY_END")
    except ClientError as err:
        report["deviceLookup"]="DENIED_OR_FAILED"
        report["deviceLookupErrorCode"]=err.response["Error"].get("Code")
        report["deviceLookupError"]=str(err)[:1200]
        print("Device Farm inventory error:",report["deviceLookupError"],file=sys.stderr)
    except Exception as err:
        report["deviceLookup"]="FAILED"
        report["deviceLookupError"]=repr(err)
        print("Device Farm inventory failed:",str(err),file=sys.stderr)
    finally:
        (out/"inventory.json").write_text(json.dumps(report,indent=2,default=str)+"\n")
    return 0 if report["deviceLookup"]=="PASS" else 1


if __name__=="__main__":
    sys.exit(main())
