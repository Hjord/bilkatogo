from datetime import timedelta
from logging import getLogger

from homeassistant.const import Platform

LOGGER = getLogger(__package__)

DOMAIN = "bilkatogo"
PLATFORMS: list[Platform] = [Platform.SENSOR]

UPDATE_INTERVAL = timedelta(minutes=60)
