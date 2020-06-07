import time
import logging

import pytest

from helpers.cluster import ClickHouseCluster

logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())

cluster = ClickHouseCluster(__file__)

node1 = cluster.add_instance('node1', macros={'replica': 'test1'}, with_zookeeper=True)
node2 = cluster.add_instance('node2', macros={'replica': 'test2'}, with_zookeeper=True)
node3 = cluster.add_instance('node3', macros={'replica': 'test3'}, with_zookeeper=True)

@pytest.fixture(scope="module")
def started_cluster():
    try:
        cluster.start()

        for node in [node1, node2]:
            node.query("DROP DATABASE IF EXISTS testdb")
            node.query("CREATE DATABASE testdb ENGINE = Replicated('/clickhouse/databases/test1', '{replica}');")
        yield cluster

    finally:
        cluster.shutdown()


def test_create_replicated_table(started_cluster):
    DURATION_SECONDS = 1
    node1.query("CREATE TABLE testdb.replicated_table (d Date, k UInt64, i32 Int32) ENGINE=ReplicatedMergeTree(d, k, 8192);")

    time.sleep(DURATION_SECONDS)
    assert node1.query("desc table testdb.replicated_table") == node2.query("desc table testdb.replicated_table")

def test_simple_alter_table(started_cluster):
    DURATION_SECONDS = 1
    node1.query("CREATE TABLE testdb.alter_test (CounterID UInt32, StartDate Date, UserID UInt32, VisitID UInt32, NestedColumn Nested(A UInt8, S String), ToDrop UInt32) ENGINE = MergeTree(StartDate, intHash32(UserID), (CounterID, StartDate, intHash32(UserID), VisitID), 8192);")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN Added0 UInt32;")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN Added2 UInt32;")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN Added1 UInt32 AFTER Added0;")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN AddedNested1 Nested(A UInt32, B UInt64) AFTER Added2;")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN AddedNested1.C Array(String) AFTER AddedNested1.B;")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN AddedNested2 Nested(A UInt32, B UInt64) AFTER AddedNested1;")

    time.sleep(DURATION_SECONDS)
    assert node1.query("desc table testdb.alter_test") == node2.query("desc table testdb.alter_test")

def test_create_replica_after_delay(started_cluster):
    DURATION_SECONDS = 2

    node3.query("CREATE DATABASE testdb ENGINE = Replicated('/clickhouse/databases/test1', '{replica}');")

    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN Added3 UInt32 ;")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN Added4 UInt32 ;")
    node1.query("ALTER TABLE testdb.alter_test ADD COLUMN Added5 UInt32 ;")

    time.sleep(DURATION_SECONDS)

    assert node3.query("desc table testdb.alter_test") == node1.query("desc table testdb.alter_test")

def test_alters_from_different_replicas(started_cluster):
    DURATION_SECONDS = 1

    node1.query("CREATE TABLE testdb.concurrent_test (CounterID UInt32, StartDate Date, UserID UInt32, VisitID UInt32, NestedColumn Nested(A UInt8, S String), ToDrop UInt32) ENGINE = MergeTree(StartDate, intHash32(UserID), (CounterID, StartDate, intHash32(UserID), VisitID), 8192);")

    time.sleep(DURATION_SECONDS)

    node3.query("ALTER TABLE testdb.concurrent_test ADD COLUMN Added0 UInt32;")
    node1.query("ALTER TABLE testdb.concurrent_test ADD COLUMN Added2 UInt32;")
    node3.query("ALTER TABLE testdb.concurrent_test ADD COLUMN Added1 UInt32 AFTER Added0;")
    node1.query("ALTER TABLE testdb.concurrent_test ADD COLUMN AddedNested1 Nested(A UInt32, B UInt64) AFTER Added2;")
    node3.query("ALTER TABLE testdb.concurrent_test ADD COLUMN AddedNested1.C Array(String) AFTER AddedNested1.B;")
    node1.query("ALTER TABLE testdb.concurrent_test ADD COLUMN AddedNested2 Nested(A UInt32, B UInt64) AFTER AddedNested1;")

    time.sleep(DURATION_SECONDS)

    logging.info("NODE3")
    logging.info(node3.query("desc table testdb.concurrent_test"))
    logging.info("NODE1")
    logging.info(node1.query("desc table testdb.concurrent_test"))
    assert node3.query("desc table testdb.concurrent_test") == node1.query("desc table testdb.concurrent_test")