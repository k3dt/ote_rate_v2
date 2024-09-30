import logging
from datetime import timedelta, datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import aiohttp_client
from homeassistant.core import HomeAssistant
from .const import URL
from zoneinfo import ZoneInfo

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    session = aiohttp_client.async_get_clientsession(hass)
    coordinator = AmigonetOTEDataUpdateCoordinator(hass, session)
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        AmigonetOTESensor(coordinator, "current_ote_price", "Aktuální OTE cena", "CZK"),
        AmigonetOTESensor(coordinator, "average_ote_price", "Průměrná OTE cena", "CZK"),
    ]

    for i in range(1, 7):
        sensors.append(
            AmigonetOTEHourSensor(coordinator, f"min{i}", f"Min OTE ({i} hod)")
        )

    async_add_entities(sensors)


class AmigonetOTESensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, unit):
        super().__init__(coordinator)
        self._key = key
        self._name = name
        self._unit = unit

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._key

    @property
    def state(self):
        return self.coordinator.data.get(self._key)

    @property
    def unit_of_measurement(self):
        return self._unit


class AmigonetOTEHourSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self._key = key
        self._name = name
        self._attributes = {"hodiny": []}

    @property
    def name(self):
        return self._name

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def unique_id(self):
        return "min_ote_" + self._key + "_hours"

    @property
    def state(self):
        prague_tz = ZoneInfo("Europe/Prague")
        current_time = datetime.now(prague_tz)
        current_hour = current_time.hour
        hours_list = self.coordinator.data.get(self._key, [])
        self._attributes["hodiny"] = hours_list
        # _LOGGER.debug(f"{self._name} - Hours: {hours_list}, Current: {current_hour}")
        return current_hour in hours_list

    @property
    def icon(self):
        return "mdi:clock"


class AmigonetOTEDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, session):
        self.session = session
        super().__init__(
            hass,
            _LOGGER,
            name="Amigonet OTE Data",
            update_interval=timedelta(minutes=5),
        )
        self.data = {}

    async def _async_update_data(self):
        try:
            async with self.session.get(URL) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Error fetching data: {response.status}")
                self.data = await response.json()
                # _LOGGER.debug(f"Data: {self.data}")
            return self.data
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")
