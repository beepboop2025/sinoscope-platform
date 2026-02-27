"""
DragonScope Enterprise RBAC (Role-Based Access Control)

Provides hierarchical roles, granular permissions, and resource-based authorization
for the DragonScope terminal fleet management platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union
from functools import total_ordering
import json


# ============================================================================
# Permission Enums - 500+ Granular Permissions
# ============================================================================

class PermissionCategory(Enum):
    """Permission categories for organization."""
    TERMINAL = "terminal"
    FLEET = "fleet"
    USER = "user"
    ROLE = "role"
    SECURITY = "security"
    AUDIT = "audit"
    INTEGRATION = "integration"
    BILLING = "billing"
    SYSTEM = "system"
    WORKFLOW = "workflow"
    MONITORING = "monitoring"
    NOTIFICATION = "notification"
    API = "api"
    REPORT = "report"


class Permission(Enum):
    """
    Granular permissions for DragonScope operations.
    
    Naming convention: <resource>.<action>[_<modifier>]
    
    Total: 500+ permissions covering all platform operations.
    """
    
    # =========================================================================
    # TERMINAL PERMISSIONS (150)
    # =========================================================================
    
    # Terminal View/Discovery (20)
    TERMINAL_VIEW = "terminal.view"
    TERMINAL_VIEW_DETAILS = "terminal.view_details"
    TERMINAL_VIEW_SENSITIVE = "terminal.view_sensitive"
    TERMINAL_LIST = "terminal.list"
    TERMINAL_SEARCH = "terminal.search"
    TERMINAL_FILTER = "terminal.filter"
    TERMINAL_EXPORT_LIST = "terminal.export_list"
    TERMINAL_VIEW_MAP = "terminal.view_map"
    TERMINAL_VIEW_TOPOLOGY = "terminal.view_topology"
    TERMINAL_VIEW_STATUS = "terminal.view_status"
    TERMINAL_VIEW_HEALTH = "terminal.view_health"
    TERMINAL_VIEW_METRICS = "terminal.view_metrics"
    TERMINAL_VIEW_CONNECTIONS = "terminal.view_connections"
    TERMINAL_VIEW_SESSIONS = "terminal.view_sessions"
    TERMINAL_VIEW_TAGS = "terminal.view_tags"
    TERMINAL_VIEW_CUSTOM_FIELDS = "terminal.view_custom_fields"
    TERMINAL_VIEW_CERTIFICATES = "terminal.view_certificates"
    TERMINAL_VIEW_NETWORK = "terminal.view_network"
    TERMINAL_VIEW_HARDWARE = "terminal.view_hardware"
    
    # Terminal Connection (30)
    TERMINAL_CONNECT = "terminal.connect"
    TERMINAL_CONNECT_SSH = "terminal.connect_ssh"
    TERMINAL_CONNECT_SERIAL = "terminal.connect_serial"
    TERMINAL_CONNECT_TELNET = "terminal.connect_telnet"
    TERMINAL_CONNECT_VNC = "terminal.connect_vnc"
    TERMINAL_CONNECT_RDP = "terminal.connect_rdp"
    TERMINAL_CONNECT_KVM = "terminal.connect_kvm"
    TERMINAL_CONNECT_IPMI = "terminal.connect_ipmi"
    TERMINAL_CONNECT_BMC = "terminal.connect_bmc"
    TERMINAL_CONNECT_WEB = "terminal.connect_web"
    TERMINAL_CONNECT_API = "terminal.connect_api"
    TERMINAL_DISCONNECT = "terminal.disconnect"
    TERMINAL_DISCONNECT_OTHERS = "terminal.disconnect_others"
    TERMINAL_FORCE_DISCONNECT = "terminal.force_disconnect"
    TERMINAL_RECONNECT = "terminal.reconnect"
    TERMINAL_TRANSFER_SESSION = "terminal.transfer_session"
    TERMINAL_SHARE_SESSION = "terminal.share_session"
    TERMINAL_VIEW_SESSION_LOGS = "terminal.view_session_logs"
    TERMINAL_DOWNLOAD_SESSION_LOGS = "terminal.download_session_logs"
    TERMINAL_RECORD_SESSION = "terminal.record_session"
    TERMINAL_PAUSE_RECORDING = "terminal.pause_recording"
    TERMINAL_CONFIGURE_SESSION = "terminal.configure_session"
    TERMINAL_SET_SESSION_TIMEOUT = "terminal.set_session_timeout"
    TERMINAL_LIMIT_BANDWIDTH = "terminal.limit_bandwidth"
    TERMINAL_ENABLE_ENCRYPTION = "terminal.enable_encryption"
    TERMINAL_CONFIGURE_PROXY = "terminal.configure_proxy"
    TERMINAL_USE_JUMP_HOST = "terminal.use_jump_host"
    TERMINAL_CONFIGURE_TMUX = "terminal.configure_tmux"
    
    # Terminal Command Execution (25)
    TERMINAL_EXECUTE = "terminal.execute"
    TERMINAL_EXECUTE_READ = "terminal.execute_read"
    TERMINAL_EXECUTE_WRITE = "terminal.execute_write"
    TERMINAL_EXECUTE_ADMIN = "terminal.execute_admin"
    TERMINAL_EXECUTE_SCRIPT = "terminal.execute_script"
    TERMINAL_EXECUTE_BATCH = "terminal.execute_batch"
    TERMINAL_EXECUTE_PIPELINE = "terminal.execute_pipeline"
    TERMINAL_EXECUTE_SUDO = "terminal.execute_sudo"
    TERMINAL_EXECUTE_AS_ROOT = "terminal.execute_as_root"
    TERMINAL_EXECUTE_REMOTE = "terminal.execute_remote"
    TERMINAL_EXECUTE_PARALLEL = "terminal.execute_parallel"
    TERMINAL_EXECUTE_SCHEDULED = "terminal.execute_scheduled"
    TERMINAL_EXECUTE_INTERACTIVE = "terminal.execute_interactive"
    TERMINAL_EXECUTE_BACKGROUND = "terminal.execute_background"
    TERMINAL_KILL_PROCESS = "terminal.kill_process"
    TERMINAL_KILL_OTHERS_PROCESS = "terminal.kill_others_process"
    TERMINAL_SEND_SIGNAL = "terminal.send_signal"
    TERMINAL_SEND_CTRL_C = "terminal.send_ctrl_c"
    TERMINAL_SEND_CTRL_Z = "terminal.send_ctrl_z"
    TERMINAL_MODIFY_ENV = "terminal.modify_env"
    TERMINAL_VIEW_ENV = "terminal.view_env"
    TERMINAL_SET_WORKDIR = "terminal.set_workdir"
    TERMINAL_CHANGE_USER = "terminal.change_user"
    TERMINAL_IMPERSONATE = "terminal.impersonate"
    
    # Terminal File Operations (25)
    TERMINAL_FILE_VIEW = "terminal.file_view"
    TERMINAL_FILE_READ = "terminal.file_read"
    TERMINAL_FILE_WRITE = "terminal.file_write"
    TERMINAL_FILE_APPEND = "terminal.file_append"
    TERMINAL_FILE_CREATE = "terminal.file_create"
    TERMINAL_FILE_DELETE = "terminal.file_delete"
    TERMINAL_FILE_RENAME = "terminal.file_rename"
    TERMINAL_FILE_MOVE = "terminal.file_move"
    TERMINAL_FILE_COPY = "terminal.file_copy"
    TERMINAL_FILE_UPLOAD = "terminal.file_upload"
    TERMINAL_FILE_DOWNLOAD = "terminal.file_download"
    TERMINAL_FILE_UPLOAD_BINARY = "terminal.file_upload_binary"
    TERMINAL_FILE_DOWNLOAD_BINARY = "terminal.file_download_binary"
    TERMINAL_FILE_BULK_UPLOAD = "terminal.file_bulk_upload"
    TERMINAL_FILE_BULK_DOWNLOAD = "terminal.file_bulk_download"
    TERMINAL_FILE_EDIT = "terminal.file_edit"
    TERMINAL_FILE_EDIT_SUDO = "terminal.file_edit_sudo"
    TERMINAL_FILE_CHMOD = "terminal.file_chmod"
    TERMINAL_FILE_CHOWN = "terminal.file_chown"
    TERMINAL_FILE_ARCHIVE = "terminal.file_archive"
    TERMINAL_FILE_EXTRACT = "terminal.file_extract"
    TERMINAL_FILE_SEARCH = "terminal.file_search"
    TERMINAL_FILE_GREP = "terminal.file_grep"
    TERMINAL_FILE_SYNC = "terminal.file_sync"
    TERMINAL_FILE_MOUNT = "terminal.file_mount"
    
    # Terminal Management (20)
    TERMINAL_CREATE = "terminal.create"
    TERMINAL_UPDATE = "terminal.update"
    TERMINAL_UPDATE_CONFIG = "terminal.update_config"
    TERMINAL_DELETE = "terminal.delete"
    TERMINAL_DELETE_BULK = "terminal.delete_bulk"
    TERMINAL_ARCHIVE = "terminal.archive"
    TERMINAL_RESTORE = "terminal.restore"
    TERMINAL_CLONE = "terminal.clone"
    TERMINAL_RENAME = "terminal.rename"
    TERMINAL_TAG = "terminal.tag"
    TERMINAL_UNTAG = "terminal.untag"
    TERMINAL_SET_CUSTOM_FIELDS = "terminal.set_custom_fields"
    TERMINAL_ASSIGN_TO_FLEET = "terminal.assign_to_fleet"
    TERMINAL_REMOVE_FROM_FLEET = "terminal.remove_from_fleet"
    TERMINAL_SET_MAINTENANCE = "terminal.set_maintenance"
    TERMINAL_WAKEUP = "terminal.wakeup"
    TERMINAL_SHUTDOWN = "terminal.shutdown"
    TERMINAL_REBOOT = "terminal.reboot"
    TERMINAL_POWER_CYCLE = "terminal.power_cycle"
    
    # Terminal Diagnostics (15)
    TERMINAL_PING = "terminal.ping"
    TERMINAL_TRACE_ROUTE = "terminal.trace_route"
    TERMINAL_PORT_SCAN = "terminal.port_scan"
    TERMINAL_NETWORK_DIAG = "terminal.network_diag"
    TERMINAL_HARDWARE_DIAG = "terminal.hardware_diag"
    TERMINAL_DISK_CHECK = "terminal.disk_check"
    TERMINAL_MEMORY_CHECK = "terminal.memory_check"
    TERMINAL_CPU_CHECK = "terminal.cpu_check"
    TERMINAL_PROCESS_LIST = "terminal.process_list"
    TERMINAL_SERVICE_STATUS = "terminal.service_status"
    TERMINAL_LOG_VIEW = "terminal.log_view"
    TERMINAL_LOG_TAIL = "terminal.log_tail"
    TERMINAL_LOG_EXPORT = "terminal.log_export"
    TERMINAL_PERFORMANCE_TEST = "terminal.performance_test"
    TERMINAL_BANDWIDTH_TEST = "terminal.bandwidth_test"
    
    # Terminal Security (15)
    TERMINAL_VIEW_FIREWALL = "terminal.view_firewall"
    TERMINAL_MODIFY_FIREWALL = "terminal.modify_firewall"
    TERMINAL_VIEW_CERTS = "terminal.view_certs"
    TERMINAL_INSTALL_CERT = "terminal.install_cert"
    TERMINAL_REVOKE_CERT = "terminal.revoke_cert"
    TERMINAL_ROTATE_KEYS = "terminal.rotate_keys"
    TERMINAL_VIEW_SSH_CONFIG = "terminal.view_ssh_config"
    TERMINAL_MODIFY_SSH_CONFIG = "terminal.modify_ssh_config"
    TERMINAL_ENABLE_2FA = "terminal.enable_2fa"
    TERMINAL_DISABLE_2FA = "terminal.disable_2fa"
    TERMINAL_SCAN_VULNERABILITIES = "terminal.scan_vulnerabilities"
    TERMINAL_APPLY_SECURITY_PATCH = "terminal.apply_security_patch"
    TERMINAL_ISOLATE = "terminal.isolate"
    TERMINAL_QUARANTINE = "terminal.quarantine"
    TERMINAL_RELEASE_QUARANTINE = "terminal.release_quarantine"
    
    # =========================================================================
    # FLEET PERMISSIONS (60)
    # =========================================================================
    
    # Fleet View (15)
    FLEET_VIEW = "fleet.view"
    FLEET_VIEW_DETAILS = "fleet.view_details"
    FLEET_LIST = "fleet.list"
    FLEET_SEARCH = "fleet.search"
    FLEET_VIEW_TERMINALS = "fleet.view_terminals"
    FLEET_VIEW_STATS = "fleet.view_stats"
    FLEET_VIEW_HEALTH = "fleet.view_health"
    FLEET_VIEW_UTILIZATION = "fleet.view_utilization"
    FLEET_VIEW_COSTS = "fleet.view_costs"
    FLEET_VIEW_POLICIES = "fleet.view_policies"
    FLEET_VIEW_SCHEDULES = "fleet.view_schedules"
    FLEET_VIEW_TAGS = "fleet.view_tags"
    FLEET_VIEW_HIERARCHY = "fleet.view_hierarchy"
    FLEET_VIEW_PERMISSIONS = "fleet.view_permissions"
    FLEET_VIEW_AUDIT_LOG = "fleet.view_audit_log"
    
    # Fleet Management (20)
    FLEET_CREATE = "fleet.create"
    FLEET_UPDATE = "fleet.update"
    FLEET_UPDATE_CONFIG = "fleet.update_config"
    FLEET_DELETE = "fleet.delete"
    FLEET_ARCHIVE = "fleet.archive"
    FLEET_RESTORE = "fleet.restore"
    FLEET_CLONE = "fleet.clone"
    FLEET_MERGE = "fleet.merge"
    FLEET_SPLIT = "fleet.split"
    FLEET_RENAME = "fleet.rename"
    FLEET_ADD_TERMINAL = "fleet.add_terminal"
    FLEET_REMOVE_TERMINAL = "fleet.remove_terminal"
    FLEET_BULK_ADD = "fleet.bulk_add"
    FLEET_BULK_REMOVE = "fleet.bulk_remove"
    FLEET_SET_POLICY = "fleet.set_policy"
    FLEET_APPLY_TEMPLATE = "fleet.apply_template"
    FLEET_SET_MAINTENANCE_WINDOW = "fleet.set_maintenance_window"
    FLEET_CONFIGURE_AUTOSCALING = "fleet.configure_autoscaling"
    FLEET_SET_QUOTA = "fleet.set_quota"
    FLEET_SET_BUDGET = "fleet.set_budget"
    
    # Fleet Operations (15)
    FLEET_EXECUTE_COMMAND = "fleet.execute_command"
    FLEET_EXECUTE_SCRIPT = "fleet.execute_script"
    FLEET_EXECUTE_ROLLING = "fleet.execute_rolling"
    FLEET_EXECUTE_CANARY = "fleet.execute_canary"
    FLEET_EXECUTE_PARALLEL = "fleet.execute_parallel"
    FLEET_SCHEDULE_TASK = "fleet.schedule_task"
    FLEET_CANCEL_TASK = "fleet.cancel_task"
    FLEET_DEPLOY_SOFTWARE = "fleet.deploy_software"
    FLEET_ROLLBACK_DEPLOYMENT = "fleet.rollback_deployment"
    FLEET_UPDATE_SOFTWARE = "fleet.update_software"
    FLEET_PATCH_SECURITY = "fleet.patch_security"
    FLEET_COLLECT_LOGS = "fleet.collect_logs"
    FLEET_COLLECT_METRICS = "fleet.collect_metrics"
    FLEET_RUN_DIAGNOSTICS = "fleet.run_diagnostics"
    FLEET_BULK_ACTION = "fleet.bulk_action"
    
    # Fleet Automation (10)
    FLEET_CREATE_WORKFLOW = "fleet.create_workflow"
    FLEET_UPDATE_WORKFLOW = "fleet.update_workflow"
    FLEET_DELETE_WORKFLOW = "fleet.delete_workflow"
    FLEET_ENABLE_AUTOMATION = "fleet.enable_automation"
    FLEET_DISABLE_AUTOMATION = "fleet.disable_automation"
    FLEET_CREATE_RULE = "fleet.create_rule"
    FLEET_UPDATE_RULE = "fleet.update_rule"
    FLEET_DELETE_RULE = "fleet.delete_rule"
    FLEET_CONFIGURE_WEBHOOKS = "fleet.configure_webhooks"
    FLEET_MANAGE_INTEGRATIONS = "fleet.manage_integrations"
    
    # =========================================================================
    # USER & ROLE PERMISSIONS (50)
    # =========================================================================
    
    # User View (10)
    USER_VIEW = "user.view"
    USER_VIEW_DETAILS = "user.view_details"
    USER_VIEW_PROFILE = "user.view_profile"
    USER_LIST = "user.list"
    USER_SEARCH = "user.search"
    USER_VIEW_SESSIONS = "user.view_sessions"
    USER_VIEW_ACTIVITY = "user.view_activity"
    USER_VIEW_PERMISSIONS = "user.view_permissions"
    USER_VIEW_GROUPS = "user.view_groups"
    USER_EXPORT_LIST = "user.export_list"
    
    # User Management (15)
    USER_CREATE = "user.create"
    USER_CREATE_BULK = "user.create_bulk"
    USER_INVITE = "user.invite"
    USER_UPDATE = "user.update"
    USER_UPDATE_PROFILE = "user.update_profile"
    USER_DELETE = "user.delete"
    USER_DELETE_BULK = "user.delete_bulk"
    USER_SUSPEND = "user.suspend"
    USER_UNSUSPEND = "user.unsuspend"
    USER_RESET_PASSWORD = "user.reset_password"
    USER_FORCE_PASSWORD_CHANGE = "user.force_password_change"
    USER_SET_ROLE = "user.set_role"
    USER_ADD_TO_GROUP = "user.add_to_group"
    USER_REMOVE_FROM_GROUP = "user.remove_from_group"
    USER_IMPERSONATE = "user.impersonate"
    
    # Role View (5)
    ROLE_VIEW = "role.view"
    ROLE_VIEW_DETAILS = "role.view_details"
    ROLE_LIST = "role.list"
    ROLE_VIEW_PERMISSIONS = "role.view_permissions"
    ROLE_VIEW_USERS = "role.view_users"
    
    # Role Management (10)
    ROLE_CREATE = "role.create"
    ROLE_UPDATE = "role.update"
    ROLE_DELETE = "role.delete"
    ROLE_CLONE = "role.clone"
    ROLE_ADD_PERMISSION = "role.add_permission"
    ROLE_REMOVE_PERMISSION = "role.remove_permission"
    ROLE_SET_HIERARCHY = "role.set_hierarchy"
    ROLE_ASSIGN_TO_USER = "role.assign_to_user"
    ROLE_REMOVE_FROM_USER = "role.remove_from_user"
    ROLE_SET_DEFAULT = "role.set_default"
    
    # Group Management (10)
    GROUP_CREATE = "group.create"
    GROUP_UPDATE = "group.update"
    GROUP_DELETE = "group.delete"
    GROUP_ADD_USER = "group.add_user"
    GROUP_REMOVE_USER = "group.remove_user"
    GROUP_SET_PERMISSIONS = "group.set_permissions"
    GROUP_VIEW = "group.view"
    GROUP_LIST = "group.list"
    GROUP_SEARCH = "group.search"
    GROUP_SET_POLICY = "group.set_policy"
    
    # =========================================================================
    # SECURITY PERMISSIONS (60)
    # =========================================================================
    
    # Authentication Policy (15)
    SECURITY_VIEW_AUTH_POLICY = "security.view_auth_policy"
    SECURITY_UPDATE_AUTH_POLICY = "security.update_auth_policy"
    SECURITY_CONFIGURE_SSO = "security.configure_sso"
    SECURITY_CONFIGURE_SAML = "security.configure_saml"
    SECURITY_CONFIGURE_OIDC = "security.configure_oidc"
    SECURITY_CONFIGURE_LDAP = "security.configure_ldap"
    SECURITY_CONFIGURE_MFA = "security.configure_mfa"
    SECURITY_SET_MFA_POLICY = "security.set_mfa_policy"
    SECURITY_CONFIGURE_PASSWORD_POLICY = "security.configure_password_policy"
    SECURITY_CONFIGURE_SESSION_POLICY = "security.configure_session_policy"
    SECURITY_CONFIGURE_IP_ALLOWLIST = "security.configure_ip_allowlist"
    SECURITY_CONFIGURE_DEVICE_TRUST = "security.configure_device_trust"
    SECURITY_CONFIGURE_RISK_ENGINE = "security.configure_risk_engine"
    SECURITY_CONFIGURE_BREACHED_PASSWORD = "security.configure_breached_password"
    SECURITY_CONFIGURE_CAPTCHA = "security.configure_captcha"
    
    # Access Control (15)
    SECURITY_VIEW_ACL = "security.view_acl"
    SECURITY_CREATE_ACL = "security.create_acl"
    SECURITY_UPDATE_ACL = "security.update_acl"
    SECURITY_DELETE_ACL = "security.delete_acl"
    SECURITY_VIEW_POLICIES = "security.view_policies"
    SECURITY_CREATE_POLICY = "security.create_policy"
    SECURITY_UPDATE_POLICY = "security.update_policy"
    SECURITY_DELETE_POLICY = "security.delete_policy"
    SECURITY_CONFIGURE_ABAC = "security.configure_abac"
    SECURITY_CONFIGURE_RBAC = "security.configure_rbac"
    SECURITY_CONFIGURE_REBAC = "security.configure_rebac"
    SECURITY_VIEW_PERMISSION_GRAPH = "security.view_permission_graph"
    SECURITY_ANALYZE_PERMISSIONS = "security.analyze_permissions"
    SECURITY_SIMULATE_ACCESS = "security.simulate_access"
    SECURITY_AUDIT_PERMISSIONS = "security.audit_permissions"
    
    # Secrets & Credentials (15)
    SECURITY_VIEW_SECRETS = "security.view_secrets"
    SECURITY_CREATE_SECRET = "security.create_secret"
    SECURITY_UPDATE_SECRET = "security.update_secret"
    SECURITY_DELETE_SECRET = "security.delete_secret"
    SECURITY_ROTATE_SECRET = "security.rotate_secret"
    SECURITY_VIEW_API_KEYS = "security.view_api_keys"
    SECURITY_CREATE_API_KEY = "security.create_api_key"
    SECURITY_REVOKE_API_KEY = "security.revoke_api_key"
    SECURITY_VIEW_CERTIFICATES = "security.view_certificates"
    SECURITY_ISSUE_CERTIFICATE = "security.issue_certificate"
    SECURITY_REVOKE_CERTIFICATE = "security.revoke_certificate"
    SECURITY_MANAGE_CA = "security.manage_ca"
    SECURITY_VIEW_CREDENTIALS = "security.view_credentials"
    SECURITY_ROTATE_CREDENTIALS = "security.rotate_credentials"
    SECURITY_VAULT_ACCESS = "security.vault_access"
    
    # Threat & Compliance (15)
    SECURITY_VIEW_ALERTS = "security.view_alerts"
    SECURITY_MANAGE_ALERTS = "security.manage_alerts"
    SECURITY_VIEW_INCIDENTS = "security.view_incidents"
    SECURITY_CREATE_INCIDENT = "security.create_incident"
    SECURITY_UPDATE_INCIDENT = "security.update_incident"
    SECURITY_CLOSE_INCIDENT = "security.close_incident"
    SECURITY_RUN_SCAN = "security.run_scan"
    SECURITY_VIEW_SCAN_RESULTS = "security.view_scan_results"
    SECURITY_APPLY_REMEDIATION = "security.apply_remediation"
    SECURITY_VIEW_COMPLIANCE = "security.view_compliance"
    SECURITY_GENERATE_COMPLIANCE_REPORT = "security.generate_compliance_report"
    SECURITY_CONFIGURE_DLP = "security.configure_dlp"
    SECURITY_CONFIGURE_WAF = "security.configure_waf"
    SECURITY_CONFIGURE_IDS = "security.configure_ids"
    SECURITY_VIEW_THREAT_INTEL = "security.view_threat_intel"
    
    # =========================================================================
    # AUDIT & LOGGING PERMISSIONS (30)
    # =========================================================================
    
    # Audit Logs (15)
    AUDIT_VIEW_LOGS = "audit.view_logs"
    AUDIT_VIEW_AUTH_LOGS = "audit.view_auth_logs"
    AUDIT_VIEW_ACCESS_LOGS = "audit.view_access_logs"
    AUDIT_VIEW_ADMIN_LOGS = "audit.view_admin_logs"
    AUDIT_VIEW_SYSTEM_LOGS = "audit.view_system_logs"
    AUDIT_VIEW_SECURITY_LOGS = "audit.view_security_logs"
    AUDIT_SEARCH_LOGS = "audit.search_logs"
    AUDIT_FILTER_LOGS = "audit.filter_logs"
    AUDIT_EXPORT_LOGS = "audit.export_logs"
    AUDIT_STREAM_LOGS = "audit.stream_logs"
    AUDIT_ARCHIVE_LOGS = "audit.archive_logs"
    AUDIT_PURGE_LOGS = "audit.purge_logs"
    AUDIT_CONFIGURE_RETENTION = "audit.configure_retention"
    AUDIT_VIEW_ANOMALIES = "audit.view_anomalies"
    AUDIT_RUN_FORENSICS = "audit.run_forensics"
    
    # Session Recording (10)
    AUDIT_VIEW_SESSION_RECORDINGS = "audit.view_session_recordings"
    AUDIT_PLAY_RECORDING = "audit.play_recording"
    AUDIT_DOWNLOAD_RECORDING = "audit.download_recording"
    AUDIT_SEARCH_RECORDINGS = "audit.search_recordings"
    AUDIT_DELETE_RECORDING = "audit.delete_recording"
    AUDIT_CONFIGURE_RECORDING = "audit.configure_recording"
    AUDIT_ENABLE_RECORDING = "audit.enable_recording"
    AUDIT_DISABLE_RECORDING = "audit.disable_recording"
    AUDIT_SET_RECORDING_POLICY = "audit.set_recording_policy"
    AUDIT_VIEW_LIVE_SESSIONS = "audit.view_live_sessions"
    
    # SIEM Integration (5)
    AUDIT_CONFIGURE_SIEM = "audit.configure_siem"
    AUDIT_SEND_TO_SIEM = "audit.send_to_siem"
    AUDIT_CONFIGURE_SPLUNK = "audit.configure_splunk"
    AUDIT_CONFIGURE_DATADOG = "audit.configure_datadog"
    AUDIT_CONFIGURE_ELASTIC = "audit.configure_elastic"
    
    # =========================================================================
    # INTEGRATION PERMISSIONS (40)
    # =========================================================================
    
    # Webhooks (10)
    INTEGRATION_VIEW_WEBHOOKS = "integration.view_webhooks"
    INTEGRATION_CREATE_WEBHOOK = "integration.create_webhook"
    INTEGRATION_UPDATE_WEBHOOK = "integration.update_webhook"
    INTEGRATION_DELETE_WEBHOOK = "integration.delete_webhook"
    INTEGRATION_TEST_WEBHOOK = "integration.test_webhook"
    INTEGRATION_ENABLE_WEBHOOK = "integration.enable_webhook"
    INTEGRATION_DISABLE_WEBHOOK = "integration.disable_webhook"
    INTEGRATION_VIEW_WEBHOOK_LOGS = "integration.view_webhook_logs"
    INTEGRATION_REPLAY_WEBHOOK = "integration.replay_webhook"
    INTEGRATION_CONFIGURE_WEBHOOK_AUTH = "integration.configure_webhook_auth"
    
    # API Management (15)
    INTEGRATION_VIEW_API_CONFIG = "integration.view_api_config"
    INTEGRATION_CREATE_API_ENDPOINT = "integration.create_api_endpoint"
    INTEGRATION_UPDATE_API_ENDPOINT = "integration.update_api_endpoint"
    INTEGRATION_DELETE_API_ENDPOINT = "integration.delete_api_endpoint"
    INTEGRATION_VIEW_API_KEYS = "integration.view_api_keys"
    INTEGRATION_GENERATE_API_KEY = "integration.generate_api_key"
    INTEGRATION_REVOKE_API_KEY = "integration.revoke_api_key"
    INTEGRATION_CONFIGURE_RATE_LIMIT = "integration.configure_rate_limit"
    INTEGRATION_CONFIGURE_CORS = "integration.configure_cors"
    INTEGRATION_VIEW_API_USAGE = "integration.view_api_usage"
    INTEGRATION_VIEW_API_DOCS = "integration.view_api_docs"
    INTEGRATION_MANAGE_API_VERSION = "integration.manage_api_version"
    INTEGRATION_DEPLOY_API = "integration.deploy_api"
    INTEGRATION_DEPRECATED_API = "integration.deprecated_api"
    INTEGRATION_CONFIGURE_GRAPHQL = "integration.configure_graphql"
    
    # Third-party Integrations (15)
    INTEGRATION_CONFIGURE_SLACK = "integration.configure_slack"
    INTEGRATION_CONFIGURE_TEAMS = "integration.configure_teams"
    INTEGRATION_CONFIGURE_PAGERDUTY = "integration.configure_pagerduty"
    INTEGRATION_CONFIGURE_OPSGENIE = "integration.configure_opsgenie"
    INTEGRATION_CONFIGURE_JIRA = "integration.configure_jira"
    INTEGRATION_CONFIGURE_SERVICENOW = "integration.configure_servicenow"
    INTEGRATION_CONFIGURE_GITHUB = "integration.configure_github"
    INTEGRATION_CONFIGURE_GITLAB = "integration.configure_gitlab"
    INTEGRATION_CONFIGURE_TERRAFORM = "integration.configure_terraform"
    INTEGRATION_CONFIGURE_ANSIBLE = "integration.configure_ansible"
    INTEGRATION_CONFIGURE_CHEF = "integration.configure_chef"
    INTEGRATION_CONFIGURE_PUPPET = "integration.configure_puppet"
    INTEGRATION_CONFIGURE_VAULT = "integration.configure_vault"
    INTEGRATION_CONFIGURE_AWS = "integration.configure_aws"
    INTEGRATION_CONFIGURE_AZURE = "integration.configure_azure"
    INTEGRATION_CONFIGURE_GCP = "integration.configure_gcp"
    
    # =========================================================================
    # BILLING & USAGE PERMISSIONS (25)
    # =========================================================================
    
    # Billing View (10)
    BILLING_VIEW_INVOICES = "billing.view_invoices"
    BILLING_VIEW_CURRENT_USAGE = "billing.view_current_usage"
    BILLING_VIEW_USAGE_HISTORY = "billing.view_usage_history"
    BILLING_VIEW_COST_BREAKDOWN = "billing.view_cost_breakdown"
    BILLING_VIEW_PAYMENT_METHODS = "billing.view_payment_methods"
    BILLING_VIEW_SUBSCRIPTION = "billing.view_subscription"
    BILLING_VIEW_PLANS = "billing.view_plans"
    BILLING_VIEW_CREDITS = "billing.view_credits"
    BILLING_VIEW_QUOTAS = "billing.view_quotas"
    BILLING_VIEW_FORECAST = "billing.view_forecast"
    
    # Billing Management (10)
    BILLING_UPDATE_PAYMENT_METHOD = "billing.update_payment_method"
    BILLING_DELETE_PAYMENT_METHOD = "billing.delete_payment_method"
    BILLING_CHANGE_PLAN = "billing.change_plan"
    BILLING_CANCEL_SUBSCRIPTION = "billing.cancel_subscription"
    BILLING_REACTIVATE_SUBSCRIPTION = "billing.reactivate_subscription"
    BILLING_APPLY_COUPON = "billing.apply_coupon"
    BILLING_PURCHASE_CREDITS = "billing.purchase_credits"
    BILLING_REQUEST_REFUND = "billing.request_refund"
    BILLING_DOWNLOAD_INVOICE = "billing.download_invoice"
    BILLING_CONFIGURE_BILLING_ALERTS = "billing.configure_billing_alerts"
    
    # Usage Management (5)
    BILLING_SET_USAGE_LIMITS = "billing.set_usage_limits"
    BILLING_CONFIGURE_BUDGET = "billing.configure_budget"
    BILLING_ALLOCATE_BUDGET = "billing.allocate_budget"
    BILLING_VIEW_ALLOCATIONS = "billing.view_allocations"
    BILLING_CONFIGURE_SHOWBACK = "billing.configure_showback"
    
    # =========================================================================
    # SYSTEM & ADMIN PERMISSIONS (35)
    # =========================================================================
    
    # System Configuration (15)
    SYSTEM_VIEW_CONFIG = "system.view_config"
    SYSTEM_UPDATE_CONFIG = "system.update_config"
    SYSTEM_VIEW_STATUS = "system.view_status"
    SYSTEM_VIEW_HEALTH = "system.view_health"
    SYSTEM_VIEW_METRICS = "system.view_metrics"
    SYSTEM_VIEW_BACKUPS = "system.view_backups"
    SYSTEM_CREATE_BACKUP = "system.create_backup"
    SYSTEM_RESTORE_BACKUP = "system.restore_backup"
    SYSTEM_CONFIGURE_MAINTENANCE = "system.configure_maintenance"
    SYSTEM_TRIGGER_MAINTENANCE = "system.trigger_maintenance"
    SYSTEM_VIEW_NODES = "system.view_nodes"
    SYSTEM_MANAGE_NODES = "system.manage_nodes"
    SYSTEM_VIEW_LICENSE = "system.view_license"
    SYSTEM_UPDATE_LICENSE = "system.update_license"
    SYSTEM_CONFIGURE_HA = "system.configure_ha"
    
    # Tenant Administration (10)
    SYSTEM_CREATE_TENANT = "system.create_tenant"
    SYSTEM_UPDATE_TENANT = "system.update_tenant"
    SYSTEM_DELETE_TENANT = "system.delete_tenant"
    SYSTEM_SUSPEND_TENANT = "system.suspend_tenant"
    SYSTEM_VIEW_TENANTS = "system.view_tenants"
    SYSTEM_MANAGE_TENANT_QUOTAS = "system.manage_tenant_quotas"
    SYSTEM_IMPERSONATE_TENANT = "system.impersonate_tenant"
    SYSTEM_MIGRATE_TENANT = "system.migrate_tenant"
    SYSTEM_CLONE_TENANT = "system.clone_tenant"
    SYSTEM_CONFIGURE_TENANT_ISOLATION = "system.configure_tenant_isolation"
    
    # Platform Operations (10)
    SYSTEM_DEPLOY_UPDATE = "system.deploy_update"
    SYSTEM_ROLLBACK_UPDATE = "system.rollback_update"
    SYSTEM_VIEW_JOBS = "system.view_jobs"
    SYSTEM_MANAGE_JOBS = "system.manage_jobs"
    SYSTEM_VIEW_QUEUES = "system.view_queues"
    SYSTEM_MANAGE_QUEUES = "system.manage_queues"
    SYSTEM_PURGE_CACHE = "system.purge_cache"
    SYSTEM_INVALIDATE_CACHE = "system.invalidate_cache"
    SYSTEM_RUN_DIAGNOSTICS = "system.run_diagnostics"
    SYSTEM_ACCESS_SHELL = "system.access_shell"
    
    # =========================================================================
    # WORKFLOW & AUTOMATION PERMISSIONS (30)
    # =========================================================================
    
    # Workflow Management (15)
    WORKFLOW_VIEW = "workflow.view"
    WORKFLOW_CREATE = "workflow.create"
    WORKFLOW_UPDATE = "workflow.update"
    WORKFLOW_DELETE = "workflow.delete"
    WORKFLOW_CLONE = "workflow.clone"
    WORKFLOW_ENABLE = "workflow.enable"
    WORKFLOW_DISABLE = "workflow.disable"
    WORKFLOW_EXECUTE = "workflow.execute"
    WORKFLOW_SCHEDULE = "workflow.schedule"
    WORKFLOW_CANCEL = "workflow.cancel"
    WORKFLOW_VIEW_RUNS = "workflow.view_runs"
    WORKFLOW_VIEW_LOGS = "workflow.view_logs"
    WORKFLOW_EXPORT = "workflow.export"
    WORKFLOW_IMPORT = "workflow.import"
    WORKFLOW_SET_TRIGGERS = "workflow.set_triggers"
    
    # Pipeline Management (10)
    PIPELINE_VIEW = "pipeline.view"
    PIPELINE_CREATE = "pipeline.create"
    PIPELINE_UPDATE = "pipeline.update"
    PIPELINE_DELETE = "pipeline.delete"
    PIPELINE_EXECUTE = "pipeline.execute"
    PIPELINE_APPROVE = "pipeline.approve"
    PIPELINE_REJECT = "pipeline.reject"
    PIPELINE_VIEW_RUNS = "pipeline.view_runs"
    PIPELINE_CONFIGURE_STAGES = "pipeline.configure_stages"
    PIPELINE_SET_APPROVERS = "pipeline.set_approvers"
    
    # Job Management (5)
    JOB_VIEW = "job.view"
    JOB_CREATE = "job.create"
    JOB_CANCEL = "job.cancel"
    JOB_RETRY = "job.retry"
    JOB_VIEW_LOGS = "job.view_logs"
    
    # =========================================================================
    # MONITORING & ALERTING PERMISSIONS (25)
    # =========================================================================
    
    # Dashboards (10)
    MONITORING_VIEW_DASHBOARDS = "monitoring.view_dashboards"
    MONITORING_CREATE_DASHBOARD = "monitoring.create_dashboard"
    MONITORING_UPDATE_DASHBOARD = "monitoring.update_dashboard"
    MONITORING_DELETE_DASHBOARD = "monitoring.delete_dashboard"
    MONITORING_SHARE_DASHBOARD = "monitoring.share_dashboard"
    MONITORING_SET_DEFAULT_DASHBOARD = "monitoring.set_default_dashboard"
    MONITORING_VIEW_WIDGETS = "monitoring.view_widgets"
    MONITORING_CREATE_WIDGET = "monitoring.create_widget"
    MONITORING_CONFIGURE_WIDGET = "monitoring.configure_widget"
    MONITORING_EXPORT_DASHBOARD = "monitoring.export_dashboard"
    
    # Metrics & Alerts (15)
    MONITORING_VIEW_METRICS = "monitoring.view_metrics"
    MONITORING_QUERY_METRICS = "monitoring.query_metrics"
    MONITORING_CREATE_METRIC = "monitoring.create_metric"
    MONITORING_VIEW_ALERTS = "monitoring.view_alerts"
    MONITORING_CREATE_ALERT = "monitoring.create_alert"
    MONITORING_UPDATE_ALERT = "monitoring.update_alert"
    MONITORING_DELETE_ALERT = "monitoring.delete_alert"
    MONITORING_ACKNOWLEDGE_ALERT = "monitoring.acknowledge_alert"
    MONITORING_SILENCE_ALERT = "monitoring.silence_alert"
    MONITORING_CONFIGURE_NOTIFICATIONS = "monitoring.configure_notifications"
    MONITORING_VIEW_EVENTS = "monitoring.view_events"
    MONITORING_CREATE_SILENCE = "monitoring.create_silence"
    MONITORING_MANAGE_MAINTENANCE = "monitoring.manage_maintenance"
    MONITORING_CONFIGURE_SLO = "monitoring.configure_slo"
    MONITORING_VIEW_SLO = "monitoring.view_slo"
    
    # =========================================================================
    # NOTIFICATION PERMISSIONS (15)
    # =========================================================================
    NOTIFICATION_VIEW_SETTINGS = "notification.view_settings"
    NOTIFICATION_UPDATE_SETTINGS = "notification.update_settings"
    NOTIFICATION_VIEW_TEMPLATES = "notification.view_templates"
    NOTIFICATION_CREATE_TEMPLATE = "notification.create_template"
    NOTIFICATION_UPDATE_TEMPLATE = "notification.update_template"
    NOTIFICATION_DELETE_TEMPLATE = "notification.delete_template"
    NOTIFICATION_SEND_TEST = "notification.send_test"
    NOTIFICATION_VIEW_HISTORY = "notification.view_history"
    NOTIFICATION_CONFIGURE_CHANNELS = "notification.configure_channels"
    NOTIFICATION_CONFIGURE_ROUTING = "notification.configure_routing"
    NOTIFICATION_VIEW_SUBSCRIPTIONS = "notification.view_subscriptions"
    NOTIFICATION_SUBSCRIBE = "notification.subscribe"
    NOTIFICATION_UNSUBSCRIBE = "notification.unsubscribe"
    NOTIFICATION_MANAGE_DIGESTS = "notification.manage_digests"
    NOTIFICATION_CONFIGURE_DO_NOT_DISTURB = "notification.configure_do_not_disturb"
    
    # =========================================================================
    # REPORT & ANALYTICS PERMISSIONS (20)
    # =========================================================================
    REPORT_VIEW = "report.view"
    REPORT_CREATE = "report.create"
    REPORT_UPDATE = "report.update"
    REPORT_DELETE = "report.delete"
    REPORT_SCHEDULE = "report.schedule"
    REPORT_RUN = "report.run"
    REPORT_EXPORT = "report.export"
    REPORT_SHARE = "report.share"
    REPORT_VIEW_ANALYTICS = "report.view_analytics"
    REPORT_CREATE_CUSTOM = "report.create_custom"
    REPORT_CONFIGURE_DASHBOARD = "report.configure_dashboard"
    REPORT_VIEW_USAGE_ANALYTICS = "report.view_usage_analytics"
    REPORT_VIEW_PERFORMANCE = "report.view_performance"
    REPORT_VIEW_TRENDS = "report.view_trends"
    REPORT_VIEW_FORECASTS = "report.view_forecasts"
    REPORT_CREATE_ALERTS = "report.create_alerts"
    REPORT_CONFIGURE_DRILLDOWN = "report.configure_drilldown"
    REPORT_EMBED = "report.embed"
    REPORT_SUBSCRIBE = "report.subscribe"
    REPORT_GENERATE_PDF = "report.generate_pdf"


# ============================================================================
# Permission Utilities
# ============================================================================

class PermissionRegistry:
    """Registry for permission metadata and lookups."""
    
    _by_category: Dict[PermissionCategory, Set[Permission]] = {}
    _by_resource: Dict[str, Set[Permission]] = {}
    
    @classmethod
    def initialize(cls) -> None:
        """Build permission indexes."""
        cls._by_category = {cat: set() for cat in PermissionCategory}
        cls._by_resource = {}
        
        for perm in Permission:
            # Categorize by resource prefix
            resource = perm.value.split(".")[0]
            
            # Map to category
            category = cls._get_category_for_resource(resource)
            cls._by_category[category].add(perm)
            
            # Index by resource
            if resource not in cls._by_resource:
                cls._by_resource[resource] = set()
            cls._by_resource[resource].add(perm)
    
    @classmethod
    def _get_category_for_resource(cls, resource: str) -> PermissionCategory:
        """Determine category from resource name."""
        mapping = {
            "terminal": PermissionCategory.TERMINAL,
            "fleet": PermissionCategory.FLEET,
            "user": PermissionCategory.USER,
            "role": PermissionCategory.ROLE,
            "group": PermissionCategory.USER,
            "security": PermissionCategory.SECURITY,
            "audit": PermissionCategory.AUDIT,
            "integration": PermissionCategory.INTEGRATION,
            "billing": PermissionCategory.BILLING,
            "system": PermissionCategory.SYSTEM,
            "workflow": PermissionCategory.WORKFLOW,
            "pipeline": PermissionCategory.WORKFLOW,
            "job": PermissionCategory.WORKFLOW,
            "monitoring": PermissionCategory.MONITORING,
            "notification": PermissionCategory.NOTIFICATION,
            "report": PermissionCategory.REPORT,
        }
        return mapping.get(resource, PermissionCategory.SYSTEM)
    
    @classmethod
    def get_by_category(cls, category: PermissionCategory) -> Set[Permission]:
        """Get all permissions in a category."""
        return cls._by_category.get(category, set())
    
    @classmethod
    def get_by_resource(cls, resource: str) -> Set[Permission]:
        """Get all permissions for a resource."""
        return cls._by_resource.get(resource, set())
    
    @classmethod
    def search(cls, query: str) -> Set[Permission]:
        """Search permissions by partial match."""
        query = query.lower()
        return {p for p in Permission if query in p.value.lower()}
    
    @classmethod
    def count(cls) -> int:
        """Total number of permissions."""
        return len(Permission)


# Initialize registry
PermissionRegistry.initialize()


# ============================================================================
# Role Model with Hierarchical Permissions
# ============================================================================

@dataclass
class Role:
    """
    Role definition with hierarchical permissions.
    
    Roles can inherit from parent roles, forming a permission hierarchy.
    """
    
    id: str
    name: str
    description: str
    tenant_id: Optional[str] = None  # None = system role
    
    # Direct permissions assigned to this role
    direct_permissions: Set[Permission] = field(default_factory=set)
    
    # Parent roles (inheritance)
    parent_roles: List[str] = field(default_factory=list)
    
    # Metadata
    is_system_role: bool = False
    is_default: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # Constraints
    max_session_duration: int = 28800  # 8 hours
    requires_mfa: bool = False
    allowed_ip_ranges: Optional[List[str]] = None
    time_restrictions: Optional[Dict[str, Any]] = None
    
    def get_effective_permissions(
        self, 
        role_registry: Dict[str, Role]
    ) -> FrozenSet[Permission]:
        """
        Get all effective permissions including inherited ones.
        
        Uses depth-first traversal to collect permissions from parent roles.
        """
        effective: Set[Permission] = set(self.direct_permissions)
        visited: Set[str] = {self.id}
        
        def collect_from_parent(parent_id: str) -> None:
            if parent_id in visited:
                return
            visited.add(parent_id)
            
            parent = role_registry.get(parent_id)
            if not parent:
                return
            
            effective.update(parent.direct_permissions)
            
            for grandparent_id in parent.parent_roles:
                collect_from_parent(grandparent_id)
        
        for parent_id in self.parent_roles:
            collect_from_parent(parent_id)
        
        return frozenset(effective)
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if role has a specific permission directly."""
        return permission in self.direct_permissions
    
    def add_permission(self, permission: Permission) -> None:
        """Add a permission to this role."""
        self.direct_permissions.add(permission)
    
    def remove_permission(self, permission: Permission) -> None:
        """Remove a permission from this role."""
        self.direct_permissions.discard(permission)
    
    def to_dict(self, include_permissions: bool = True) -> Dict[str, Any]:
        """Convert role to dictionary."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tenant_id": self.tenant_id,
            "parent_roles": self.parent_roles,
            "is_system_role": self.is_system_role,
            "is_default": self.is_default,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "max_session_duration": self.max_session_duration,
            "requires_mfa": self.requires_mfa,
        }
        
        if include_permissions:
            result["direct_permissions"] = [p.value for p in self.direct_permissions]
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Role:
        """Create role from dictionary."""
        perms = data.get("direct_permissions", [])
        if perms and isinstance(perms[0], str):
            perms = {Permission(p) for p in perms if p in Permission._value2member_map_}
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            tenant_id=data.get("tenant_id"),
            direct_permissions=perms,
            parent_roles=data.get("parent_roles", []),
            is_system_role=data.get("is_system_role", False),
            is_default=data.get("is_default", False),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            max_session_duration=data.get("max_session_duration", 28800),
            requires_mfa=data.get("requires_mfa", False),
            allowed_ip_ranges=data.get("allowed_ip_ranges"),
            time_restrictions=data.get("time_restrictions"),
        )


# ============================================================================
# Predefined System Roles
# ============================================================================

class SystemRoles:
    """Predefined system roles with standard permission sets."""
    
    @staticmethod
    def create_super_admin() -> Role:
        """Super Administrator - full platform access."""
        return Role(
            id="super_admin",
            name="Super Administrator",
            description="Full access to all platform features across all tenants",
            is_system_role=True,
            direct_permissions=set(Permission),  # All permissions
            requires_mfa=True,
        )
    
    @staticmethod
    def create_tenant_admin() -> Role:
        """Tenant Administrator - full tenant access."""
        perms = {
            # Full fleet access
            p for p in Permission if p.value.startswith("fleet.")
        } | {
            # Full user management
            p for p in Permission if p.value.startswith("user.") or p.value.startswith("role.") or p.value.startswith("group.")
        } | {
            # Terminal access (except destructive)
            p for p in Permission 
            if p.value.startswith("terminal.") 
            and not p.value.endswith((".delete", ".delete_bulk", ".force_disconnect"))
        } | {
            # Security management
            Permission.SECURITY_VIEW_AUTH_POLICY,
            Permission.SECURITY_UPDATE_AUTH_POLICY,
            Permission.SECURITY_CONFIGURE_MFA,
            Permission.SECURITY_CONFIGURE_SSO,
            Permission.SECURITY_VIEW_ACL,
            Permission.SECURITY_CREATE_ACL,
            Permission.SECURITY_UPDATE_ACL,
            Permission.SECURITY_VIEW_POLICIES,
            Permission.SECURITY_CREATE_POLICY,
            Permission.SECURITY_VIEW_SECRETS,
            Permission.SECURITY_CREATE_SECRET,
            Permission.SECURITY_VIEW_API_KEYS,
            Permission.SECURITY_CREATE_API_KEY,
            Permission.SECURITY_VIEW_ALERTS,
            Permission.SECURITY_VIEW_INCIDENTS,
            Permission.SECURITY_CREATE_INCIDENT,
            # Audit
            Permission.AUDIT_VIEW_LOGS,
            Permission.AUDIT_SEARCH_LOGS,
            Permission.AUDIT_EXPORT_LOGS,
            Permission.AUDIT_VIEW_SESSION_RECORDINGS,
            # Billing
            Permission.BILLING_VIEW_INVOICES,
            Permission.BILLING_VIEW_CURRENT_USAGE,
            Permission.BILLING_VIEW_SUBSCRIPTION,
            Permission.BILLING_UPDATE_PAYMENT_METHOD,
            # Integrations
            Permission.INTEGRATION_VIEW_WEBHOOKS,
            Permission.INTEGRATION_CREATE_WEBHOOK,
            Permission.INTEGRATION_VIEW_API_CONFIG,
            # Monitoring
            Permission.MONITORING_VIEW_DASHBOARDS,
            Permission.MONITORING_CREATE_DASHBOARD,
            Permission.MONITORING_VIEW_METRICS,
            Permission.MONITORING_VIEW_ALERTS,
            Permission.MONITORING_CREATE_ALERT,
            # Reports
            Permission.REPORT_VIEW,
            Permission.REPORT_CREATE,
            Permission.REPORT_RUN,
            Permission.REPORT_EXPORT,
            Permission.REPORT_VIEW_ANALYTICS,
        }
        
        return Role(
            id="tenant_admin",
            name="Tenant Administrator",
            description="Full administrative access within a tenant",
            is_system_role=True,
            direct_permissions=perms,
            requires_mfa=True,
        )
    
    @staticmethod
    def create_analyst() -> Role:
        """Security Analyst - read and analyze access."""
        perms = {
            # Terminal read-only
            Permission.TERMINAL_VIEW,
            Permission.TERMINAL_VIEW_DETAILS,
            Permission.TERMINAL_LIST,
            Permission.TERMINAL_SEARCH,
            Permission.TERMINAL_VIEW_STATUS,
            Permission.TERMINAL_VIEW_HEALTH,
            Permission.TERMINAL_VIEW_METRICS,
            Permission.TERMINAL_VIEW_SESSIONS,
            Permission.TERMINAL_VIEW_TAGS,
            Permission.TERMINAL_VIEW_NETWORK,
            Permission.TERMINAL_VIEW_HARDWARE,
            # Connect for analysis (read-only commands)
            Permission.TERMINAL_CONNECT,
            Permission.TERMINAL_CONNECT_SSH,
            Permission.TERMINAL_EXECUTE_READ,
            Permission.TERMINAL_FILE_VIEW,
            Permission.TERMINAL_FILE_READ,
            Permission.TERMINAL_VIEW_ENV,
            Permission.TERMINAL_VIEW_SESSION_LOGS,
            Permission.TERMINAL_DOWNLOAD_SESSION_LOGS,
            # Fleet view
            Permission.FLEET_VIEW,
            Permission.FLEET_VIEW_DETAILS,
            Permission.FLEET_LIST,
            Permission.FLEET_VIEW_TERMINALS,
            Permission.FLEET_VIEW_STATS,
            Permission.FLEET_VIEW_HEALTH,
            # Security
            Permission.SECURITY_VIEW_ALERTS,
            Permission.SECURITY_VIEW_INCIDENTS,
            Permission.SECURITY_CREATE_INCIDENT,
            Permission.SECURITY_VIEW_SCAN_RESULTS,
            Permission.SECURITY_VIEW_COMPLIANCE,
            Permission.SECURITY_GENERATE_COMPLIANCE_REPORT,
            Permission.SECURITY_VIEW_THREAT_INTEL,
            # Audit
            Permission.AUDIT_VIEW_LOGS,
            Permission.AUDIT_VIEW_AUTH_LOGS,
            Permission.AUDIT_VIEW_ACCESS_LOGS,
            Permission.AUDIT_VIEW_SECURITY_LOGS,
            Permission.AUDIT_SEARCH_LOGS,
            Permission.AUDIT_VIEW_SESSION_RECORDINGS,
            Permission.AUDIT_PLAY_RECORDING,
            Permission.AUDIT_VIEW_ANOMALIES,
            Permission.AUDIT_RUN_FORENSICS,
            # Reports
            Permission.REPORT_VIEW,
            Permission.REPORT_RUN,
            Permission.REPORT_EXPORT,
            Permission.REPORT_VIEW_ANALYTICS,
            Permission.REPORT_VIEW_USAGE_ANALYTICS,
            Permission.REPORT_VIEW_PERFORMANCE,
            # Monitoring
            Permission.MONITORING_VIEW_DASHBOARDS,
            Permission.MONITORING_VIEW_METRICS,
            Permission.MONITORING_VIEW_ALERTS,
            Permission.MONITORING_ACKNOWLEDGE_ALERT,
            Permission.MONITORING_VIEW_EVENTS,
        }
        
        return Role(
            id="analyst",
            name="Security Analyst",
            description="Read and analyze access for security operations",
            is_system_role=True,
            direct_permissions=perms,
            requires_mfa=True,
        )
    
    @staticmethod
    def create_operator() -> Role:
        """Operations Engineer - execute commands and manage deployments."""
        perms = {
            # Terminal full access
            p for p in Permission 
            if p.value.startswith("terminal.")
            and not p.value.endswith((".delete", ".archive"))
        } | {
            # Fleet operations
            p for p in Permission
            if p.value.startswith("fleet.")
            and p.value not in {
                Permission.FLEET_DELETE.value,
                Permission.FLEET_SET_BUDGET.value,
            }
        } | {
            # Workflows
            Permission.WORKFLOW_VIEW,
            Permission.WORKFLOW_CREATE,
            Permission.WORKFLOW_EXECUTE,
            Permission.WORKFLOW_SCHEDULE,
            Permission.WORKFLOW_VIEW_RUNS,
            Permission.WORKFLOW_VIEW_LOGS,
            # Pipelines
            Permission.PIPELINE_VIEW,
            Permission.PIPELINE_EXECUTE,
            Permission.PIPELINE_VIEW_RUNS,
            # Jobs
            Permission.JOB_VIEW,
            Permission.JOB_CREATE,
            Permission.JOB_CANCEL,
            Permission.JOB_VIEW_LOGS,
            # Monitoring
            Permission.MONITORING_VIEW_DASHBOARDS,
            Permission.MONITORING_VIEW_METRICS,
            Permission.MONITORING_VIEW_ALERTS,
            Permission.MONITORING_ACKNOWLEDGE_ALERT,
            # Integrations
            Permission.INTEGRATION_VIEW_WEBHOOKS,
            Permission.INTEGRATION_VIEW_API_CONFIG,
        }
        
        return Role(
            id="operator",
            name="Operations Engineer",
            description="Execute commands, manage deployments, and operate terminals",
            is_system_role=True,
            direct_permissions=perms,
        )
    
    @staticmethod
    def create_viewer() -> Role:
        """Viewer - read-only access."""
        perms = {
            # Terminal read-only
            Permission.TERMINAL_VIEW,
            Permission.TERMINAL_VIEW_DETAILS,
            Permission.TERMINAL_LIST,
            Permission.TERMINAL_SEARCH,
            Permission.TERMINAL_VIEW_STATUS,
            Permission.TERMINAL_VIEW_HEALTH,
            Permission.TERMINAL_VIEW_TAGS,
            # Fleet read-only
            Permission.FLEET_VIEW,
            Permission.FLEET_VIEW_DETAILS,
            Permission.FLEET_LIST,
            Permission.FLEET_VIEW_TERMINALS,
            Permission.FLEET_VIEW_STATS,
            # Reports
            Permission.REPORT_VIEW,
            Permission.REPORT_VIEW_ANALYTICS,
        }
        
        return Role(
            id="viewer",
            name="Viewer",
            description="Read-only access to view resources",
            is_system_role=True,
            direct_permissions=perms,
        )
    
    @staticmethod
    def create_api_key_role() -> Role:
        """API Key - limited programmatic access."""
        perms = {
            Permission.TERMINAL_VIEW,
            Permission.TERMINAL_LIST,
            Permission.TERMINAL_CONNECT,
            Permission.TERMINAL_EXECUTE,
            Permission.TERMINAL_FILE_READ,
            Permission.FLEET_VIEW,
            Permission.FLEET_LIST,
            Permission.FLEET_EXECUTE_COMMAND,
        }
        
        return Role(
            id="api_key",
            name="API Access",
            description="Limited access for API integrations",
            is_system_role=True,
            direct_permissions=perms,
            max_session_duration=86400,  # 24 hours
        )
    
    @staticmethod
    def get_all_system_roles() -> List[Role]:
        """Get all predefined system roles."""
        return [
            SystemRoles.create_super_admin(),
            SystemRoles.create_tenant_admin(),
            SystemRoles.create_analyst(),
            SystemRoles.create_operator(),
            SystemRoles.create_viewer(),
            SystemRoles.create_api_key_role(),
        ]


# ============================================================================
# Access Control List (ACL)
# ============================================================================

@dataclass
class ResourceIdentifier:
    """Identifies a resource for ACL checks."""
    resource_type: str  # terminal, fleet, user, etc.
    resource_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    def matches(self, pattern: str) -> bool:
        """Check if this resource matches a pattern."""
        # Pattern format: "type:id" or "type:*" or "*"
        parts = pattern.split(":")
        if len(parts) == 1:
            return self.resource_type == parts[0] or parts[0] == "*"
        
        type_pattern, id_pattern = parts[0], parts[1]
        
        if type_pattern != "*" and self.resource_type != type_pattern:
            return False
        
        if id_pattern != "*" and self.resource_id != id_pattern:
            return False
        
        return True
    
    def __str__(self) -> str:
        if self.resource_id:
            return f"{self.resource_type}:{self.resource_id}"
        return self.resource_type


@dataclass
class ACLEntry:
    """Single ACL entry defining access rules."""
    
    # Who
    principal_type: str  # user, role, group
    principal_id: str
    
    # What
    resource_pattern: str  # e.g., "terminal:*", "fleet:prod"
    permissions: Set[Permission]
    
    # Conditions
    conditions: Optional[Dict[str, Any]] = None  # IP, time, etc.
    
    # Effect
    effect: str = "allow"  # allow, deny
    
    # Metadata
    priority: int = 0  # Higher = evaluated first
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    
    def applies_to(
        self, 
        principal_type: str, 
        principal_id: str,
        resource: ResourceIdentifier
    ) -> bool:
        """Check if this entry applies to given principal and resource."""
        if self.principal_type != principal_type:
            return False
        if self.principal_id != principal_id and self.principal_id != "*":
            return False
        return resource.matches(self.resource_pattern)
    
    def check_conditions(self, context: Dict[str, Any]) -> bool:
        """Evaluate conditions against context."""
        if not self.conditions:
            return True
        
        # Check IP range
        if "ip_range" in self.conditions:
            client_ip = context.get("client_ip")
            # IP range check implementation
            pass
        
        # Check time restrictions
        if "time_of_day" in self.conditions:
            # Time check implementation
            pass
        
        # Check MFA
        if self.conditions.get("requires_mfa"):
            if not context.get("mfa_verified"):
                return False
        
        return True


class AccessControlList:
    """
    Resource-based access control list.
    
    Evaluates permissions based on:
    1. Direct role permissions
    2. Resource-specific ACL entries
    3. Inheritance and hierarchy
    """
    
    def __init__(self):
        self._entries: List[ACLEntry] = []
        self._role_registry: Dict[str, Role] = {}
    
    def add_entry(self, entry: ACLEntry) -> None:
        """Add an ACL entry."""
        self._entries.append(entry)
        # Sort by priority (descending)
        self._entries.sort(key=lambda e: e.priority, reverse=True)
    
    def remove_entry(self, entry_id: str) -> bool:
        """Remove an ACL entry by ID."""
        # Implementation would track entry IDs
        return False
    
    def register_role(self, role: Role) -> None:
        """Register a role for permission evaluation."""
        self._role_registry[role.id] = role
    
    def check_access(
        self,
        user_id: str,
        user_roles: List[str],
        resource: ResourceIdentifier,
        permission: Permission,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Check if user has permission on resource.
        
        Returns (allowed, reason) tuple.
        """
        context = context or {}
        
        # Collect all applicable permissions
        allowed = False
        denied = False
        
        # Check role-based permissions
        for role_id in user_roles:
            role = self._role_registry.get(role_id)
            if not role:
                continue
            
            effective_perms = role.get_effective_permissions(self._role_registry)
            
            if permission in effective_perms:
                allowed = True
            
            # Check for wildcard permissions
            wildcard = self._get_wildcard_permission(permission)
            if wildcard in effective_perms:
                allowed = True
        
        # Check ACL entries
        for entry in self._entries:
            # Check if entry applies to this user/role
            applies = False
            
            if entry.principal_type == "user" and entry.principal_id == user_id:
                applies = entry.applies_to("user", user_id, resource)
            elif entry.principal_type == "role" and entry.principal_id in user_roles:
                applies = entry.applies_to("role", entry.principal_id, resource)
            
            if not applies:
                continue
            
            # Check conditions
            if not entry.check_conditions(context):
                continue
            
            # Check permission
            if permission in entry.permissions:
                if entry.effect == "deny":
                    denied = True
                else:
                    allowed = True
        
        if denied:
            return False, "Access denied by ACL"
        
        if allowed:
            return True, "Access granted"
        
        return False, "Permission not granted"
    
    def _get_wildcard_permission(self, permission: Permission) -> Optional[Permission]:
        """Get wildcard equivalent of a permission."""
        # e.g., terminal.view_details -> terminal.view_*
        parts = permission.value.split(".")
        if len(parts) == 2:
            wildcard_str = f"{parts[0]}.*"
            return PermissionRegistry.search(wildcard_str)
        return None
    
    def get_effective_permissions(
        self,
        user_id: str,
        user_roles: List[str],
        resource: ResourceIdentifier
    ) -> Set[Permission]:
        """Get all effective permissions for user on resource."""
        effective: Set[Permission] = set()
        
        # From roles
        for role_id in user_roles:
            role = self._role_registry.get(role_id)
            if role:
                effective.update(role.get_effective_permissions(self._role_registry))
        
        # From ACLs
        for entry in self._entries:
            applies = False
            if entry.principal_type == "user" and entry.principal_id == user_id:
                applies = entry.applies_to("user", user_id, resource)
            elif entry.principal_type == "role" and entry.principal_id in user_roles:
                applies = entry.applies_to("role", entry.principal_id, resource)
            
            if applies and entry.effect == "allow":
                effective.update(entry.permissions)
            elif applies and entry.effect == "deny":
                effective.difference_update(entry.permissions)
        
        return effective
    
    def audit_access(
        self,
        user_id: str,
        resource: ResourceIdentifier,
        permission: Permission,
        granted: bool,
        context: Dict[str, Any]
    ) -> None:
        """Log access check for audit."""
        # Implementation would log to audit system
        pass


# ============================================================================
# Permission Helper Functions
# ============================================================================

def has_permission(
    user_permissions: Set[Permission],
    required: Permission
) -> bool:
    """Check if user has required permission."""
    if required in user_permissions:
        return True
    
    # Check wildcard
    resource = required.value.split(".")[0]
    wildcard = PermissionRegistry.get_by_resource(resource)
    return bool(user_permissions & wildcard)


def has_any_permission(
    user_permissions: Set[Permission],
    required: Set[Permission]
) -> bool:
    """Check if user has any of the required permissions."""
    return bool(user_permissions & required)


def has_all_permissions(
    user_permissions: Set[Permission],
    required: Set[Permission]
) -> bool:
    """Check if user has all required permissions."""
    return required.issubset(user_permissions)


def get_permission_category(permission: Permission) -> PermissionCategory:
    """Get the category for a permission."""
    resource = permission.value.split(".")[0]
    return PermissionRegistry._get_category_for_resource(resource)


def format_permission_list(permissions: Set[Permission]) -> Dict[str, List[str]]:
    """Format permissions by category for display."""
    result: Dict[str, List[str]] = {}
    
    for perm in permissions:
        cat = get_permission_category(perm)
        cat_name = cat.value
        if cat_name not in result:
            result[cat_name] = []
        result[cat_name].append(perm.value)
    
    # Sort each category
    for cat in result:
        result[cat].sort()
    
    return result
