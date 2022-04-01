"""
DPDK L3 Exact Match (match fields, actions) with TAP Port
"""

# in-built module imports
import time

# ptf related imports
import ptf
import ptf.dataplane as dataplane
from ptf.base_tests import BaseTest
from ptf.testutils import *
from ptf import config

# scapy related imports
from scapy.packet import *
from scapy.fields import *
from scapy.all import *

# framework related imports
import common.utils.ovsp4ctl_utils as ovs_p4ctl
import common.utils.test_utils as test_utils
from common.utils.config_file_utils import get_config_dict, get_params_tap_port_simple, get_interface_ipv4_dict
from common.utils.gnmi_cli_utils import gnmi_cli_set_and_verify, gnmi_set_params, ifconfig_set_ipv4


class L3_Exact_Match(BaseTest):

    def setUp(self):
        BaseTest.setUp(self)
        config["relax"] = True # for verify_packets to ignore other packets received at the interface
        
        test_params = test_params_get()
        config_json = test_params['config_json']
        self.dataplane = ptf.dataplane_instance
        ptf.dataplane_instance = ptf.dataplane.DataPlane(config)

        self.config_data = get_config_dict(config_json)
        self.gnmicli_params = get_params_tap_port_simple(self.config_data)
        self.interface_ip_list = get_interface_ipv4_dict(self.config_data)

        self.PASSED = True

    def runTest(self):
        gnmi_set_params(self.gnmicli_params)
        ifconfig_set_ipv4(self.interface_ip_list)

        port_list = self.config_data['port_list']
        port_ids = test_utils.add_port_to_dataplane(port_list)

        for port_id, ifname in config["port_map"].items():
            device, port = port_id
            self.dataplane.port_add(ifname, device, port)

        ovs_p4ctl.ovs_p4ctl_set_pipe(self.config_data['switch'], self.config_data['pb_bin'], self.config_data['p4_info'])

        for table in self.config_data['table']:

            print(f"Scenario : l3 exact match : {table['description']}")
            print(f"Adding {table['description']} rules")
            for match_action in table['match_action']:
                ovs_p4ctl.ovs_p4ctl_add_entry(table['switch'],table['name'], match_action)

            # forming 1st packet and sending to validate if scenario-1:rule-1 hits or not
            print("sending packet to check if rule 1  hits")
            if table['description'] == "table_for_dst_ip":
                pkt = simple_tcp_packet(ip_dst=self.config_data['traffic']['in_pkt_header']['ip_dst_1'])
            else:
                pkt = simple_tcp_packet(ip_dst=self.config_data['traffic']['in_pkt_header']['ip_src_1'])

            # Verify whether packet is received as per rule 1 
            send_packet(self, port_ids[self.config_data['traffic']['send_port'][0]], pkt)
            try:
                verify_packets(self, pkt, device_number=0, ports=[port_ids[self.config_data['traffic']['receive_port'][0]][1]])
                print(f"PASS: Verification of packets passed, packet received as per rule 1")
            except Exception as err:
                print(f"FAIL: Verification of packets sent failed with exception {err}")
                self.PASSED = False
        
            # forming 2th packet and sending to validate if scenario-1:rule-2 hits or not
            print("sending packet to check if rule2 hits")
            if table['description'] == "table_for_dst_ip":
                pkt = simple_tcp_packet(ip_dst=self.config_data['traffic']['in_pkt_header']['ip_dst_2'])
            else:
                pkt = simple_tcp_packet(ip_dst=self.config_data['traffic']['in_pkt_header']['ip_src_2'])
            # Verify whether packet is dropped as per rule 2
            send_packet(self, port_ids[self.config_data['traffic']['send_port'][1]], pkt)
            try:
                verify_no_packet_any(self, pkt, device_number=0, ports=[port_ids[self.config_data['traffic']['receive_port'][1]][1]])
                print(f"PASS: Verification of packets passed, packet dropped as per rule 2")
            except Exception as err:
                print(f"FAIL: Verification of packets sent failed with exception {err}")
                self.PASSED = False

        self.dataplane.kill()


    def tearDown(self):
        for table in self.config_data['table']:
            print(f"Deleting {table['description']} rules")
            for del_action in table['del_action']:
                ovs_p4ctl.ovs_p4ctl_del_entry(table['switch'], table['name'], del_action)
        
        if self.PASSED:
            print("Test has PASSED")
        else:
            print("Test has FAILED")

 

