from __future__ import absolute_import, unicode_literals

from struct import pack

from amqp import spec
from amqp.basic_message import Message
from amqp.exceptions import UnexpectedFrame
from amqp.method_framing import frame_handler, frame_writer

from .case import Case, Mock


class test_frame_handler(Case):

    def setup(self):
        self.conn = Mock(name='connection')
        self.conn.bytes_recv = 0
        self.callback = Mock(name='callback')
        self.g = frame_handler(self.conn, self.callback)

    def test_header(self):
        buf = pack('>HH', 60, 51)
        self.g((1, 1, buf))
        self.callback.assert_called_with(1, (60, 51), buf, None)
        self.assertTrue(self.conn.bytes_recv)

    def test_header_message_empty_body(self):
        self.g((1, 1, pack('>HH', *spec.Basic.Deliver)))
        self.assertFalse(self.callback.called)

        with self.assertRaises(UnexpectedFrame):
            self.g((1, 1, pack('>HH', *spec.Basic.Deliver)))

        m = Message()
        m.properties = {}
        buf = pack('>HxxQ', m.CLASS_ID, 0)
        buf += m._serialize_properties()
        self.g((2, 1, buf))

        self.assertTrue(self.callback.called)
        msg = self.callback.call_args[0][3]
        self.callback.assert_called_with(
            1, msg.frame_method, msg.frame_args, msg,
        )

    def test_header_message_content(self):
        self.g((1, 1, pack('>HH', *spec.Basic.Deliver)))
        self.assertFalse(self.callback.called)

        m = Message()
        m.properties = {}
        buf = pack('>HxxQ', m.CLASS_ID, 16)
        buf += m._serialize_properties()
        self.g((2, 1, buf))
        self.assertFalse(self.callback.called)

        self.g((3, 1, b'thequick'))
        self.assertFalse(self.callback.called)

        self.g((3, 1, b'brownfox'))
        self.assertTrue(self.callback.called)
        msg = self.callback.call_args[0][3]
        self.callback.assert_called_with(
            1, msg.frame_method, msg.frame_args, msg,
        )
        self.assertEqual(msg.body, b'thequickbrownfox')

    def test_heartbeat_frame(self):
        self.g((8, 1, ''))
        self.assertTrue(self.conn.bytes_recv)


class test_frame_writer(Case):

    def setup(self):
        self.connection = Mock(name='connection')
        self.transport = self.connection.Transport()
        self.connection.frame_max = 512
        self.connection.bytes_sent = 0
        self.g = frame_writer(self.connection, self.transport)
        self.write = self.transport.write

    def test_write_fast_header(self):
        frame = 1, 1, spec.Queue.Declare, b'x' * 30, None
        self.g.send(frame)
        self.assertTrue(self.write.called)

    def test_write_fast_content(self):
        msg = Message(body=b'y' * 10, content_type='utf-8')
        frame = 2, 1, spec.Basic.Publish, b'x' * 10, msg
        self.g.send(frame)
        self.assertTrue(self.write.called)

    def test_write_slow_content(self):
        msg = Message(body=b'y' * 2048, content_type='utf-8')
        frame = 2, 1, spec.Basic.Publish, b'x' * 10, msg
        self.g.send(frame)
        self.assertTrue(self.write.called)
