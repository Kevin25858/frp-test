"""Tests for protocol module"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frp_monitor.protocol import (
    Message,
    MessageType,
    ProbeRequest,
    ProbeResult,
    new_ping,
    new_pong,
    new_heartbeat,
    new_register,
    new_probe_start,
    new_probe_result,
)


class TestMessage:
    def test_ping_message(self):
        msg = new_ping(123)
        assert msg.type == MessageType.PING.value
        assert msg.seq == 123
        assert msg.timestamp > 0

    def test_pong_message(self):
        msg = new_pong(123, 1000000)
        assert msg.type == MessageType.PONG.value
        assert msg.seq == 123
        assert msg.timestamp == 1000000

    def test_heartbeat_message(self):
        msg = new_heartbeat()
        assert msg.type == MessageType.HEARTBEAT.value
        assert msg.timestamp > 0

    def test_register_message(self):
        msg = new_register("test-client")
        assert msg.type == MessageType.REGISTER.value
        assert msg.data == "test-client"

    def test_probe_start_message(self):
        msg = new_probe_start("1.2.3.4", "7000", "tcp")
        assert msg.type == MessageType.PROBE_START.value
        assert msg.data["server_addr"] == "1.2.3.4"
        assert msg.data["server_port"] == "7000"
        assert msg.data["protocol"] == "tcp"

    def test_probe_result_message(self):
        msg = new_probe_result(True, 25.5, "")
        assert msg.type == MessageType.PROBE_RESULT.value
        assert msg.data["success"] is True
        assert msg.data["rtt_ms"] == 25.5

    def test_encode_decode_roundtrip(self):
        original = new_probe_start("8.8.8.8", "53", "udp")
        encoded = original.encode()
        decoded = Message.decode(encoded)
        assert decoded.type == original.type
        assert decoded.data["server_addr"] == "8.8.8.8"

    def test_get_probe_request(self):
        msg = new_probe_start("1.2.3.4", "8080", "tcp")
        req = msg.get_probe_request()
        assert isinstance(req, ProbeRequest)
        assert req.server_addr == "1.2.3.4"
        assert req.server_port == "8080"
        assert req.protocol == "tcp"

    def test_get_probe_result(self):
        msg = new_probe_result(True, 10.5, "")
        result = msg.get_probe_result()
        assert isinstance(result, ProbeResult)
        assert result.success is True
        assert result.rtt_ms == 10.5


class TestProbeResult:
    def test_to_dict(self):
        result = ProbeResult(success=True, rtt_ms=15.5, error=None, timestamp=1000)
        d = result.to_dict()
        assert d["success"] is True
        assert d["rtt_ms"] == 15.5
        assert d["ts"] == 1000

    def test_from_dict(self):
        d = {"success": False, "rtt_ms": 0, "error": "timeout", "ts": 2000}
        result = ProbeResult.from_dict(d)
        assert result.success is False
        assert result.error == "timeout"
