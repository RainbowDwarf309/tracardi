import logging
import os
from hashlib import md5

import yaml

from tracardi.domain.version import Version
from tracardi.domain.yaml_config import YamlConfig
from tracardi.service.singleton import Singleton
from tracardi.service.utils.validators import is_valid_url

VERSION = os.environ.get('_DEBUG_VERSION', '0.8.1')
TENANT_NAME = os.environ.get('TENANT_NAME', None)


def _get_logging_level(level: str) -> int:
    level = level.upper()
    if level == 'DEBUG':
        return logging.DEBUG
    if level == 'INFO':
        return logging.INFO
    if level == 'WARNING' or level == "WARN":
        return logging.WARNING
    if level == 'ERROR':
        return logging.ERROR

    return logging.WARNING


class MemoryCacheConfig:
    def __init__(self, env):
        self.event_to_profile_coping_ttl = int(env.get('EVENT_TO_PROFILE_COPY_CACHE_TTL', 2))
        self.source_ttl = int(env.get('SOURCE_CACHE_TTL', 2))
        self.session_cache_ttl = int(env.get('SESSION_CACHE_TTL', 2))
        self.event_validation_cache_ttl = int(env.get('EVENT_VALIDATION_CACHE_TTL', 2))
        self.event_metadata_cache_ttl = int(env.get('EVENT_METADATA_CACHE_TTL', 2))
        self.event_destination_cache_ttl = int(env.get('EVENT_DESTINATION_CACHE_TTL', 2))
        self.profile_destination_cache_ttl = int(env.get('PROFILE_DESTINATION_CACHE_TTL', 2))


class ElasticConfig:

    def __init__(self, env):
        self.env = env
        self.replicas = env.get('ELASTIC_INDEX_REPLICAS', "1")
        self.shards = env.get('ELASTIC_INDEX_SHARDS', "3")
        self.conf_shards = env.get('ELASTIC_CONF_INDEX_SHARDS', "1")
        self.sniff_on_start = env.get('ELASTIC_SNIFF_ON_START', None)
        self.sniff_on_connection_fail = env.get('ELASTIC_SNIFF_ON_CONNECTION_FAIL', None)
        self.sniffer_timeout = env.get('ELASTIC_SNIFFER_TIMEOUT', None)
        self.ca_file = env.get('ELASTIC_CA_FILE', None)
        self.api_key_id = env.get('ELASTIC_API_KEY_ID', None)
        self.api_key = env.get('ELASTIC_API_KEY', None)
        self.cloud_id = env['ELASTIC_CLOUD_ID'] if 'ELASTIC_CLOUD_ID' in env else None
        self.maxsize = int(env.get('ELASTIC_MAX_CONN', 25))
        self.http_compress = env.get('ELASTIC_HTTP_COMPRESS', None)
        self.verify_certs = (env['ELASTIC_VERIFY_CERTS'].lower() == 'yes') if 'ELASTIC_VERIFY_CERTS' in env else None

        self.refresh_profiles_after_save = (env['ELASTIC_REFRESH_PROFILES_AFTER_SAVE'].lower() == 'yes') \
            if 'ELASTIC_REFRESH_PROFILES_AFTER_SAVE' in env else False

        self.host = self.get_host()
        self.http_auth_username = self.env.get('ELASTIC_HTTP_AUTH_USERNAME', None)
        self.http_auth_password = self.env.get('ELASTIC_HTTP_AUTH_PASSWORD', None)
        self.scheme = self.env.get('ELASTIC_SCHEME', 'http')
        self.query_timeout = int(env.get('ELASTIC_QUERY_TIMEOUT', 12))
        self.save_pool = int(env.get('ELASTIC_SAVE_POOL', 0))
        self.save_pool_ttl = int(env.get('ELASTIC_SAVE_POOL_TTL', 5))
        self.logging_level = _get_logging_level(
            env['ELASTIC_LOGGING_LEVEL']) if 'ELASTIC_LOGGING_LEVEL' in env else logging.ERROR

        self._unset_credentials()

    def get_host(self):
        hosts = self.env.get('ELASTIC_HOST', 'http://localhost:9200')

        if not isinstance(hosts, str) or hosts.isnumeric():
            raise ValueError("Env ELASTIC_HOST must be sting")

        if not hosts:
            raise ValueError("ELASTIC_HOST environment variable not set.")
        return hosts.split(",")

    def _unset_credentials(self):
        self.env['ELASTIC_HOST'] = ""
        if 'ELASTIC_HTTP_AUTH_USERNAME' in self.env:
            del self.env['ELASTIC_HTTP_AUTH_USERNAME']
        if 'ELASTIC_HTTP_AUTH_PASSWORD' in self.env:
            del self.env['ELASTIC_HTTP_AUTH_PASSWORD']

    def has(self, prop):
        return "Set" if getattr(self, prop, None) else "Unset"


class RedisConfig:

    def __init__(self, env):
        self.env = env
        self.host = env.get('REDIS_HOST', 'localhost')
        self.port = int(env.get('REDIS_PORT', '6379'))
        self.redis_host = env.get('REDIS_HOST', 'redis://localhost:6379')
        self.redis_password = env.get('REDIS_PASSWORD', None)

        if self.host.startswith("redis://"):
            self.host = self.host[8:]

        if self.host.startswith("rediss://"):
            self.host = self.host[9:]

        if ":" in self.host:
            self.host = self.host.split(":")[0]

    def get_redis_with_password(self):
        return self.get_redis_uri(self.redis_host, password=self.redis_password)

    @staticmethod
    def get_redis_uri(host, user=None, password=None, protocol="redis", database="0"):
        if not host.startswith('redis://'):
            host = f"{protocol}://{host}/{database}"
        if user and password:
            return f"{protocol}://{user}:{password}@{host[8:]}/{database}"
        elif password:
            return f"{protocol}://:{password}@{host[8:]}/{database}"
        return host


redis_config = RedisConfig(os.environ)
elastic = ElasticConfig(os.environ)
memory_cache = MemoryCacheConfig(os.environ)


class TracardiConfig(metaclass=Singleton):

    def __init__(self, env):
        self.env = env
        _production = (env['PRODUCTION'].lower() == 'yes') if 'PRODUCTION' in env else False
        self.track_debug = (env['TRACK_DEBUG'].lower() == 'yes') if 'TRACK_DEBUG' in env else False
        self.save_logs = env.get('SAVE_LOGS', 'yes').lower() == 'yes'
        self.disable_event_destinations = env.get('DISABLE_EVENT_DESTINATIONS', 'no').lower() == 'yes'
        self.disable_profile_destinations = env.get('DISABLE_PROFILE_DESTINATIONS', 'no').lower() == 'yes'
        self.disable_workflow = env.get('DISABLE_WORKFLOW', 'no').lower() == 'yes'
        self.system_events = env.get('SYSTEM_EVENTS', 'yes').lower() == 'yes'
        self.disable_segmentation_wf_triggers = env.get('DISABLE_SEGMENTATION_WF_TRIGGERS', 'yes').lower() == 'yes'
        # Not used now
        self.cache_profiles = env.get('CACHE_PROFILE', 'no').lower() == 'yes'
        self.sync_profile_tracks_max_repeats = int(env.get('SYNC_PROFILE_TRACKS_MAX_REPEATS', 10))
        self.sync_profile_tracks_wait = int(env.get('SYNC_PROFILE_TRACKS_WAIT', 1))
        self.postpone_destination_sync = int(env.get('POSTPONE_DESTINATION_SYNC', 20))
        self.storage_driver = env.get('STORAGE_DRIVER', 'elastic')
        self.query_language = env.get('QUERY_LANGUAGE', 'kql')
        self.tracardi_pro_host = env.get('TRACARDI_PRO_HOST', 'pro.tracardi.com')
        self.tracardi_pro_port = int(env.get('TRACARDI_PRO_PORT', 40000))
        self.tracardi_scheduler_host = env.get('TRACARDI_SCHEDULER_HOST', 'scheduler.tracardi.com')
        self.logging_level = _get_logging_level(env['LOGGING_LEVEL']) if 'LOGGING_LEVEL' in env else logging.WARNING
        self.server_logging_level = _get_logging_level(
            env['SERVER_LOGGING_LEVEL']) if 'SERVER_LOGGING_LEVEL' in env else logging.WARNING
        self.multi_tenant = env.get('MULTI_TENANT', "no") == 'yes'
        self.multi_tenant_manager_url = env.get('MULTI_TENANT_MANAGER_URL', None)
        self.multi_tenant_manager_api_key = env.get('MULTI_TENANT_MANAGER_API_KEY', None)
        self.version: Version = Version(version=VERSION, name=TENANT_NAME, production=_production)
        self.installation_token = env.get('INSTALLATION_TOKEN', 'tracardi')
        random_hash = md5(f"akkdskjd-askmdj-jdff-3039djn-{self.version.db_version}".encode()).hexdigest()
        self.internal_source = f"@internal-{random_hash[:20]}"
        self.cardio_source = f"@heartbeats-{random_hash[:20]}"
        self.segmentation_source = f"@segmentation-{random_hash[:20]}"
        self._config = None
        self._unset_secrets()

        if self.multi_tenant and (self.multi_tenant_manager_url is None or self.multi_tenant_manager_api_key is None):
            if self.multi_tenant_manager_url is None:
                raise AssertionError('No MULTI_TENANT_MANAGER_URL set for MULTI_TENANT mode. Either set '
                                     'the MULTI_TENANT_MANAGER_URL or set MULTI_TENANT to "no"')

            if self.multi_tenant_manager_api_key is None:
                raise AssertionError('No MULTI_TENANT_MANAGER_API_KEY set for MULTI_TENANT mode. Either set '
                                     'the MULTI_TENANT_MANAGER_API_KEY or set MULTI_TENANT to "no"')

        if self.multi_tenant and not is_valid_url(self.multi_tenant_manager_url):
            raise AssertionError('Env MULTI_TENANT_MANAGER_URL is not valid URL.')

    @property
    def config(self) -> YamlConfig:
        if not self._config:
            config = self.env.get('CONFIG', 'config.yaml')
            with open(config, "r") as stream:
                config = yaml.safe_load(stream)
                self._config = YamlConfig(**config)
        return self._config

    def _unset_secrets(self):
        self.env['INSTALLATION_TOKEN'] = ""


tracardi = TracardiConfig(os.environ)
