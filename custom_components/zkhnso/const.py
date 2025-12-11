"""Constants for the ZKHNSO integration."""

DOMAIN = "zkhnso"

# API URLs
API_BASE_URL = "https://xn--f1aijeow.xn--p1ai/room/lk/"
API_URL_PREFLIGHT = "login.action"
API_URL_LOGIN = "doLogin!enter.action"
API_URL_TARIFFS = "tariffs.action"
API_URL_METERS = "counters.action"
API_URL_MAIN = "main.action"

# Configuration keys
CONF_API_KEY = "api_key"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Default values
DEFAULT_NAME = "ZKHNSO"
DEFAULT_SCAN_INTERVAL = 3600  # 1 hour in seconds

# Attributes
ATTR_STATUS = "status"
ATTR_LAST_UPDATE = "last_update"

# Session keys
SESSION_JSESSIONID = "JSESSIONID"
SESSION_FORM_TOKEN = "FORM_TOKEN"

