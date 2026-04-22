"""Tests for storage module"""

import pytest
import sys
import os
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frp_monitor.storage import Storage, ClientRecord, MetricRecord


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def storage(db_path):
    return Storage(db_path)


class TestStorage:
    def test_save_and_get_client(self, storage):
        client_id = storage.save_client("test-client", "192.168.1.100:12345")
        assert client_id > 0

        clients = storage.get_clients()
        assert len(clients) == 1
        assert clients[0].name == "test-client"
        assert clients[0].addr == "192.168.1.100:12345"
        assert clients[0].status == "online"

    def test_save_client_updates_existing(self, storage):
        storage.save_client("test-client", "192.168.1.100:12345")
        storage.save_client("test-client", "192.168.1.200:54321")

        clients = storage.get_clients()
        assert len(clients) == 1
        assert clients[0].addr == "192.168.1.200:54321"

    def test_get_client_by_name(self, storage):
        storage.save_client("test-client", "192.168.1.100:12345")

        client = storage.get_client_by_name("test-client")
        assert client is not None
        assert client.name == "test-client"

        not_found = storage.get_client_by_name("nonexistent")
        assert not_found is None

    def test_set_client_offline(self, storage):
        storage.save_client("test-client", "192.168.1.100:12345")
        storage.set_client_offline("test-client")

        client = storage.get_client_by_name("test-client")
        assert client.status == "offline"

    def test_save_and_get_metrics(self, storage):
        client_id = storage.save_client("test-client", "192.168.1.100:12345")

        storage.save_metric(client_id, 25.5, 0.0)
        storage.save_metric(client_id, 30.0, 0.1)
        storage.save_metric(client_id, 28.0, 0.05)

        latest = storage.get_latest_metric(client_id)
        assert latest is not None
        assert latest.rtt_ms == 28.0
        assert latest.loss_rate == 0.05

    def test_get_metrics_in_time_range(self, storage):
        client_id = storage.save_client("test-client", "192.168.1.100:12345")

        now = datetime.now()
        yesterday = now - timedelta(days=1)

        # This should be within range
        storage.save_metric(client_id, 25.0, 0.0)

        metrics = storage.get_metrics(client_id, yesterday, now)
        assert len(metrics) >= 1

    def test_multiple_clients(self, storage):
        storage.save_client("client1", "192.168.1.1:1111")
        storage.save_client("client2", "192.168.1.2:2222")
        storage.save_client("client3", "192.168.1.3:3333")

        clients = storage.get_clients()
        assert len(clients) == 3
        names = {c.name for c in clients}
        assert names == {"client1", "client2", "client3"}

    def test_close(self, storage):
        storage.close()
        # Should not raise on double close
        storage.close()
