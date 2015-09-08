# -*- coding:utf-8 -*-

# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from networkapi.api_rest import exceptions as api_exceptions
from networkapi.log import Log
from . import exceptions
from networkapi.equipamento.models import Equipamento, EquipamentoAcesso
from networkapi.settings import TFTP_SERVER_ADDR
import re
from time import sleep
import unicodedata, string
import paramiko

log = Log(__name__)

class BasePlugin(object):
	'''
	Base plugin interface
	'''
	ERROR_REGEX = '[Ee][Rr][Rr][Oo][Rr]|[Ff]ail|\%|utility is occupied'
	INVALID_REGEX = '([Ii]nvalid)'
	VALID_TFTP_GET_MESSAGE = 'Copy complete, now saving to disk'
	VALID_TFTP_PUT_MESSAGE = 'bytes copied in'
	VALID_OUTPUT_CHARS = "-_.()\r\n %s%s" % (string.ascii_letters, string.digits)

	admin_privileges = 'not defined'
	GUEST_PRIVILEGES = 'not defined'
	
	connect_port = 22
	equipment = None
	equipment_access = None
	channel = None
	remote_conn = None
	tftpserver = TFTP_SERVER_ADDR
	management_vrf = ''

	def __init__(self, **kwargs):

		if 'equipment' in kwargs:
			self.equipment = kwargs.get('equipment')
		if 'equipment_access' in kwargs:
			self.equipment_access = kwargs.get('equipment_access')
		if 'connect_port' in kwargs:
			self.connect_port = kwargs.get('connect_port')
		if 'tftpserver' in kwargs:
			self.tftpserver = kwargs.get('tftpserver')

	def copyScriptFileToConfig(self, filename, use_vrf='', destination=''):
		'''
		Copy file from server to destination configuration
		By default, plugin should apply file in running configuration (active)
		'''
		raise NotImplementedError()

	def connect(self):
		'''Connects to equipment via ssh using paramiko.SSHClient  and
			sets channel variable with invoked shell object

		Raises:
			IOError: if cannot connect to host
			Exception: for other unhandled exceptions
		'''

		if self.equipment_access==None:
			try:
				self.equipment_access = EquipamentoAcesso.search(None, self.equipment, "ssh").uniqueResult()
			except e:
				log.error("Access type %s not found for equipment %s." % ("ssh", self.equipment.nome))
				raise exceptions.InvalidEquipmentAccessException()

		device = self.equipment_access.fqdn
		username = self.equipment_access.user
		password = self.equipment_access.password

		self.remote_conn=paramiko.SSHClient()
		self.remote_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())

		try:
			self.remote_conn.connect(device, port=self.connect_port, username=username, password=password)
			self.channel = self.remote_conn.invoke_shell()
		except IOError, e:
			log.error("Could not connect to host %s: %s" % (device, e))
			raise exceptions.ConnectionException(device)
		except Exception, e:
			log.error("Error connecting to host %s: %s" % (device, e))
			raise e

	def close(self):
		self.channel.close()

	def ensure_privilege_level(self, privilege_level=None):
		'''
		Ensure connection has the right privileges expected
		'''
		raise NotImplementedError()

	def exec_command (self, command, success_regex='', invalid_regex=None, error_regex=None):
		'''
		Send single command to equipment and than closes connection channel
		'''
		try:
			stdin, stdout, stderr = self.channel.exec_command('%s' %(command))
		except Exception, e:
			log.error("Error in connection. Cannot send command.", e)
			raise api_exceptions.NetworkAPIException

		equip_output_lines = stdout.readlines()
		output_text = ''.join(equip_output_lines)

		if re.search(invalid_regex, output_text, re.DOTALL ):
			raise exceptions.InvalidCommandException(output_text)
		elif re.search(error_regex, output_text, re.DOTALL):
			raise exceptions.CommandErrorException
		elif re.search(success_regex, output_text, re.DOTALL):
			return output_text
		else:
			raise exceptions.UnableToVerifyResponse()

	def removeDisallowedChars(self, data):
		data = u'%s' % data
		cleanedStr = unicodedata.normalize('NFKD', data).encode('ASCII', 'ignore')
		return ''.join(c for c in cleanedStr if c in self.VALID_OUTPUT_CHARS)

	def waitString(self, wait_str_ok_regex='', wait_str_invalid_regex=None, wait_str_failed_regex=None):

		if wait_str_invalid_regex is None:
			wait_str_invalid_regex = self.INVALID_REGEX

		if wait_str_failed_regex is None:
			wait_str_failed_regex = self.ERROR_REGEX

		string_ok = 0
		recv_string = ''
		while not string_ok:
			while not self.channel.recv_ready():
				sleep(1)
			recv_string = self.channel.recv(9999)
			file_name_string = self.removeDisallowedChars(recv_string)
			if re.search(wait_str_invalid_regex, recv_string, re.DOTALL ):
				raise exceptions.CommandErrorException(file_name_string)
			elif re.search(wait_str_failed_regex, recv_string, re.DOTALL ):
				raise exceptions.InvalidCommandException(file_name_string)
			elif re.search(wait_str_ok_regex, recv_string, re.DOTALL ):
				string_ok = 1

		return recv_string
