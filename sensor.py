import logging
from datetime import datetime
import requests
import homeassistant.util.dt as dt_util

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)

API_URL = "https://www.amigonet.cz/api/ote"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Nastavení senzorů pro OTE ceny."""
    ote_data = OTEData(hass)
    await ote_data.async_update()  # Načtení počátečních dat

    sensors = []
    # Vytvoření senzorů min_ote_price_X_hour
    for x in range(1, 10):
        sensors.append(MinOTEPriceSensor(ote_data, x, hass))
    # Senzor pro aktuální OTE cenu
    sensors.append(CurrentOTEPriceSensor(ote_data, hass))
    # Senzor pro průměrnou OTE cenu
    sensors.append(AverageOTEPriceSensor(ote_data, hass))

    async_add_entities(sensors, True)

    # Aktualizace senzorů na začátku každé hodiny
    async def update_sensors():
        await ote_data.async_update()
        for sensor in sensors:
            sensor.async_schedule_update_ha_state(True)

    async_track_time_change(hass, update_sensors, minute=0, second=0)


class OTEData:
    """Třída pro držení OTE dat."""

    def __init__(self, hass):
        self.hass = hass
        self.prices = []
        self.average_price = None
        self.last_update = None

    async def async_update(self):
        """Načtení nových dat z API."""
        _LOGGER.warning("Aktualizace OTE dat")
        now_utc = dt_util.utcnow().date()
        if self.last_update == now_utc:
            return
        try:
            response = await self.hass.async_add_executor_job(requests.get, API_URL)
            data = response.json()
            self.prices = data["prices"]
            self.average_price = data["average_ote_price"]  # Získání průměrné ceny
            self.last_update = now_utc
            _LOGGER.debug("Načtená OTE data: %s", data)
        except Exception as e:
            _LOGGER.error("Chyba při načítání OTE dat: %s", e)
            return


class MinOTEPriceSensor(SensorEntity):
    """Senzor pro min_ote_price_Xhour."""

    def __init__(self, ote_data, x, hass):
        self.ote_data = ote_data
        self.x = x
        self.hass = hass
        self._state = None
        self._hours = []

    @property
    def name(self):
        """Název senzoru."""
        return f"Min OTE ({self.x} hrs)"

    @property
    def unique_id(self):
        """Unikátní ID senzoru."""
        return f"min_ote_{self.x}_hod"

    @property
    def state(self):
        """Stav senzoru."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Atributy senzoru."""
        return {"hours": self._hours}

    async def async_update(self):
        """Aktualizace stavu senzoru."""
        if not self.ote_data.prices:
            return

        now = dt_util.now()
        current_date = now.date()

        # Filtrování cen pro dnešní datum a převod časů do lokální časové zóny
        prices = []
        for price_entry in self.ote_data.prices:
            # Parsing UTC datetime from API
            price_datetime = datetime.strptime(price_entry["date"], "%Y-%m-%d %H:%M:%S")
            price_datetime = price_datetime.replace(tzinfo=dt_util.UTC)
            # Converting to local timezone
            local_datetime = price_datetime.astimezone(dt_util.DEFAULT_TIME_ZONE)
            if local_datetime.date() == current_date:
                price_entry["datetime"] = local_datetime
                prices.append(price_entry)

        if not prices:
            _LOGGER.error("Žádná data cen pro dnešek")
            return

        # Seřazení cen a získání X nejnižších hodin
        sorted_prices = sorted(prices, key=lambda x: x["price"])
        lowest_prices = sorted_prices[: self.x]
        self._hours = [price["datetime"].hour for price in lowest_prices]

        current_hour = now.hour

        self._state = current_hour in self._hours


class CurrentOTEPriceSensor(SensorEntity):
    """Senzor pro aktuální OTE cenu."""

    def __init__(self, ote_data, hass):
        self.ote_data = ote_data
        self.hass = hass
        self._state = None

    @property
    def name(self):
        """Název senzoru."""
        return "Actual OTE Price"

    @property
    def unique_id(self):
        """Unikátní ID senzoru."""
        return "current_ote_price"

    @property
    def unit_of_measurement(self):
        """Jednotka měření."""
        return "Kč/MWh"

    @property
    def state(self):
        """Stav senzoru."""
        return self._state

    async def async_update(self):
        """Aktualizace stavu senzoru."""
        if not self.ote_data.prices:
            return

        now = dt_util.now()
        current_hour = now.hour
        current_date = now.date()

        for price_entry in self.ote_data.prices:
            # Parsing UTC datetime from API
            entry_datetime = datetime.strptime(price_entry["date"], "%Y-%m-%d %H:%M:%S")
            entry_datetime = entry_datetime.replace(tzinfo=dt_util.UTC)
            # Converting to local timezone
            local_datetime = entry_datetime.astimezone(dt_util.DEFAULT_TIME_ZONE)
            if (
                local_datetime.hour == current_hour
                and local_datetime.date() == current_date
            ):
                self._state = float(price_entry["price"])
                break
        else:
            self._state = None


class AverageOTEPriceSensor(SensorEntity):
    """Senzor pro průměrnou OTE cenu."""

    def __init__(self, ote_data, hass):
        self.ote_data = ote_data
        self.hass = hass
        self._state = None

    @property
    def name(self):
        """Název senzoru."""
        return "Average OTE Price"

    @property
    def unique_id(self):
        """Unikátní ID senzoru."""
        return "average_ote_price"

    @property
    def unit_of_measurement(self):
        """Jednotka měření."""
        return "Kč/MWh"

    @property
    def state(self):
        """Stav senzoru."""
        return self._state

    async def async_update(self):
        """Aktualizace stavu senzoru."""
        if self.ote_data.average_price is not None:
            self._state = float(self.ote_data.average_price)
        else:
            self._state = None
