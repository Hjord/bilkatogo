from datetime import timedelta
from logging import getLogger

from homeassistant.const import Platform

LOGGER = getLogger(__package__)

DOMAIN = "bilkatogo"
PLATFORMS: list[Platform] = [Platform.SENSOR]

EVENT_SUBSTITUTION = f"{DOMAIN}_substitution"

UPDATE_INTERVAL = timedelta(minutes=60)
FAST_UPDATE_INTERVAL = timedelta(minutes=5)
FAST_UPDATE_LEAD_TIME = timedelta(hours=3)
