import pytest
from app.extraction.config_loader import load_city_config, list_configured_cities, CityConfig


def test_list_configured_cities():
    cities = list_configured_cities()
    assert "dallas_tx" in cities
    assert "fort_worth_tx" in cities
    # Template should be excluded from active list
    assert "_template" not in cities


def test_load_dallas_config():
    config = load_city_config("dallas_tx")
    assert isinstance(config, CityConfig)
    assert config.jurisdiction == "Dallas, TX"
    assert config.platform == "socrata"
    assert config.socrata is not None
    assert config.socrata.domain == "data.dallasopendata.com"
    assert config.socrata.dataset_id == "ydr8-5enu"


def test_load_fort_worth_config():
    config = load_city_config("fort_worth_tx")
    assert isinstance(config, CityConfig)
    assert config.jurisdiction == "Fort Worth, TX"
    assert config.platform == "accela"
    assert config.portal is not None
    assert "aca-prod.accela.com" in config.portal.base_url
    assert config.disclaimer is not None
    assert config.disclaimer.has_disclaimer is True


def test_load_nonexistent_city():
    with pytest.raises(FileNotFoundError):
        load_city_config("nonexistent_city_zz")
