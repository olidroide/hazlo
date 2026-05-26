from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree

import httpx
import pytest

from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.adapters.rss_adapter import (
    RssSourceAdapter,
    _parse_dates,
    _parse_price,
)

_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service fechaActualizacion="2026-05-20" id="109019">
        <basicData>
            <language>es</language>
            <name><![CDATA[The CUBintage]]></name>
            <email/>
            <phone/>
            <fax/>
            <title><![CDATA[The CUBintage]]></title>
            <body><![CDATA[<p>Concierto de jazz.</p>]]></body>
            <web>https://www.esmadrid.com/agenda/cubintage</web>
            <idrt>68233</idrt>
            <nombrert>Café Central Ateneo</nombrert>
        </basicData>
        <geoData>
            <address>de Santa Catalina, 10</address>
            <zipcode>28014</zipcode>
            <locality/>
            <country>Spain</country>
            <latitude>40.415443200000</latitude>
            <longitude>-3.697904600000</longitude>
            <subAdministrativeArea>Madrid</subAdministrativeArea>
        </geoData>
        <multimedia/>
        <extradata>
            <item name="idTipo">6</item>
            <item name="Tipo">Eventos</item>
            <item name="Servicios de pago"><![CDATA[<p>Desde 17,50 €</p>]]></item>
            <item name="Horario"><![CDATA[<p>19:30 h</p>]]></item>
            <fechas>
                <rango>
                    <inicio>12/06/2026</inicio>
                    <dias>5</dias>
                    <fin>12/06/2026</fin>
                </rango>
            </fechas>
        </extradata>
    </service>
    <service fechaActualizacion="2026-05-20" id="109020">
        <basicData>
            <language>es</language>
            <name><![CDATA[Evento Gratuito]]></name>
            <title><![CDATA[Evento Gratuito]]></title>
            <web>https://www.esmadrid.com/agenda/gratuito</web>
        </basicData>
        <geoData>
            <address>Plaza Mayor, 1</address>
            <subAdministrativeArea>Centro</subAdministrativeArea>
        </geoData>
        <extradata>
            <item name="Servicios de pago"><![CDATA[<p>Gratuito</p>]]></item>
            <item name="Horario"><![CDATA[<p>10:00 h</p>]]></item>
            <fechas>
                <rango>
                    <inicio>15/07/2026</inicio>
                    <fin>16/07/2026</fin>
                </rango>
            </fechas>
        </extradata>
    </service>
</serviceList>
"""

_EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
</serviceList>
"""

_XML_WITH_SERVICE_NO_BASIC_DATA = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="1">
        <geoData>
            <address>Some address</address>
        </geoData>
    </service>
</serviceList>
"""

_XML_WITH_MINIMAL_SERVICE = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="2">
        <basicData>
            <title>Minimal Event</title>
        </basicData>
    </service>
</serviceList>
"""


def _make_source(url: str | None = "https://example.com/feed.xml") -> Source:
    return Source(
        name="Test RSS",
        source_type=SourceType.RSS,
        url=url,
    )


def _mock_httpx_response(text: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=response
        )
    return response


@pytest.mark.asyncio
async def test_rss_adapter_parses_xml() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_SAMPLE_XML)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 2

    first = raw_events[0]
    assert first["title"] == "The CUBintage"
    assert first["raw_title"] == "The CUBintage"
    assert first["address"] == "de Santa Catalina, 10"
    assert first["neighborhood"] == "Madrid"
    assert first["source_url"] == "https://www.esmadrid.com/agenda/cubintage"
    assert first["is_free"] is False
    assert first["venue"] == "Café Central Ateneo"
    assert first["description"] == "Concierto de jazz."
    assert first["raw_description"] == "<p>Concierto de jazz.</p>"

    second = raw_events[1]
    assert second["title"] == "Evento Gratuito"
    assert second["is_free"] is True
    assert second["address"] == "Plaza Mayor, 1"


@pytest.mark.asyncio
async def test_rss_adapter_empty_xml() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_EMPTY_XML)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert raw_events == []


@pytest.mark.asyncio
async def test_rss_adapter_skips_service_without_basic_data() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITH_SERVICE_NO_BASIC_DATA)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert raw_events == []


@pytest.mark.asyncio
async def test_rss_adapter_minimal_service() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITH_MINIMAL_SERVICE)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 1
    event = raw_events[0]
    assert event["title"] == "Minimal Event"
    assert event["address"] == ""
    assert event["start_at"] is None
    assert event["is_free"] is False


@pytest.mark.asyncio
async def test_rss_adapter_url_none() -> None:
    adapter = RssSourceAdapter()
    source = _make_source(url=None)
    raw_events = await adapter.fetch(source)
    assert raw_events == []


@pytest.mark.asyncio
async def test_rss_adapter_http_error() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response("Not Found", status_code=404)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.fetch(_make_source())


@pytest.mark.asyncio
async def test_rss_adapter_normalize() -> None:
    adapter = RssSourceAdapter()
    raw = {
        "title": "Test Event",
        "address": "Calle Mayor 1",
        "neighborhood": "Centro",
        "metro": "Sol",
        "start_at": "2026-06-12T19:30:00+00:00",
        "end_at": "2026-06-12T21:30:00+00:00",
        "price_amount_cents": 1750,
        "is_free": False,
        "price_notes": "Desde 17,50 €",
        "ticket_url": None,
        "ticket_notes": None,
        "is_children_activity": False,
        "is_toddler_friendly": False,
        "source_url": "https://example.com/event",
    }

    event = await adapter.normalize(raw)

    assert event.title == "Test Event"
    assert event.location is not None
    assert event.location.address == "Calle Mayor 1"
    assert event.location.neighborhood == "Centro"
    assert event.location.metro == "Sol"

    assert event.price is not None
    assert event.start_at is not None
    assert event.start_at.tzinfo == UTC
    assert event.price.amount_cents == 1750
    assert event.source_url == "https://example.com/event"


@pytest.mark.asyncio
async def test_rss_adapter_normalize_missing_optional_fields() -> None:
    adapter = RssSourceAdapter()
    raw = {
        "title": "Bare Event",
        "source_url": "https://example.com/bare",
    }

    event = await adapter.normalize(raw)

    assert event.title == "Bare Event"
    assert event.location is not None
    assert event.location.address == ""
    assert event.location.neighborhood == ""
    assert event.location.metro is None
    assert event.start_at is None

    assert event.price is not None
    assert event.price.is_free is True  # unknown price → treat as free, don't require ticket_url
    assert event.price.amount_cents is None

    assert event.ticket_info is not None
    assert event.ticket_info.url is None


@pytest.mark.asyncio
async def test_rss_adapter_normalize_free_event() -> None:
    adapter = RssSourceAdapter()
    raw = {
        "title": "Free Event",
        "source_url": "https://example.com/free",
        "is_free": True,
        "start_at": "2026-07-01T10:00:00+00:00",
    }

    event = await adapter.normalize(raw)

    assert event.price is not None
    assert event.price.is_free is True
    assert event.price.amount_cents is None


def test_parse_dates_single_day() -> None:
    start, end = _parse_dates("12/06/2026", "12/06/2026", "19:30 h")
    assert start is not None
    assert "2026-06-12" in start
    assert "19:30" in start
    assert end is None


def test_parse_dates_multi_day() -> None:
    start, end = _parse_dates("24/10/2026", "25/10/2026", "11:00 h")
    assert start is not None
    assert end is not None
    assert "2026-10-24" in start
    assert "2026-10-25" in end


def test_parse_dates_no_time() -> None:
    start, _end = _parse_dates("12/06/2026", "12/06/2026", "")
    assert start is not None
    assert "00:00" in start


def test_parse_dates_invalid_format() -> None:
    start, end = _parse_dates("not-a-date", "not-a-date", "19:30 h")
    assert start is None
    assert end is None


def test_parse_dates_no_fin() -> None:
    start, end = _parse_dates("12/06/2026", "", "19:30 h")
    assert start is not None
    assert end is None


def test_parse_dates_epoch_rejected() -> None:
    start, end = _parse_dates("01/01/1970", "01/01/1970", "18:30 h")
    assert start is None
    assert end is None


def test_parse_dates_before_min_year_rejected() -> None:
    start, end = _parse_dates("01/01/2010", "01/01/2010", "10:00 h")
    assert start is None
    assert end is None


def test_parse_dates_spanish_format_dias_y() -> None:
    start, end = _parse_dates("días 19 y 20 de junio de 2026", "", "18:30 h")
    assert start is not None
    assert "2026-06-19" in start
    assert "18:30" in start
    assert end is None


def test_parse_dates_spanish_format_current_year() -> None:
    start, end = _parse_dates("días 15 y 16 de marzo", "", "12:00 h")
    assert start is not None
    assert "-03-15" in start
    assert end is None


def test_parse_dates_spanish_format_invalid_month() -> None:
    start, end = _parse_dates("días 19 y 20 de fakebruary", "", "10:00 h")
    assert start is None
    assert end is None


def test_parse_dates_time_without_h_suffix() -> None:
    start, _end = _parse_dates("12/06/2026", "12/06/2026", "19:30")
    assert start is not None
    assert "00:00" in start


def test_parse_price_with_amount() -> None:
    amount_cents, is_free, _notes = _parse_price("Desde 17,50 €")
    assert amount_cents is not None
    assert amount_cents == 1750
    assert is_free is False


def test_parse_price_free() -> None:
    amount, is_free, _notes = _parse_price("Gratuito")
    assert amount is None
    assert is_free is True


def test_parse_price_empty() -> None:
    amount, is_free, notes = _parse_price("")
    assert amount is None
    assert is_free is False
    assert notes is None


def test_parse_price_none() -> None:
    amount, is_free, notes = _parse_price(None)
    assert amount is None
    assert is_free is False
    assert notes is None


def test_parse_price_free_variants() -> None:
    for text in ["gratis", "Free", "GRATUITO"]:
        _, is_free, _ = _parse_price(text)
        assert is_free is True, f"Expected free for '{text}'"


def test_parse_price_no_match() -> None:
    amount, is_free, notes = _parse_price("Consultar precio")
    assert amount is None
    assert is_free is False
    assert notes == "Consultar precio"


# ============================================================
# Additional edge case tests for RSS/XML parsing
# ============================================================

_XML_WITH_CDATA_IN_ALL_FIELDS = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="100">
        <basicData>
            <name><![CDATA[<b>Special Event</b>]]></name>
            <title><![CDATA[<h1>Special Event</h1>]]></title>
            <body><![CDATA[<p>Descripción con <strong>HTML</strong> y &amp; entidades.</p>]]></body>
            <web><![CDATA[https://example.com/event]]></web>
            <nombrert><![CDATA[Sala <i>Principal</i>]]></nombrert>
        </basicData>
        <geoData>
            <address><![CDATA[Calle de <b>Sol</b>, 5]]></address>
            <subAdministrativeArea><![CDATA[<i>Centro</i>]]></subAdministrativeArea>
        </geoData>
        <extradata>
            <item name="Horario"><![CDATA[<p>20:00 h</p>]]></item>
            <item name="Servicios de pago"><![CDATA[<p>25,00 €</p>]]></item>
            <fechas>
                <rango>
                    <inicio>01/12/2026</inicio>
                    <fin>01/12/2026</fin>
                </rango>
            </fechas>
            <categorias>
                <categoria>
                    <item name="Categoria">Música</item>
                </categoria>
                <subcategoria>
                    <item name="SubCategoria">Jazz</item>
                </subcategoria>
            </categorias>
        </extradata>
    </service>
</serviceList>
"""

_XML_WITH_MULTIPLE_TIMES = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="200">
        <basicData>
            <title>Multi-time Event</title>
            <web>https://example.com/multi</web>
        </basicData>
        <geoData>
            <address>Plaza España, 1</address>
        </geoData>
        <extradata>
            <item name="Horario"><![CDATA[<p>10:00 h - 14:00 h y 16:00 h - 20:00 h</p>]]></item>
            <fechas>
                <rango>
                    <inicio>15/08/2026</inicio>
                    <fin>15/08/2026</fin>
                </rango>
            </fechas>
        </extradata>
    </service>
</serviceList>
"""

_XML_WITH_PRICE_RANGE = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="300">
        <basicData>
            <title>Price Range Event</title>
            <web>https://example.com/price-range</web>
        </basicData>
        <geoData>
            <address>Calle Mayor, 10</address>
        </geoData>
        <extradata>
            <item name="Horario"><![CDATA[<p>19:00 h</p>]]></item>
            <item name="Servicios de pago"><![CDATA[<p>Desde 10 € hasta 50 €</p>]]></item>
            <fechas>
                <rango>
                    <inicio>20/09/2026</inicio>
                    <fin>20/09/2026</fin>
                </rango>
            </fechas>
        </extradata>
    </service>
</serviceList>
"""

_XML_WITH_THOUSAND_SEPARATOR = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="400">
        <basicData>
            <title>Thousand Separator Event</title>
            <web>https://example.com/thousand</web>
        </basicData>
        <geoData>
            <address>Gran Vía, 1</address>
        </geoData>
        <extradata>
            <item name="Horario"><![CDATA[<p>21:00 h</p>]]></item>
            <item name="Servicios de pago"><![CDATA[<p>1.234,56 €</p>]]></item>
            <fechas>
                <rango>
                    <inicio>05/11/2026</inicio>
                    <fin>05/11/2026</fin>
                </rango>
            </fechas>
        </extradata>
    </service>
</serviceList>
"""

_XML_WITHOUT_EXTRADATA = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="500">
        <basicData>
            <title>No ExtraData Event</title>
            <web>https://example.com/no-extra</web>
        </basicData>
        <geoData>
            <address>Calle Sierpes, 5</address>
            <subAdministrativeArea>Sevilla</subAdministrativeArea>
        </geoData>
    </service>
</serviceList>
"""

_XML_WITH_EMPTY_TITLE_AND_NAME = """<?xml version="1.0" encoding="UTF-8"?>
<serviceList>
    <service id="600">
        <basicData>
            <name/>
            <title/>
            <web>https://example.com/empty-title</web>
        </basicData>
        <geoData>
            <address>Some address</address>
        </geoData>
    </service>
</serviceList>
"""


@pytest.mark.asyncio
async def test_rss_adapter_cdata_in_all_fields() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITH_CDATA_IN_ALL_FIELDS)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 1
    event = raw_events[0]
    assert event["title"] == "Special Event"
    assert event["raw_title"] == "<h1>Special Event</h1>"
    assert event["description"] == "Descripción con HTML y & entidades."
    assert event["raw_description"] == "<p>Descripción con <strong>HTML</strong> y & entidades.</p>"
    assert event["source_url"] == "https://example.com/event"
    assert event["venue"] == "Sala <i>Principal</i>"
    assert event["address"] == "Calle de <b>Sol</b>, 5"
    assert event["neighborhood"] == "<i>Centro</i>"
    assert event["is_free"] is False
    assert event["categories"] == ["Música", "Jazz"]


@pytest.mark.asyncio
async def test_rss_adapter_multiple_times_in_schedule() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITH_MULTIPLE_TIMES)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 1
    event = raw_events[0]
    assert event["start_at"] is not None
    assert "10:00" in event["start_at"]


@pytest.mark.asyncio
async def test_rss_adapter_price_range() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITH_PRICE_RANGE)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 1
    event = raw_events[0]
    assert event["price_amount_cents"] is not None
    assert event["price_amount_cents"] == 1000
    assert event["is_free"] is False


@pytest.mark.asyncio
async def test_rss_adapter_thousand_separator_price() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITH_THOUSAND_SEPARATOR)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 1
    event = raw_events[0]
    assert event["price_amount_cents"] is not None
    assert event["price_amount_cents"] == 123456


@pytest.mark.asyncio
async def test_rss_adapter_without_extradata() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITHOUT_EXTRADATA)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 1
    event = raw_events[0]
    assert event["title"] == "No ExtraData Event"
    assert event["start_at"] is None
    assert event["is_free"] is False
    assert event["price_amount_cents"] is None
    assert event["categories"] == []


@pytest.mark.asyncio
async def test_rss_adapter_empty_title_and_name() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response(_XML_WITH_EMPTY_TITLE_AND_NAME)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        raw_events = await adapter.fetch(_make_source())

    assert len(raw_events) == 1
    event = raw_events[0]
    assert event["title"] == ""


@pytest.mark.asyncio
async def test_rss_adapter_connection_error() -> None:
    adapter = RssSourceAdapter()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.ConnectError):
            await adapter.fetch(_make_source())


@pytest.mark.asyncio
async def test_rss_adapter_timeout_error() -> None:
    adapter = RssSourceAdapter()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.TimeoutException):
            await adapter.fetch(_make_source())


@pytest.mark.asyncio
async def test_rss_adapter_malformed_xml() -> None:
    adapter = RssSourceAdapter()
    mock_response = _mock_httpx_response("<not valid xml><unclosed>")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ElementTree.ParseError):
            await adapter.fetch(_make_source())


@pytest.mark.asyncio
async def test_rss_adapter_normalize_missing_required_keys() -> None:
    adapter = RssSourceAdapter()
    raw = {}

    with pytest.raises(KeyError):
        await adapter.normalize(raw)


@pytest.mark.asyncio
async def test_rss_adapter_normalize_invalid_datetime() -> None:
    adapter = RssSourceAdapter()
    raw = {
        "title": "Test",
        "source_url": "https://example.com",
        "start_at": "not-a-datetime",
    }

    with pytest.raises(ValueError):
        await adapter.normalize(raw)


@pytest.mark.asyncio
async def test_rss_adapter_normalize_invalid_price() -> None:
    adapter = RssSourceAdapter()
    raw = {
        "title": "Test",
        "source_url": "https://example.com",
        "price_amount_cents": None,
    }

    event = await adapter.normalize(raw)

    assert event.price is not None
    assert event.price.amount_cents is None


def test_parse_dates_empty_string_inicio() -> None:
    start, end = _parse_dates("", "12/06/2026", "19:30 h")
    assert start is None
    assert end is None


def test_parse_dates_none_values() -> None:
    start, end = _parse_dates(None, None, None)
    assert start is None
    assert end is None


def test_parse_dates_timezone_in_output() -> None:
    start, _end = _parse_dates("12/06/2026", "", "19:30 h")
    assert start is not None
    assert "+00:00" in start or "Z" in start


def test_parse_price_without_euro_symbol() -> None:
    amount, is_free, notes = _parse_price("10.50")
    assert amount is None
    assert is_free is False
    assert notes == "10.50"


def test_parse_price_with_html_entities() -> None:
    amount_cents, is_free, _notes = _parse_price("<p>15,00 €</p>")
    assert amount_cents is not None
    assert amount_cents == 1500
    assert is_free is False


def test_parse_dates_hour_gte_24_rolls_to_next_day() -> None:
    start, end = _parse_dates("12/06/2026", "12/06/2026", "25:30 h")
    assert start is not None
    assert "2026-06-13" in start
    assert "01:30" in start
    assert end is None


def test_parse_dates_hour_gte_24_multi_day() -> None:
    start, end = _parse_dates("12/06/2026", "13/06/2026", "24:00 h")
    assert start is not None
    assert "2026-06-13" in start
    assert "00:00" in start
    assert end is not None
    assert "2026-06-13" in end


def test_parse_price_zero_amount() -> None:
    amount, is_free, _notes = _parse_price("0,00 €")
    assert amount is not None
    assert float(amount) == 0.00
    assert is_free is False
