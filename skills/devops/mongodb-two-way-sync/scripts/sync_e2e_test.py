#!/usr/bin/env python3
"""
MongoDB Two-Way Sync E2E Test — 10 scenarios
Run after any sync engine change to verify correctness.

Usage:
  cd /root/.hermes/profiles/ilma
  python3 scripts/sync_e2e_test.py
"""
import sys, os, time
sys.path.insert(0, ".")
sys.path.insert(0, "sot")

from pymongo import MongoClient
from scripts.ilma_two_way_sync import _get_conflict_policy

env = {}
with open("/root/.hermes/.env") as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1); env[k] = v

WAIT = 5  # seconds per operation

loc = MongoClient(host="127.0.0.1", port=27017, username="ilma_sync",
                  password=env.get("ILMA_MONGO_LOCAL_PASS"), authSource="admin",
                  directConnection=True, serverSelectionTimeoutMS=5000)
rem = MongoClient(host=env["ILMA_MONGO_HOST"], port=int(env.get("ILMA_MONGO_PORT","27017")),
                  username=env["ILMA_MONGO_USER"], password=env["ILMA_MONGO_PASS"],
                  authSource="admin", directConnection=True, serverSelectionTimeoutMS=10000)

results = {}

# Setup test collections
tl = loc["credentials"]["_sync_test"]
tr = rem["credentials"]["_sync_test"]
tl.drop(); tr.drop()
tl2 = loc["QuantumTrafficDB"]["_sync_qt"]
tr2 = rem["QuantumTrafficDB"]["_sync_qt"]
tl2.drop(); tr2.drop()

try:
    # T1: Local insert → remote
    tl.insert_one({"_id": "t1", "val": "from_local"})
    time.sleep(WAIT)
    r1 = tr.find_one({"_id": "t1"})
    results["1_local_insert"] = r1 is not None and r1["val"] == "from_local"

    # T2: Remote insert → local
    tr.insert_one({"_id": "t2", "val": "from_remote"})
    time.sleep(WAIT)
    r2 = tl.find_one({"_id": "t2"})
    results["2_remote_insert"] = r2 is not None and r2["val"] == "from_remote"

    # T3: Local update → remote
    tl.update_one({"_id": "t1"}, {"$set": {"updated": True}})
    time.sleep(WAIT)
    r3 = tr.find_one({"_id": "t1"})
    results["3_local_update"] = r3 is not None and r3.get("updated") is True

    # T4: Remote update → local
    tr.update_one({"_id": "t2"}, {"$set": {"updated": True}})
    time.sleep(WAIT)
    r4 = tl.find_one({"_id": "t2"})
    results["4_remote_update"] = r4 is not None and r4.get("updated") is True

    # T5: Local delete → remote
    tl.insert_one({"_id": "t5", "val": "del_me"})
    time.sleep(WAIT)
    tl.delete_one({"_id": "t5"})
    time.sleep(WAIT)
    results["5_local_delete"] = tr.find_one({"_id": "t5"}) is None

    # T6: Remote delete → local
    tr.insert_one({"_id": "t6", "val": "del_r"})
    time.sleep(WAIT)
    tr.delete_one({"_id": "t6"})
    time.sleep(WAIT)
    results["6_remote_delete"] = tl.find_one({"_id": "t6"}) is None

    # T7-T8: Conflict policies
    results["7_creds_local_wins"] = _get_conflict_policy("credentials") == "local_wins"
    results["8_qtdb_remote_wins"] = _get_conflict_policy("QuantumTrafficDB") == "remote_wins"

    # T9: Cross-DB insert
    tl2.insert_one({"_id": "qt1", "val": "q_local"})
    time.sleep(WAIT)
    r9 = tr2.find_one({"_id": "qt1"})
    results["9_cross_db_insert"] = r9 is not None and r9["val"] == "q_local"

    # T10: No duplication loop
    results["10_no_dupe_loop"] = (
        tl.count_documents({}) <= 4 and tr.count_documents({}) <= 4
        and tl2.count_documents({}) <= 1 and tr2.count_documents({}) <= 1
    )
finally:
    tl.drop(); tr.drop(); tl2.drop(); tr2.drop()
    loc.close(); rem.close()

passed = sum(1 for v in results.values() if v)
total = len(results)
print(f"\n{'='*50}")
print(f"E2E: {passed}/{total} PASSED")
print(f"{'='*50}")
for k, v in results.items():
    print(f"  {'✅' if v else '❌'} {k}")

sys.exit(0 if passed == total else 1)
