from datetime import timedelta
from logging import getLogger

from homeassistant.const import Platform

LOGGER = getLogger(__package__)

DOMAIN = "bilkatogo"
PLATFORMS: list[Platform] = [Platform.SENSOR]
CURRENCY = "DKK"

EVENT_SUBSTITUTION = f"{DOMAIN}_substitution"
EVENT_MISSING_ITEM = f"{DOMAIN}_missing_item"

UPDATE_INTERVAL = timedelta(minutes=60)
FAST_UPDATE_INTERVAL = timedelta(minutes=5)
FAST_UPDATE_LEAD_TIME = timedelta(hours=3)
