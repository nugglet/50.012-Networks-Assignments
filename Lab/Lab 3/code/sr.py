import config
import threading
import time
import udt
import util

# Extras:
# Question: what is the largest file you could send in this case?
# Answer:


class SelectiveRepeat:

    NO_PREV_ACK_MSG = "Don't have previous ACK to send, will wait for server to timeout."

    # "msg_handler" is used to deliver messages to application layer
    def __init__(self, local_port, remote_port, msg_handler):
        util.log("Starting up `Selective Repeat` protocol ... ")
        # For Sender
        self.sender_base = 0
        self.next_sequence_number = 0
        self.msg_handler = msg_handler
        self.sender_window = [b''] * config.WINDOW_SIZE
        self.ack_received = [False] * config.WINDOW_SIZE
        self.packets_sent_sender = [b''] * config.WINDOW_SIZE
        self.network_layer = udt.NetworkLayer(local_port, remote_port, self)
        self.sender_lock = threading.Lock()
        self.timer_list = [self.set_timer(-1)] * config.WINDOW_SIZE

        # For Receiver
        self.is_receiver = True
        self.receiver_base = 0
        self.receiver_packets_status = [False] * config.WINDOW_SIZE
        self.receiver_window = [b''] * config.WINDOW_SIZE

    def set_timer(self, seq_num):
        return threading.Timer((config.TIMEOUT_MSEC / 1000.0), self._timeout, {seq_num: seq_num})

    # "send" is called by application. Return true on success, false otherwise.
    def send(self, msg):
        self.is_receiver = False
        if self.next_sequence_number < (self.sender_base + config.WINDOW_SIZE):
            self._send_helper(msg)
            return True
        else:
            util.log("Window is full. App data rejected.")
            time.sleep(1)
            return False

    # Helper fn for thread to send the next packet
    def _send_helper(self, msg):
        self.sender_lock.acquire()
        packet = util.make_packet(
            msg, config.MSG_TYPE_DATA, self.next_sequence_number)
        packet_data = util.extract_data(packet)
        util.log("Sending data: " + util.pkt_to_string(packet_data))
        self.network_layer.send(packet)

        # If next sequence number is within window range, packetize and send.
        # Else return to upper layer.
        if self.next_sequence_number < self.sender_base + config.WINDOW_SIZE:
            # send packet and start timer
            pkt_index = (self.next_sequence_number -
                         self.sender_base) % config.WINDOW_SIZE
            print(pkt_index)
            self.sender_window[pkt_index] = packet
            self.ack_received[pkt_index] = False

            self.timer_list[pkt_index] = self.set_timer(
                self.next_sequence_number)
            self.timer_list[pkt_index].start()
            self.next_sequence_number += 1

        self.sender_lock.release()
        return

    # "handler" to be called by network layer when packet is ready.
    def handle_arrival_msg(self):
        msg = self.network_layer.recv()
        msg_data = util.extract_data(msg)

        # For reciever recieving packet
        # Check if reciever is getting a corrupt packet.
        # If yes, ignore packet
        if msg_data.is_corrupt:
            return

        # For sender recieving ACK
        # Shift window to smallest index available
        if msg_data.msg_type == config.MSG_TYPE_ACK:
            self.sender_lock.acquire()
            self.sender_base = msg_data.seq_num + 1
            pkt_index = (msg_data.seq_num -
                         self.sender_base) % config.WINDOW_SIZE
            self.ack_received[pkt_index] = True

            if(self.sender_base == self.next_sequence_number):
                util.log("Received ACK with seq # matching the end of the window: "
                         + util.pkt_to_string(msg_data) + ". Cancelling timer.")

                self.timer_list[pkt_index].cancel()
                self.timer_list[pkt_index] = self.set_timer(msg_data.seq_num)

            # check acks and see if meets condition to shift window
            while self.ack_received[0]:
                self.sender_base += 1
                util.log(f"Updated sender base to {self.sender_base}")

                # shift window
                self.ack_list = self.ack_list[1:] + [False]
                self.timer_list = self.timer_list[1:] + self.set_timer(-1)

                self.sender_window = self.sender_window[1:] + [b'']
            self.sender_lock.release()

        # If DATA message, assume its for receiver
        elif msg_data.msg_type == config.MSG_TYPE_DATA:
            util.log("Received DATA: " + util.pkt_to_string(msg_data))
            # Case 1: packet within window range
            # Send back ACK and add packet to buffer if not previously recieved
            if msg_data.seq_num in range(self.sender_base, self.sender_base + config.WINDOW_SIZE):
                pkt_index = (msg_data.seq_num -
                             self.sender_base) % config.WINDOW_SIZE
                self.msg_handler(msg_data.payload)
                ack_pkt = util.make_packet(
                    b'', config.MSG_TYPE_ACK, msg_data.seq_num)
                self.network_layer.send(ack_pkt)
                self.receiver_packets_status[pkt_index] = True
                self.receiver_window[pkt_index] = msg_data.payload

                # Check if condition meets to shift receiver window
                if msg_data.seq_num != self.receiver_base:
                    while self.receiver_packets_status[0]:
                        self.receiver_base += 1
                        self.rec = self.receiver_packets_status[1:] + [False]
                        self.receiver_window = self.receiver_window[1:] + [b'']
                        util.log(
                            f"Updated receiver base to {self.receiver_base}")
                    util.log("Sent ACK: " +
                             util.pkt_to_string(util.extract_data(ack_pkt)))
            else:
                # packet received late, seq number within [recv_base - N, recv_base - 1]
                # return ACK
                if (msg_data.seq_num > (self.receiver_base - config.WINDOW_SIZE)) and (msg_data.seq_num < (self.receiver_base - 1)):
                    util.log(
                        "Packet from previous window recieved. Returning ACK.")
                    ack_pkt = util.make_packet(
                        b'', config.MSG_TYPE_ACK, msg_data.seq_num)
                    self.network_layer.send(ack_pkt)
                    return
        return

    # Cleanup resources.

    def shutdown(self):
        if not self.is_receiver:
            self._wait_for_last_ACK()
        for timer in self.timer_list:
            if timer.is_alive():
                timer.cancel()
        util.log("Connection shutting down...")
        self.network_layer.shutdown()

    def _wait_for_last_ACK(self):
        while self.sender_base < self.next_sequence_number-1:
            util.log("Waiting for last ACK from receiver with sequence # "
                     + str(int(self.next_sequence_number-1)) + ".")
            time.sleep(1)

# each packet has its own logical timer
    def _timeout(self, seq_num):
        util.log("Timeout! Resending packet with seq #s "
                 + str(seq_num) + ".")
        self.sender_lock.acquire()
        pkt_index = (self.next_sequence_number -
                     self.sender_base) % config.WINDOW_SIZE
        if self.timer_list[pkt_index].is_alive():
            self.timer_list[pkt_index].cancel()
        self.timer_list[pkt_index] = self.set_timer(seq_num)

       # Resend packet
        pkt = self.sender_window[pkt_index]
        self.network_layer.send(pkt)
        util.log("Resending packet: " +
                 util.pkt_to_string(util.extract_data(pkt)))

        self.timer_list[pkt_index].start()
        self.sender_lock.release()
        return
